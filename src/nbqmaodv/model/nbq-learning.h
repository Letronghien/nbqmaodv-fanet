/*
 * nbq-learning.h -- NBQ-MAODV (Neighbour-Bootstrapped Q-learning Multipath AODV)
 * Header-only learning agent + packet tag, to be called from an existing
 * SA-QMAODV / QMAODV routing module in NS-3.
 *
 *   neighbourBootstrap = true   -> NBQ-MAODV   (path-cost Q, bootstraps from V_u of the next hop)
 *   neighbourBootstrap = false  -> SA-QMAODV   (utility Q, bootstraps from own max Q)
 *
 * The agent keeps, for every destination, up to K next hops with (hop count, Q).
 * Your routing module keeps doing discovery, RREP/RERR processing and packet I/O;
 * it only calls the hooks marked [HOOK] below.  See NBQ-MAODV_huong_dan.md.
 */
#ifndef NBQMAODV_NBQ_LEARNING_H
#define NBQMAODV_NBQ_LEARNING_H

#include "ns3/ipv4-address.h"
#include "ns3/nstime.h"
#include "ns3/random-variable-stream.h"
#include "ns3/tag.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <deque>
#include <limits>
#include <map>
#include <ostream>
#include <utility>
#include <vector>

namespace ns3
{
namespace nbq
{

/* ------------------------------------------------------------------ parameters */
struct Params
{
    // ---- variant switches
    bool neighbourBootstrap = true; // NBQ-MAODV (true) or SA-QMAODV (false)
    bool adaptiveEpsilon = true;    // +0.2 on RERR / -0.02 per 5 s ; false -> QMAODV schedule
    bool adaptiveAlpha = true;      // alpha_t from SeqNo dynamics ; false -> alphaFixed
    bool adaptiveReward = true;     // 4 reward regimes ; false -> (0.6 ACK, 0.4 delay)
    bool keepQOnReinstall = false;  // false = re-initialise Q on every new route (as in the paper)

    // ---- learning
    double alphaFixed = 0.5;
    double gammaLocal = 0.9;  // SA-QMAODV target  r + gamma * max_a' Q_v
    double gammaNb = 0.95;    // NBQ target        -(1-r) + gamma' * V_u
    double vFail = 5.0;       // advertised cost of a node without a route: V = -vFail
    double hcPriorCost = 0.3; // NBQ initial Q = -hcPriorCost * HC
    double dRef = 0.010;      // delay normalisation (s)

    // ---- exploration
    double eps0 = 0.5, epsMin = 0.1, epsMax = 0.5, epsBump = 0.2, epsStep = 0.02;
    Time epsPeriodAdaptive = Seconds(5);  // adaptive schedule
    Time epsPeriodFixed = Seconds(10);    // QMAODV schedule (floor 0)

    // ---- learning-rate controller
    double lambda = 0.5;
    Time seqWindow = Seconds(5);

    // ---- context detection for the reward regimes
    double lowEnergy = 0.2;  // residual-energy fraction
    double ackThr = 0.8;     // EWMA of ACK success below -> lossy regime
    double congFactor = 2.0; // EWMA delay above congFactor * floor -> congestion regime
    double ewma = 0.1;       // weight of the newest sample

    // ---- neighbour values
    Time nbValueTtl = Seconds(3); // ignore V_u older than this (3 x HELLO interval)
};

/* ------------------------------------------------------------------ packet tag
 * Carries (destination, V_u(destination)) of the SENDER.  Attach it to every AODV
 * control packet the node sends (HELLO, RREQ, RREP, RERR).  8 bytes.            */
class QValueTag : public Tag
{
  public:
    QValueTag() = default;
    QValueTag(Ipv4Address dst, double v) : m_dst(dst), m_v(static_cast<float>(v)) {}

    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("ns3::nbq::QValueTag")
                                .SetParent<Tag>()
                                .SetGroupName("Aodv")
                                .AddConstructor<QValueTag>();
        return tid;
    }
    TypeId GetInstanceTypeId() const override { return GetTypeId(); }
    uint32_t GetSerializedSize() const override { return 8; }
    void Serialize(TagBuffer i) const override
    {
        uint32_t bits;
        std::memcpy(&bits, &m_v, 4);
        i.WriteU32(m_dst.Get());
        i.WriteU32(bits);
    }
    void Deserialize(TagBuffer i) override
    {
        m_dst = Ipv4Address(i.ReadU32());
        uint32_t bits = i.ReadU32();
        std::memcpy(&m_v, &bits, 4);
    }
    void Print(std::ostream& os) const override { os << "dst=" << m_dst << " V=" << m_v; }

    Ipv4Address GetDst() const { return m_dst; }
    double GetValue() const { return m_v; }

  private:
    Ipv4Address m_dst;
    float m_v = 0.0f;
};

/* ------------------------------------------------------------------ agent */
class Agent
{
  public:
    struct Entry
    {
        uint32_t hops;
        double q;
    };

