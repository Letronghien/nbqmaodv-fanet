/*
 * fanet-channel.h -- STEP10c: channel configuration shared by all FANET scenarios.
 *
 *  channel=range  : original setup (no path loss; a link exists up to `range` metres).
 *  channel=fading : air-to-air channel with log-distance path loss (exponent plExp,
 *                   2.412 GHz reference loss at 1 m) + Nakagami-m fading
 *                   (m = 3 below 80 m, 2 between 80 and 200 m, 1.5 beyond), hard cut at 2*range.
 *                   Tx power, CCA and preamble-detection thresholds are set so that the
 *                   packet success probability falls gradually around `range`
 *                   (calibrated with scratch/fanet-linkcal.cc).
 */
#ifndef FANET_CHANNEL_H
#define FANET_CHANNEL_H

#include "ns3/core-module.h"
#include "ns3/propagation-module.h"
#include "ns3/wifi-module.h"

#include <string>

namespace ns3
{

struct FanetChannelConfig
{
    std::string channel = "range"; ///< range | fading
    double range = 250.0;          ///< nominal radio range (m)
    double txPowerDbm = 0.0;       ///< fading only
    double plExp = 2.0;            ///< fading only: path-loss exponent (2 = free space, LOS)
    double ccaDbm = -92.0;         ///< fading only: CCA sensitivity
    double preambleMinRssiDbm = -95.0; ///< fading only
    double nakagamiM = 0.0; ///< STEP11b: 0 = distance profile m = 3/2/1.5 (K2); > 0 = constant m (K1: 10)
};

inline void
AddFanetChannelArgs(CommandLine& cmd, FanetChannelConfig& c)
{
    cmd.AddValue("channel", "STEP10c: range (ideal disc) or fading (path loss + Nakagami)", c.channel);
    cmd.AddValue("txPowerDbm", "STEP10c: transmit power for channel=fading (dBm)", c.txPowerDbm);
    cmd.AddValue("plExp", "STEP10c: path-loss exponent for channel=fading", c.plExp);
    cmd.AddValue("ccaDbm", "STEP10c: CCA sensitivity for channel=fading (dBm)", c.ccaDbm);
    cmd.AddValue("nakagamiM",
                 "STEP11b: Nakagami m for channel=fading; 0 = distance profile 3/2/1.5, >0 = constant m",
                 c.nakagamiM);
}

inline void
ConfigureFanetChannel(YansWifiChannelHelper& ch, YansWifiPhyHelper& phy, const FanetChannelConfig& c)
{
    ch.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    if (c.channel == "range")
    {
        ch.AddPropagationLoss("ns3::RangePropagationLossModel", "MaxRange", DoubleValue(c.range));
    }
    else if (c.channel == "fading")
    {
        ch.AddPropagationLoss("ns3::LogDistancePropagationLossModel",
                              "Exponent", DoubleValue(c.plExp),
                              "ReferenceDistance", DoubleValue(1.0),
                              "ReferenceLoss", DoubleValue(40.09)); // Friis at 1 m, 2.412 GHz
        double m0 = 3.0, m1 = 2.0, m2 = 1.5; // K2: distance profile
        if (c.nakagamiM > 0.0)
            m0 = m1 = m2 = c.nakagamiM;      // K1: constant (strong line of sight)
        ch.AddPropagationLoss("ns3::NakagamiPropagationLossModel",
                              "Distance1", DoubleValue(80.0),
                              "Distance2", DoubleValue(200.0),
                              "m0", DoubleValue(m0),
                              "m1", DoubleValue(m1),
                              "m2", DoubleValue(m2));
        ch.AddPropagationLoss("ns3::RangePropagationLossModel", "MaxRange", DoubleValue(2.0 * c.range));
        phy.Set("TxPowerStart", DoubleValue(c.txPowerDbm));
        phy.Set("TxPowerEnd", DoubleValue(c.txPowerDbm));
        phy.Set("CcaSensitivity", DoubleValue(c.ccaDbm));
        phy.SetPreambleDetectionModel("ns3::ThresholdPreambleDetectionModel",
                                      "MinimumRssi", DoubleValue(c.preambleMinRssiDbm),
                                      "Threshold", DoubleValue(4.0));
    }
    else
    {
        NS_FATAL_ERROR("channel must be range or fading, got " << c.channel);
    }
}

} // namespace ns3

#endif // FANET_CHANNEL_H
