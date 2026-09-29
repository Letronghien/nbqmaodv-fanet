/*
 * fanet-core.h -- STEP11: common body of every fanet-scenario-<module>.cc.
 * A scenario file only includes its routing module, defines MakeRouting() and calls FanetMain().
 *
 * Output (stdout):
 *   "# METRICS k=v ..."  extra metrics (always; before the CSV line)
 *   CSV (14 fields, unchanged): protocol,nUav,vmax,rate,run,tx,rx,pdr,delay_ms,thr_kbps,ctrl,nrl,
 *                               depleted,firstDepletion
 * With --warmup=W > 0 every traffic metric (CSV and METRICS) covers [W, simTime] only.
 * With default arguments the results are identical to the Step-10c scenarios.
 */
#ifndef FANET_CORE_H
#define FANET_CORE_H

#include "fanet-channel.h"

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/energy-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <utility>
#include <vector>

using namespace ns3;

// ---------- routing-control counter: every IPv4 transmission of an AODV-family packet (UDP 654)
static uint64_t g_ctrlTx = 0;
static uint64_t g_ctrlByType[5] = {0, 0, 0, 0, 0}; // STEP11: [1]=RREQ [2]=RREP/HELLO [3]=RERR [4]=RREP-ACK
static const uint16_t AODV_PORT = 654;

static void
Ipv4TxTrace(Ptr<const Packet> p, Ptr<Ipv4>, uint32_t)
{
    Ptr<Packet> c = p->Copy();
    Ipv4Header ip;
    if (c->RemoveHeader(ip) == 0 || ip.GetProtocol() != UdpL4Protocol::PROT_NUMBER)
        return;
    UdpHeader udp;
    c->RemoveHeader(udp);
    if (udp.GetDestinationPort() == AODV_PORT || udp.GetSourcePort() == AODV_PORT)
    {
        g_ctrlTx++;
        uint8_t type = 0; // STEP11: first byte = AODV TypeHeader
        if (c->GetSize() >= 1)
            c->CopyData(&type, 1);
        if (type >= 1 && type <= 4)
            g_ctrlByType[type]++;
    }
}

// ---------- routing attributes: "Name=Value;Name2=Value2" -> helper.Set(Name, StringValue(Value))
using AttrList = std::vector<std::pair<std::string, std::string>>;

static AttrList
ParseAttrs(const std::string& s)
{
    AttrList out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ';'))
    {
        auto eq = item.find('=');
        if (eq != std::string::npos && eq > 0)
            out.emplace_back(item.substr(0, eq), item.substr(eq + 1));
    }
    return out;
}

template <class H>
static std::unique_ptr<Ipv4RoutingHelper>
Make(const AttrList& attrs)
{
    auto h = std::make_unique<H>();
    for (const auto& kv : attrs)
        h->Set(kv.first, StringValue(kv.second));
    return h;
}

using RoutingFactory = std::function<std::unique_ptr<Ipv4RoutingHelper>(const std::string&, const AttrList&)>;

// ---------- STEP11: per-UAV application counters (packets generated after a UAV died)
static std::vector<Ptr<UdpClient>> g_clients;
static std::vector<uint64_t> g_txBytesAtDeath;   // UdpClient::GetTotalTx() when the UAV died
static std::vector<uint64_t> g_txBytesAtWarmup;  // ... at the end of the warm-up
// ---------- STEP8: energy bookkeeping (UAV counted as depleted at the BasicEnergySource
// low-battery threshold, where the WifiRadioEnergyModel switches the PHY off)
static std::vector<Ptr<energy::BasicEnergySource>> g_sources;
static std::vector<bool> g_depleted;
static uint32_t g_nDepleted = 0;
static double g_firstDepletion = -1.0;
static double g_lowThreshold = 0.10;
static double g_sumFracAtDeath = 0.0; // STEP8c: battery fraction when each UAV died
static std::vector<bool> g_phyOffDone;  // STEP8e: PHY actually switched off

// STEP8e: the energy source must not call WifiPhy::SetOffMode() directly: in ns-3.48 this can
// happen in the middle of a reception, and the pending reception event then aborts with
// "Invalid WifiPhy state OFF". PollEnergy() switches the PHY off safely instead.
static void
NoOpDepletion()
{
}
// ---------- STEP8b: energy diagnostics (--energyDebug=1)
static energy::DeviceEnergyModelContainer g_models;
static NetDeviceContainer g_uavDev;