    explicit Agent(const Params& p = Params()) : m_p(p), m_eps(p.eps0) {}

    void SetParams(const Params& p) { m_p = p; m_eps = p.eps0; }
    const Params& GetParams() const { return m_p; }

    /* [HOOK 1] a RREP (re)installs forward routes to dst.
     * nextHops = {(next hop, hop count to dst via it)}, at most K entries.       */
    void InstallRoutes(Ipv4Address dst, const std::vector<std::pair<Ipv4Address, uint32_t>>& nextHops,
                       Time now)
    {
        auto& tab = m_q[dst];
        std::map<Ipv4Address, Entry> fresh;
        double z = 0.0;
        for (const auto& nh : nextHops)
            z += 1.0 / std::max<uint32_t>(nh.second, 1);
        for (const auto& nh : nextHops)
        {
            double h = std::max<uint32_t>(nh.second, 1);
            double q0 = m_p.neighbourBootstrap ? -m_p.hcPriorCost * h : (1.0 / h) / z;
            auto old = tab.find(nh.first);
            if (m_p.keepQOnReinstall && old != tab.end())
                q0 = old->second.q;
            fresh[nh.first] = Entry{nh.second, q0};
        }
        tab.swap(fresh);
        m_seq.push_back(now); // one destination-sequence update seen by this node
    }

    /* [HOOK 2] link break to nextHop (MAC retries exhausted) or RERR received from it */
    void RemoveNextHop(Ipv4Address dst, Ipv4Address nextHop, Time now, bool markDeadEnd = true)
    {
        auto it = m_q.find(dst);
        if (it != m_q.end())
            it->second.erase(nextHop);
        if (markDeadEnd)
            m_nb[nextHop][dst] = NbValue{-m_p.vFail, now};
        m_seq.push_back(now);
        if (m_p.adaptiveEpsilon)
            m_eps = std::min(m_p.epsMax, m_eps + m_p.epsBump);
    }

    bool HasRoute(Ipv4Address dst) const
    {
        auto it = m_q.find(dst);
        return it != m_q.end() && !it->second.empty();
    }

    /* [HOOK 3] choose the next hop for a data packet (epsilon-greedy on Q).
     * prevHop = the neighbour the packet came from (Ipv4Address() at the source).
     * Returns Ipv4Address() (0.0.0.0) when there is no usable candidate.        */
    Ipv4Address Select(Ipv4Address dst, Ipv4Address prevHop, Ptr<UniformRandomVariable> rng) const
    {
        auto it = m_q.find(dst);
        if (it == m_q.end())
            return Ipv4Address();
        std::vector<std::pair<Ipv4Address, double>> c;
        for (const auto& kv : it->second)
            if (kv.first != prevHop)
                c.emplace_back(kv.first, kv.second.q);
        if (c.empty())
            return Ipv4Address();
        if (rng->GetValue(0.0, 1.0) < m_eps)
            return c[rng->GetInteger(0, c.size() - 1)].first;
        double best = -std::numeric_limits<double>::infinity();
        for (const auto& x : c)
            best = std::max(best, x.second);
        std::vector<Ipv4Address> ties;
        for (const auto& x : c)
            if (x.second >= best - 1e-12)
                ties.push_back(x.first);
        return ties[rng->GetInteger(0, ties.size() - 1)];
    }

    /* [HOOK 4] MAC feedback after one transmission attempt series to nextHop.
     *   ack          : MAC ACK received (true) or retries exhausted (false)
     *   delay        : one-hop service time in seconds (MAC enqueue -> ACK / drop)
     *   nhIsDst      : nextHop is the destination itself
     *   nhEnergy     : residual-energy fraction of nextHop (1.0 if unknown)
     *   ownEnergy    : residual-energy fraction of this node                     */
    void OnFeedback(Ipv4Address dst, Ipv4Address nextHop, bool ack, double delay, bool nhIsDst,
                    double nhEnergy, double ownEnergy, Time now)
    {
        auto it = m_q.find(dst);
        if (it == m_q.end())
            return;
        auto e = it->second.find(nextHop);
        if (e == it->second.end())
            return;

        // ---- learning rate
        double alpha = m_p.alphaFixed;
        if (m_p.adaptiveAlpha)
        {
            while (!m_seq.empty() && m_seq.front() < now - m_p.seqWindow)
                m_seq.pop_front();
            alpha = 0.1 + 0.8 * (1.0 - std::exp(-m_p.lambda * double(m_seq.size())));
        }

        // ---- context EWMAs
        double a = ack ? 1.0 : 0.0;
        m_ackEwma = (1 - m_p.ewma) * m_ackEwma + m_p.ewma * a;
        if (!m_haveDelay)
        {
            m_dlyEwma = m_dlyFloor = delay;
            m_haveDelay = true;
        }
        else
        {
            m_dlyEwma = (1 - m_p.ewma) * m_dlyEwma + m_p.ewma * delay;
            m_dlyFloor = std::min(delay, 0.995 * m_dlyFloor + 0.005 * delay);
        }

        // ---- reward
        double dTerm = 1.0 / (1.0 + delay / m_p.dRef);
        double r;
        if (m_p.adaptiveReward)
        {
            double w1, w2, w3;
            if (ownEnergy < m_p.lowEnergy || nhEnergy < m_p.lowEnergy)
            { w1 = 0.1; w2 = 0.1; w3 = 0.8; m_regime = 3; }
            else if (m_ackEwma < m_p.ackThr)
            { w1 = 0.7; w2 = 0.2; w3 = 0.1; m_regime = 1; }
            else if (m_dlyEwma > m_p.congFactor * m_dlyFloor)
            { w1 = 0.3; w2 = 0.6; w3 = 0.1; m_regime = 2; }
            else
            { w1 = 0.5; w2 = 0.4; w3 = 0.1; m_regime = 0; }
            r = w1 * a + w2 * dTerm + w3 * nhEnergy;
        }
        else
        {
            r = 0.6 * a + 0.4 * dTerm;
        }

        // ---- target
        double& q = e->second.q;
        double target;
        if (m_p.neighbourBootstrap)
        {
            double vu;
            if (nhIsDst)
                vu = 0.0;
            else if (!ack)
                vu = q; // no fresh information from the neighbour
            else
                vu = NeighbourValue(nextHop, dst, now, q);
            target = -(1.0 - r) + m_p.gammaNb * vu;
        }
        else
        {
            double mx = -std::numeric_limits<double>::infinity();
            for (const auto& kv : it->second)
                mx = std::max(mx, kv.second.q);
            target = r + m_p.gammaLocal * mx;
        }
        q = (1.0 - alpha) * q + alpha * target;
        m_lastAlpha = alpha;
    }

