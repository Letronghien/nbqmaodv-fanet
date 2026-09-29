/*
 * fanet-linkcal.cc -- STEP10c: link-level calibration of the FANET channel.
 * Two static nodes at distance d; node 0 sends 512-byte UDP packets (unicast, MAC retries on)
 * to node 1 for `duration` seconds. For every d it prints
 *     d, frameSuccess (PHY frames received OK / data frames sent), appDelivery (after retries)
 * Usage:  ./ns3 run "fanet-linkcal --channel=fading --txPowerDbm=0"
 */
#include "fanet-channel.h"

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <iomanip>
#include <iostream>

using namespace ns3;

static uint64_t g_txFrames = 0;
static uint64_t g_rxOkFrames = 0;

static void
TxBegin(Ptr<const Packet> p, double)
{
    if (p->GetSize() > 400) // data frames only (ACK/ARP are small)
        ++g_txFrames;
}

static void
RxEnd(Ptr<const Packet> p)
{
    if (p->GetSize() > 400)
        ++g_rxOkFrames;
}

static void
RunOne(const FanetChannelConfig& cfg, double d, double duration, uint32_t run, double& frameSucc, double& appDel)
{
    RngSeedManager::SetSeed(12345);
    RngSeedManager::SetRun(run);
    g_txFrames = g_rxOkFrames = 0;

    NodeContainer n;
    n.Create(2);
    MobilityHelper mob;
    Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
    pos->Add(Vector(0, 0, 100));
    pos->Add(Vector(d, 0, 100));
    mob.SetPositionAllocator(pos);
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(n);

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode", StringValue("DsssRate2Mbps"),
                                 "ControlMode", StringValue("DsssRate1Mbps"));
    YansWifiChannelHelper ch;
    YansWifiPhyHelper phy;
    ConfigureFanetChannel(ch, phy, cfg);
    phy.SetChannel(ch.Create());
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");
    NetDeviceContainer dev = wifi.Install(phy, mac, n);

    InternetStackHelper stack;
    stack.Install(n);
    Ipv4AddressHelper addr("10.9.0.0", "255.255.255.0");
    Ipv4InterfaceContainer ifs = addr.Assign(dev);
    NeighborCacheHelper nch; // STEP11b: static ARP entries -> no ARP-failure artefacts
    nch.PopulateNeighborCache();

    UdpServerHelper srv(9);
    ApplicationContainer sa = srv.Install(n.Get(1));
    sa.Start(Seconds(0.0));
    UdpClientHelper cli(ifs.GetAddress(1), 9);
    cli.SetAttribute("Interval", TimeValue(Seconds(0.05)));
    cli.SetAttribute("PacketSize", UintegerValue(512));
    cli.SetAttribute("MaxPackets", UintegerValue(4294967295u));
    ApplicationContainer ca = cli.Install(n.Get(0));
    ca.Start(Seconds(1.0));
    ca.Stop(Seconds(1.0 + duration));

    Config::ConnectWithoutContext("/NodeList/0/DeviceList/0/$ns3::WifiNetDevice/Phy/PhyTxBegin",
                                  MakeCallback(&TxBegin));
    Config::ConnectWithoutContext("/NodeList/1/DeviceList/0/$ns3::WifiNetDevice/Phy/PhyRxEnd",
                                  MakeCallback(&RxEnd));
    Simulator::Stop(Seconds(duration + 2.0));
    Simulator::Run();
    uint64_t sent = DynamicCast<UdpClient>(ca.Get(0))->GetTotalTx() / 512;
    uint64_t recv = DynamicCast<UdpServer>(sa.Get(0))->GetReceived();
    frameSucc = g_txFrames ? double(g_rxOkFrames) / g_txFrames : 0.0;
    appDel = sent ? double(recv) / sent : 0.0;
    Simulator::Destroy();
}

int
main(int argc, char* argv[])
{
    FanetChannelConfig cfg;
    cfg.channel = "fading";
    double duration = 20.0, dMin = 25, dMax = 500, dStep = 25; // STEP11b: up to the 2*range cut
    uint32_t run = 1;
    CommandLine cmd(__FILE__);
    AddFanetChannelArgs(cmd, cfg);
    cmd.AddValue("range", "nominal range (m)", cfg.range);
    cmd.AddValue("duration", "seconds of traffic per distance", duration);
    cmd.AddValue("dMin", "first distance (m)", dMin);
    cmd.AddValue("dMax", "last distance (m)", dMax);
    cmd.AddValue("dStep", "distance step (m)", dStep);
    cmd.AddValue("run", "RNG run", run);
    cmd.Parse(argc, argv);

    std::cout << "# channel=" << cfg.channel << " nakagamiM=" << cfg.nakagamiM << " txPowerDbm=" << cfg.txPowerDbm << " plExp=" << cfg.plExp
              << " ccaDbm=" << cfg.ccaDbm << " range=" << cfg.range << std::endl;
    std::cout << "d_m,frameSuccess,appDelivery" << std::endl;
    for (double d = dMin; d <= dMax + 1e-9; d += dStep)
    {
        double fs, ad;
        RunOne(cfg, d, duration, run, fs, ad);
        std::cout << std::fixed << std::setprecision(0) << d << "," << std::setprecision(3) << fs << ","
                  << ad << std::endl;
    }
    return 0;
}