static void
EnergyReport()
{
    double t = Simulator::Now().GetSeconds();
    double sumFrac = 0.0, sumRadio = 0.0;
    uint32_t nOff = 0;
    for (uint32_t i = 0; i < g_models.GetN(); ++i)
    {
        Ptr<energy::BasicEnergySource> src = g_sources[i];
        Ptr<WifiRadioEnergyModel> m = DynamicCast<WifiRadioEnergyModel>(g_models.Get(i));
        Ptr<WifiNetDevice> wd = DynamicCast<WifiNetDevice>(g_uavDev.Get(i));
        double remain = src->GetRemainingEnergy();
        double radioJ = m ? m->GetTotalEnergyConsumption() : -1.0;
        bool off = wd && wd->GetPhy() && wd->GetPhy()->IsStateOff();
        sumFrac += remain / src->GetInitialEnergy();
        sumRadio += radioJ;
        nOff += off ? 1 : 0;
        if (i < 3)
        {
            std::cout << "# ENERGY t=" << t << " uav=" << i << " init=" << src->GetInitialEnergy()
                      << " remainJ=" << remain << " radioJ=" << radioJ
                      << " currentA=" << (m ? m->GetCurrentA() : -1.0)
                      << " state=" << (m ? static_cast<int>(m->GetCurrentState()) : -1)
                      << " phyOff=" << off << std::endl;
        }
    }
    std::cout << "# ENERGY t=" << t << " ALL avgRemainFrac=" << sumFrac / g_models.GetN()
              << " totalRadioJ=" << sumRadio << " phyOffCount=" << nOff
              << " depletedCount=" << g_nDepleted << " avgFracAtDeath="
              << (g_nDepleted ? g_sumFracAtDeath / g_nDepleted : -1.0) << std::endl;
}

static void
PeriodicEnergyReport(double period)
{
    EnergyReport();
    Simulator::Schedule(Seconds(period), &PeriodicEnergyReport, period);
}

static void
PollEnergy(double period)
{
    // STEP8c/8e: a UAV dies when its battery reaches the low-battery threshold (or, with
    // --nsPredictiveOff=1, when ns-3's energy model switches itself to OFF). Death is counted
    // at that instant; the real PHY is switched off at the first poll where it is IDLE, so no
    // transmission/reception is interrupted half-way (avoids an ns-3.48 abort).
    for (size_t i = 0; i < g_sources.size(); ++i)
    {
        Ptr<WifiNetDevice> wd = (i < g_uavDev.GetN()) ? DynamicCast<WifiNetDevice>(g_uavDev.Get(i)) : nullptr;
        if (!g_depleted[i])
        {
            double frac = g_sources[i]->GetRemainingEnergy() / g_sources[i]->GetInitialEnergy();
            Ptr<WifiRadioEnergyModel> m =
                (i < g_models.GetN()) ? DynamicCast<WifiRadioEnergyModel>(g_models.Get(i)) : nullptr;
            bool modelOff = m && m->GetCurrentState() == WifiPhyState::OFF;
            if (modelOff || frac <= g_lowThreshold + 1e-9)
            {
                if (i < g_clients.size() && g_clients[i])
                    g_txBytesAtDeath[i] = g_clients[i]->GetTotalTx(); // STEP11
                g_depleted[i] = true;
                ++g_nDepleted;
                g_sumFracAtDeath += frac;
                if (g_firstDepletion < 0)
                    g_firstDepletion = Simulator::Now().GetSeconds();
            }
        }
        if (g_depleted[i] && !g_phyOffDone[i] && wd && wd->GetPhy())
        {
            Ptr<WifiPhy> phy = wd->GetPhy();
            if (phy->IsStateOff())
                g_phyOffDone[i] = true;
            else if (phy->IsStateIdle())
            {
                phy->SetOffMode();
                g_phyOffDone[i] = true;
            }
        }
    }
    Simulator::Schedule(Seconds(period), &PollEnergy, period);
}


// ---------- STEP11: MAC outcome of data frames (local indicator for adaptive selection)
static uint64_t g_macAcked = 0, g_macDropped = 0;

static void
MacAcked(Ptr<const WifiMpdu> mpdu)
{
    if (mpdu && mpdu->GetHeader().IsData())
        ++g_macAcked;
}

