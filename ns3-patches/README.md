# Patches applied to the ns-3.48 tree of this project

## wifi-radio-energy-model-predictive-off.patch

Adds the attribute `PredictiveSwitchToOff` (default `true` = unchanged ns-3 behaviour) to
`ns3::WifiRadioEnergyModel`.

Reason: with the default behaviour the model schedules its own switch to OFF from a prediction
of the remaining energy. In our FANET scenarios this prediction fired when the battery still
held ~23-25% of its energy (measured with `--energyDebug=1`), and the switch only changed the
state of the energy model: the WiFi PHY kept transmitting and receiving. Depleted UAVs therefore
never left the network and the battery never reached the low-battery threshold (10%).

With `PredictiveSwitchToOff=false` (set by all fanet-scenario-*.cc files), depletion is decided
only by `BasicEnergySource` when the battery reaches its low-battery threshold; the source then
calls the depletion callback, which by default is `WifiPhy::SetOffMode`.

Apply inside the ns-3 tree of this project:

    cd ~/nbqmaodv-fanet/ns-3-nbq
    git apply -v ~/nbqmaodv-repo/ns3-patches/wifi-radio-energy-model-predictive-off.patch