    /* [HOOK 5] value this node advertises for dst (put it in QValueTag).
     * isDestination = this node IS dst (e.g. the base station) -> 0.            */
    double AdvertisedValue(Ipv4Address dst, bool isDestination) const
    {
        if (isDestination)
            return 0.0;
        auto it = m_q.find(dst);
        if (it == m_q.end() || it->second.empty())
            return -m_p.vFail;
        double mx = -std::numeric_limits<double>::infinity();
        for (const auto& kv : it->second)
            mx = std::max(mx, kv.second.q);
        return mx;
    }

    /* [HOOK 6] a QValueTag was received from neighbour `from` */
    void OnNeighbourValue(Ipv4Address from, Ipv4Address dst, double v, Time now)
    {
        m_nb[from][dst] = NbValue{v, now};
    }

    /* [HOOK 7] periodic epsilon decay; schedule every EpsilonPeriod() */
    void DecayEpsilon()
    {
        if (m_p.adaptiveEpsilon)
            m_eps = std::max(m_p.epsMin, m_eps - m_p.epsStep);
        else
            m_eps = std::max(0.0, m_eps - m_p.epsStep);
    }
    Time EpsilonPeriod() const { return m_p.adaptiveEpsilon ? m_p.epsPeriodAdaptive : m_p.epsPeriodFixed; }

    // ---- inspection / logging
    double GetEpsilon() const { return m_eps; }
    double GetLastAlpha() const { return m_lastAlpha; }
    int GetRegime() const { return m_regime; } // 0 normal, 1 lossy, 2 congestion, 3 low energy
    const std::map<Ipv4Address, Entry>* GetTable(Ipv4Address dst) const
    {
        auto it = m_q.find(dst);
        return it == m_q.end() ? nullptr : &it->second;
    }
    void Print(std::ostream& os, Ipv4Address dst) const
    {
        auto t = GetTable(dst);
        os << "eps=" << m_eps << " alpha=" << m_lastAlpha << " regime=" << m_regime << " |";
        if (t)
            for (const auto& kv : *t)
                os << " " << kv.first << "(HC=" << kv.second.hops << ",Q=" << kv.second.q << ")";
        os << "\n";
    }

  private:
    struct NbValue
    {
        double v;
        Time t;
    };
    double NeighbourValue(Ipv4Address nb, Ipv4Address dst, Time now, double fallback) const
    {
        auto a = m_nb.find(nb);
        if (a == m_nb.end())
            return fallback;
        auto b = a->second.find(dst);
        if (b == a->second.end() || now - b->second.t > m_p.nbValueTtl)
            return fallback;
        return b->second.v;
    }

    Params m_p;
    double m_eps;
    std::map<Ipv4Address, std::map<Ipv4Address, Entry>> m_q;     // dst -> next hop -> entry
    std::map<Ipv4Address, std::map<Ipv4Address, NbValue>> m_nb;  // neighbour -> dst -> V
    std::deque<Time> m_seq;
    double m_ackEwma = 1.0, m_dlyEwma = 0.0, m_dlyFloor = 0.0, m_lastAlpha = 0.5;
    bool m_haveDelay = false;
    int m_regime = 0;
};

} // namespace nbq
} // namespace ns3

#endif // NBQMAODV_NBQ_LEARNING_H