static void
MacDropped(WifiMacDropReason, Ptr<const WifiMpdu> mpdu)
{
    if (mpdu && mpdu->GetHeader().IsData())
        ++g_macDropped;
}

// ---------- STEP11: periodic samples after the warm-up (neighbours within nominal range, MAC queue)
static NodeContainer g_uavNodes;
static NetDeviceContainer g_allUavDev;
static double g_nominalRange = 250.0;
static double g_sumNeighbours = 0.0, g_sumQueue = 0.0;
static uint64_t g_nNbSamples = 0, g_nQSamples = 0;

static bool
UavAlive(uint32_t i)
{
    return g_depleted.empty() || i >= g_depleted.size() || !g_depleted[i];
}

static void
SampleLocalState(double period)
{
    uint32_t n = g_uavNodes.GetN();
    for (uint32_t i = 0; i < n; ++i)
    {
        if (!UavAlive(i))
            continue;
        Vector pi = g_uavNodes.Get(i)->GetObject<MobilityModel>()->GetPosition();
        uint32_t deg = 0;
        for (uint32_t j = 0; j < n; ++j)
        {
            if (j == i || !UavAlive(j))
                continue;
            Vector pj = g_uavNodes.Get(j)->GetObject<MobilityModel>()->GetPosition();
            if (CalculateDistance(pi, pj) <= g_nominalRange)
                ++deg;
        }
        g_sumNeighbours += deg;
        ++g_nNbSamples;
        Ptr<WifiNetDevice> wd = DynamicCast<WifiNetDevice>(g_allUavDev.Get(i));
        if (wd && wd->GetMac() && wd->GetMac()->GetTxop())
        {
            g_sumQueue += wd->GetMac()->GetTxop()->GetWifiMacQueue()->GetNPackets();
            ++g_nQSamples;
        }
    }
    Simulator::Schedule(Seconds(period), &SampleLocalState, period);
}

// ---------- STEP11: warm-up snapshot of every cumulative counter
struct FlowSnap
{
    uint64_t tx = 0, rx = 0, rxBytes = 0;
    double delaySum = 0.0;
    std::vector<uint32_t> hist; // delay histogram bin counts (1 ms bins)
};

static std::map<FlowId, FlowSnap> g_warmFlows;
static uint64_t g_warmCtrl = 0, g_warmCtrlType[5] = {0, 0, 0, 0, 0}, g_warmAcked = 0, g_warmDropped = 0;

static void
TakeWarmupSnapshot(Ptr<FlowMonitor> fm)
{
    fm->CheckForLostPackets();
    for (const auto& kv : fm->GetFlowStats())
    {
        FlowSnap s;
        s.tx = kv.second.txPackets;
        s.rx = kv.second.rxPackets;
        s.rxBytes = kv.second.rxBytes;
        s.delaySum = kv.second.delaySum.GetSeconds();
        for (uint32_t b = 0; b < kv.second.delayHistogram.GetNBins(); ++b)
            s.hist.push_back(kv.second.delayHistogram.GetBinCount(b));
        g_warmFlows[kv.first] = s;
    }
    g_warmCtrl = g_ctrlTx;
    for (int k = 0; k < 5; ++k)
        g_warmCtrlType[k] = g_ctrlByType[k];
    g_warmAcked = g_macAcked;
    g_warmDropped = g_macDropped;
    for (uint32_t i = 0; i < g_clients.size(); ++i)
        g_txBytesAtWarmup[i] = g_clients[i]->GetTotalTx();
}

// ---------- STEP11: optional cumulative report every W seconds (stationarity check)
static Ptr<FlowMonitor> g_fm;
static Ipv4Address g_bsAddr;

static void
WindowReport(double period)
{
    g_fm->CheckForLostPackets();
    uint64_t tx = 0, rx = 0;
    for (const auto& kv : g_fm->GetFlowStats())
    {
        tx += kv.second.txPackets;
        rx += kv.second.rxPackets;
    }
    std::cout << "# WIN t=" << Simulator::Now().GetSeconds() << " tx=" << tx << " rx=" << rx
              << " ctrl=" << g_ctrlTx << std::endl;
    Simulator::Schedule(Seconds(period), &WindowReport, period);
}

static double
Percentile(const std::vector<std::pair<double, uint64_t>>& bins, double q)
{
    uint64_t total = 0;
    for (const auto& b : bins)
        total += b.second;
    if (total == 0)
        return 0.0;
    uint64_t target = static_cast<uint64_t>(std::ceil(q * total));
    uint64_t acc = 0;
    for (const auto& b : bins)
    {
        acc += b.second;
        if (acc >= target)
            return b.first;
    }
    return bins.back().first;
}

// ============================================================================================
int
FanetMain(int argc, char* argv[], const std::string& defaultProto, const RoutingFactory& makeRouting)
{
    std::string proto = defaultProto;
    uint32_t nUav = 20, run = 1;
    double area = 1000.0, range = 250.0, vmin = 5.0, vmax = 20.0;
    double rate = 4.0, simTime = 200.0;
    double energyJ = 0.0; // STEP8: 0 = no energy model
    bool energyDebug = false; // STEP8b
    bool nsPredictiveOff = false; // STEP8d: true = original ns-3 predictive switch-to-OFF
    uint32_t pktSize = 512;
    std::string routingAttrs = "";
    // STEP11
    std::string mobility = "rwp";  // rwp | gm
    double gmAlpha = 0.85, zMin = 80.0, zMax = 120.0;
    std::string bsPos = "center";  // center | edge
    double energyRandMin = 1.0;    // initial energy = energyJ * U[energyRandMin, 1]
    double warmup = 0.0;           // traffic metrics cover [warmup, simTime]
    double windowReport = 0.0;     // print cumulative counters every W s (0 = off)

    CommandLine cmd(__FILE__);
    cmd.AddValue("protocol", "AODV|PMAODV|QMAODV|SA-QMAODV|NBQ-MAODV (depends on the module)", proto);
    cmd.AddValue("nUav", "number of UAVs", nUav);
    cmd.AddValue("run", "RNG run number (seed)", run);
    cmd.AddValue("area", "side of the square area (m)", area);
    cmd.AddValue("range", "radio range (m)", range);
    FanetChannelConfig chCfg; // STEP10c
    AddFanetChannelArgs(cmd, chCfg);
    cmd.AddValue("vmin", "min speed (m/s)", vmin);
    cmd.AddValue("vmax", "max speed (m/s)", vmax);
    cmd.AddValue("rate", "packets/s per UAV", rate);
    cmd.AddValue("pktSize", "payload bytes", pktSize);
    cmd.AddValue("simTime", "simulation time (s)", simTime);
    cmd.AddValue("energyJ", "initial energy per UAV in J (0 = no energy model)", energyJ);
    cmd.AddValue("nsPredictiveOff",
                 "STEP8d: keep ns-3's predictive switch-to-OFF of WifiRadioEnergyModel "
                 "(needs the ns3-patches/wifi-radio-energy-model patch)",
                 nsPredictiveOff);
    cmd.AddValue("energyDebug", "STEP8b: print energy diagnostics every 10 s and at the end", energyDebug);
    cmd.AddValue("routingAttrs", "routing attributes, e.g. \"MaxPaths=3;AdaptiveEpsilon=false\"", routingAttrs);
    cmd.AddValue("mobility", "STEP11: rwp (random waypoint, 2-D) or gm (Gauss-Markov, 3-D)", mobility);
    cmd.AddValue("gmAlpha", "STEP11: Gauss-Markov memory alpha", gmAlpha);
    cmd.AddValue("zMin", "STEP11: gm minimum altitude (m)", zMin);
    cmd.AddValue("zMax", "STEP11: gm maximum altitude (m)", zMax);
    cmd.AddValue("bsPos", "STEP11: base station at the area centre or at the middle of an edge", bsPos);
    cmd.AddValue("energyRandMin", "STEP11: initial energy = energyJ * U[energyRandMin, 1]", energyRandMin);
    cmd.AddValue("warmup", "STEP11: traffic metrics cover [warmup, simTime] (s)", warmup);
    cmd.AddValue("windowReport", "STEP11: print cumulative tx/rx every W s (0 = off)", windowReport);
    cmd.Parse(argc, argv);
    NS_ABORT_MSG_IF(mobility != "rwp" && mobility != "gm", "mobility must be rwp or gm");
    NS_ABORT_MSG_IF(bsPos != "center" && bsPos != "edge", "bsPos must be center or edge");
    NS_ABORT_MSG_IF(warmup < 0 || warmup >= simTime, "warmup must be in [0, simTime)");

    RngSeedManager::SetSeed(12345);
    RngSeedManager::SetRun(run);

    NodeContainer uavs, bs, all;
    uavs.Create(nUav);
    bs.Create(1);
    all.Add(uavs);
    all.Add(bs);
    g_uavNodes = uavs;

    // ---------- mobility (common random numbers: fixed stream indices)
    std::ostringstream u;
    u << "ns3::UniformRandomVariable[Min=0.0|Max=" << area << "]";
    std::ostringstream sp;
    sp << "ns3::UniformRandomVariable[Min=" << vmin << "|Max=" << vmax << "]";
    MobilityHelper mob;
    if (mobility == "rwp")
    {
        ObjectFactory pf;
        pf.SetTypeId("ns3::RandomRectanglePositionAllocator");
        pf.Set("X", StringValue(u.str()));
        pf.Set("Y", StringValue(u.str()));
        Ptr<PositionAllocator> pa = pf.Create()->GetObject<PositionAllocator>();
        pa->AssignStreams(1000);
        mob.SetPositionAllocator(pa);
        mob.SetMobilityModel("ns3::RandomWaypointMobilityModel",
                             "Speed", StringValue(sp.str()),
                             "Pause", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"),
                             "PositionAllocator", PointerValue(pa));
    }
    else
    {
        // STEP11: Gauss-Markov, 3-D box [0,area]^2 x [zMin,zMax], reflecting borders
        std::ostringstream z;
        z << "ns3::UniformRandomVariable[Min=" << zMin << "|Max=" << zMax << "]";
        ObjectFactory pf;
        pf.SetTypeId("ns3::RandomBoxPositionAllocator");
        pf.Set("X", StringValue(u.str()));
        pf.Set("Y", StringValue(u.str()));
        pf.Set("Z", StringValue(z.str()));
        Ptr<PositionAllocator> pa = pf.Create()->GetObject<PositionAllocator>();
        pa->AssignStreams(1000);
        mob.SetPositionAllocator(pa);
        mob.SetMobilityModel("ns3::GaussMarkovMobilityModel",
                             "Bounds", BoxValue(Box(0, area, 0, area, zMin, zMax)),
                             "TimeStep", TimeValue(Seconds(1.0)),
                             "Alpha", DoubleValue(gmAlpha),
                             "MeanVelocity", StringValue(sp.str()),
                             "MeanDirection", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=6.283185307]"),
                             "MeanPitch", StringValue("ns3::UniformRandomVariable[Min=-0.05|Max=0.05]"),
                             "NormalVelocity", StringValue("ns3::NormalRandomVariable[Mean=0.0|Variance=4.0|Bound=8.0]"),
                             "NormalDirection", StringValue("ns3::NormalRandomVariable[Mean=0.0|Variance=0.2|Bound=1.0]"),
                             "NormalPitch", StringValue("ns3::NormalRandomVariable[Mean=0.0|Variance=0.02|Bound=0.3]"));
    }
    mob.Install(uavs);
    mob.AssignStreams(uavs, 2000);
    MobilityHelper fixed;
    fixed.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    fixed.Install(bs);
    Vector bsXyz = (bsPos == "center") ? Vector(area / 2, area / 2, 0) : Vector(area / 2, 0, 0);
    bs.Get(0)->GetObject<MobilityModel>()->SetPosition(bsXyz);

    // ---------- 802.11b ad hoc, 2 Mbit/s
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode", StringValue("DsssRate2Mbps"),
                                 "ControlMode", StringValue("DsssRate1Mbps"));
    YansWifiChannelHelper ch;
    YansWifiPhyHelper phy;
    chCfg.range = range;
    ConfigureFanetChannel(ch, phy, chCfg); // STEP10c: --channel=range (default) | fading
    phy.SetChannel(ch.Create());
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");
    NetDeviceContainer dev = wifi.Install(phy, mac, all);
    for (uint32_t i = 0; i < nUav; ++i)
        g_allUavDev.Add(dev.Get(i));
    g_nominalRange = range;

    // ---------- STEP8: battery + 802.11 radio energy model on every UAV (not on the base station)
    if (energyJ > 0.0)
    {
        BasicEnergySourceHelper batt;
        batt.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(energyJ));
        batt.Set("BasicEnergyLowBatteryThreshold", DoubleValue(g_lowThreshold));
        energy::EnergySourceContainer sources = batt.Install(uavs);
        if (energyRandMin < 1.0)
        {
            // STEP11: heterogeneous batteries, same draw for every protocol (stream 4000)
            Ptr<UniformRandomVariable> er = CreateObject<UniformRandomVariable>();
            er->SetStream(4000);
            for (uint32_t i = 0; i < sources.GetN(); ++i)
                DynamicCast<energy::BasicEnergySource>(sources.Get(i))
                    ->SetInitialEnergy(energyJ * er->GetValue(energyRandMin, 1.0));
        }
        NetDeviceContainer uavDev;
        for (uint32_t i = 0; i < nUav; ++i)
            uavDev.Add(dev.Get(i));
        WifiRadioEnergyModelHelper radio; // depletion -> WifiPhy::SetOffMode
        // STEP8d: depletion decided by the battery low threshold only (see ns3-patches/)
        radio.Set("PredictiveSwitchToOff", BooleanValue(nsPredictiveOff));
        radio.SetDepletionCallback(MakeCallback(&NoOpDepletion)); // STEP8e
        g_models = radio.Install(uavDev, sources); // STEP8b: keep for diagnostics
        g_uavDev = uavDev;
        if (energyDebug)
            Simulator::Schedule(Seconds(10.0), &PeriodicEnergyReport, 10.0);
        for (uint32_t i = 0; i < sources.GetN(); ++i)
            g_sources.push_back(DynamicCast<energy::BasicEnergySource>(sources.Get(i)));
        g_depleted.assign(g_sources.size(), false);
        g_phyOffDone.assign(g_sources.size(), false); // STEP8e
        Simulator::Schedule(Seconds(0.1), &PollEnergy, 0.1); // STEP8c: 0.1 s
    }

    // ---------- routing + IP
    auto routing = makeRouting(proto, ParseAttrs(routingAttrs));
    InternetStackHelper stack;
    stack.SetRoutingHelper(*routing);
    stack.Install(all);
    Ipv4AddressHelper addr("10.1.0.0", "255.255.0.0");
    Ipv4InterfaceContainer ifs = addr.Assign(dev);
    Ipv4Address bsAddr = ifs.GetAddress(nUav);
    g_bsAddr = bsAddr;

    // ---------- traffic: every UAV -> base station, CBR over UDP
    const uint16_t port = 9;
    UdpServerHelper server(port);
    ApplicationContainer sa = server.Install(bs.Get(0));
    sa.Start(Seconds(0.0));
    sa.Stop(Seconds(simTime));
    Ptr<UniformRandomVariable> st = CreateObject<UniformRandomVariable>();
    st->SetStream(3000);
    for (uint32_t i = 0; i < nUav; ++i)
    {
        UdpClientHelper client(bsAddr, port);
        client.SetAttribute("Interval", TimeValue(Seconds(1.0 / rate)));
        client.SetAttribute("PacketSize", UintegerValue(pktSize));
        client.SetAttribute("MaxPackets", UintegerValue(4294967295u));
        ApplicationContainer ca = client.Install(uavs.Get(i));
        ca.Start(Seconds(1.0 + st->GetValue(0.0, 1.0 / rate)));
        ca.Stop(Seconds(simTime));
        g_clients.push_back(DynamicCast<UdpClient>(ca.Get(0))); // STEP11
    }
    g_txBytesAtDeath.assign(nUav, 0);
    g_txBytesAtWarmup.assign(nUav, 0);

    Config::ConnectWithoutContext("/NodeList/*/$ns3::Ipv4L3Protocol/Tx", MakeCallback(&Ipv4TxTrace));
    // STEP11: MAC outcome of every data frame (read-only)
    Config::ConnectWithoutContext("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/AckedMpdu",
                                  MakeCallback(&MacAcked));
    Config::ConnectWithoutContext("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/DroppedMpdu",
                                  MakeCallback(&MacDropped));

    FlowMonitorHelper fmh;
    Ptr<FlowMonitor> fm = fmh.InstallAll();
    g_fm = fm;
    if (warmup > 0.0)
        Simulator::Schedule(Seconds(warmup), &TakeWarmupSnapshot, fm);
    Simulator::Schedule(Seconds(std::max(warmup, 1.0)), &SampleLocalState, 1.0);
    if (windowReport > 0.0)
        Simulator::Schedule(Seconds(windowReport), &WindowReport, windowReport);

    Simulator::Stop(Seconds(simTime + 1.0));
    Simulator::Run();
    if (energyDebug && g_models.GetN() > 0)
        EnergyReport(); // STEP8b: final snapshot (printed before the CSV line)

    // ---------- metrics (data flows towards the base station only), minus the warm-up snapshot
    fm->CheckForLostPackets();
    auto cls = DynamicCast<Ipv4FlowClassifier>(fmh.GetClassifier());
    uint64_t tx = 0, rx = 0, rxBytes = 0;
    double delaySum = 0.0;
    std::map<uint32_t, uint64_t> hist; // 1-ms bin index -> packets
    for (const auto& kv : fm->GetFlowStats())
    {
        Ipv4FlowClassifier::FiveTuple t = cls->FindFlow(kv.first);
        if (t.destinationAddress != bsAddr || t.destinationPort != port)
            continue;
        FlowSnap w;
        auto it = g_warmFlows.find(kv.first);
        if (it != g_warmFlows.end())
            w = it->second;
        tx += kv.second.txPackets - w.tx;
        rx += kv.second.rxPackets - w.rx;
        rxBytes += kv.second.rxBytes - w.rxBytes;
        delaySum += kv.second.delaySum.GetSeconds() - w.delaySum;
        const Histogram& h = kv.second.delayHistogram;
        for (uint32_t b = 0; b < h.GetNBins(); ++b)
        {
            uint64_t c = h.GetBinCount(b) - (b < w.hist.size() ? w.hist[b] : 0);
            if (c > 0)
                hist[b] += c;
        }
    }
    double measured = simTime - warmup;
    uint64_t ctrl = g_ctrlTx - g_warmCtrl;
    double pdr = tx ? 100.0 * rx / tx : 0.0;
    double delayMs = rx ? 1000.0 * delaySum / rx : 0.0;
    double thr = rxBytes * 8.0 / measured / 1000.0;
    double nrl = rx ? double(ctrl) / rx : 0.0;

    // STEP11: delay percentiles (1-ms bins), app-level counts and PDR of live UAVs only
    std::vector<std::pair<double, uint64_t>> bins;
    for (const auto& kv : hist)
        bins.emplace_back((kv.first + 0.5) * 1.0, kv.second); // bin centre in ms (DelayBinWidth 1 ms)
    uint64_t txApp = 0, txAlive = 0;
    for (uint32_t i = 0; i < g_clients.size(); ++i)
    {
        uint64_t end = g_clients[i]->GetTotalTx();
        uint64_t start = (warmup > 0.0) ? g_txBytesAtWarmup[i] : 0;
        bool dead = !g_depleted.empty() && i < g_depleted.size() && g_depleted[i];
        uint64_t aliveEnd = dead ? std::max(start, std::min(end, g_txBytesAtDeath[i])) : end;
        txApp += (end - start) / pktSize;
        txAlive += (aliveEnd - start) / pktSize;
    }
    uint64_t acked = g_macAcked - g_warmAcked, dropped = g_macDropped - g_warmDropped;
    std::cout << "# METRICS warmup=" << warmup << " mobility=" << mobility << " channel=" << chCfg.channel
              << " bsPos=" << bsPos << " txApp=" << txApp << " txAlive=" << txAlive
              << " pdrAlive=" << (txAlive ? 100.0 * rx / txAlive : 0.0)
              << " delayMedMs=" << Percentile(bins, 0.5) << " delayP95Ms=" << Percentile(bins, 0.95)
              << " rreq=" << g_ctrlByType[1] - g_warmCtrlType[1] << " rrep=" << g_ctrlByType[2] - g_warmCtrlType[2]
              << " rerr=" << g_ctrlByType[3] - g_warmCtrlType[3] << " macAcked=" << acked
              << " macDropped=" << dropped
              << " macAckRatio=" << (acked + dropped ? double(acked) / (acked + dropped) : 0.0)
              << " avgNeighbours=" << (g_nNbSamples ? g_sumNeighbours / g_nNbSamples : 0.0)
              << " avgMacQueue=" << (g_nQSamples ? g_sumQueue / g_nQSamples : 0.0) << std::endl;

    std::cout << proto << "," << nUav << "," << vmax << "," << rate << "," << run << "," << tx << ","
              << rx << "," << pdr << "," << delayMs << "," << thr << "," << ctrl << "," << nrl
              << "," << g_nDepleted << ","
              << (g_firstDepletion < 0 ? simTime : g_firstDepletion) // STEP8: 14 fields
              << std::endl;

    Simulator::Destroy();
    return 0;
}

#endif // FANET_CORE_H
