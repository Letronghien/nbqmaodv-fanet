# Protocol audit (Step 9)

Code state: commit `5126abf` (Step 8e). ns-3.48 with `ns3-patches/wifi-radio-energy-model-predictive-off.patch`.
All protocols except AODV share one multipath AODV core (copied from ns-3.48 AODV): RREQ rate limit,
expanding-ring search, packet buffering during discovery, RERR, MAC-layer link-break detection, and
alternative reverse routes recorded from duplicate RREQs (up to `MaxPaths`). They differ only in how a
node picks its next hop.

Legend: ✅ matches the paper · ⚙️ implementation choice not fixed by the paper (documented) · ⚠️ known limitation

## 1. AODV (RFC 3561, ns-3.48 module)

| Item | Status | Evidence |
|---|---|---|
| Unmodified ns-3.48 `aodv` module | ✅ | `reference/aodv` identical to tag `ns-3.48` (diff: only missing `.pcap` test vectors) |

## 2. PMAODV (IAAA'25) — `qmaodv` module with `Policy=Probabilistic`

| Item | Status | Evidence |
|---|---|---|
| Multipath routes per destination, K = `MaxPaths` (default 3; paper evaluates 2, 3, 4) | ✅ | shared core, `QTable::BuildCandidates` |
| Next hop drawn with p_i = (1/HC_i) / Σ_k (1/HC_k) | ✅ | `qmaodv-qtable.cc`, `SelectEpsilonGreedy`, `m_probabilistic` branch |
| Selection at source **and** every relay | ✅ | `RouteOutput` + `Forwarding` (`HopByHop=true`) |
| Previous hop never chosen | ⚙️ | `PrevHopTag`; loops longer than 2 hops are ended by TTL only |
| Legacy AOMDV-based module `pmaodv` | not used | kept as `PMAODV-AOMDV` for reference; defects P1–P6 documented in Step 9 notes |

## 3. QMAODV (ICIT 2025) — `qmaodv` module, `Policy=QLearning`, all adaptive switches off

| Item | Paper | Code default | Status |
|---|---|---|---|
| State / action | destination / next hop | same | ✅ |
| Q initialisation | normalised 1/HC | `QTable::EnsureRecord` | ✅ |
| Update | Q ← (1−α)Q + α[r + γ max Q] | `QTable::UpdateQValue` | ✅ |
| α, γ | 0.5, 0.9 | `Alpha0`=0.5 (fixed), `Gamma`=0.9 | ✅ |
| ε schedule | 0.5, −0.02 / 10 s | `Epsilon0`=0.5, `PeriodicAdaptInterval`=10 s, floor 0 | ✅ |
| Reward | 0.6·ACK + 0.4·delay term | `RewardW1`=0.6, `RewardW2`=0.4, `RewardW3`=0 | ✅ |
| ACK and delay from the MAC layer | yes | `AckedMpdu`/`DroppedMpdu` + `QFeedbackTag` (`UseMacFeedback=true`) | ✅ |
| Delay term | 1/(delay+1) | 1/(1 + delay/d_ref), d_ref = 10 ms | ⚙️ unit fixed so the term is not ≈1 for every hop |
| Hop-by-hop selection | yes | `HopByHop=true` | ✅ |

## 4. SA-QMAODV (SA paper) — `saqmaodv` module

| Item | Paper | Code default | Status |
|---|---|---|---|
| ε raised on RERR / link break | ε = min(0.5, ε+0.2) | `UseRerrBump=true` | ✅ |
| ε periodic decay | max(0.1, ε−0.02), every 5 s (Fig. 2) | `PeriodicAdaptInterval`=5 s | ✅ |
| Initial ε | not specified | `Epsilon0`=0.3 | ⚙️ |
| α_t | 0.1 + 0.8(1 − e^(−λΔSeq)) | ΔSeq over `SeqNoWindow`=5 s | ✅ |
| λ | not specified | `Lambda`=0.1 | ⚙️ (FANET-Sim used 0.5; sensitivity in E6) |
| Reward weights, normal | (0.5, 0.4, 0.1) | same | ✅ |
| Reward weights, low energy (<20%) | (0.1, 0.1, 0.8) | same, triggered by the node's own battery | ✅ |
| Energy term = residual energy of the relay | yes (text) | `NeighborInfoTag` on all control packets, `UseRelayEnergy=true` | ✅ |
| Congestion / lossy-link regimes | text only, no thresholds | not implemented (decision S3 = option 2) | ⚙️ |
| MAC feedback, hop-by-hop, delay unit | as QMAODV | as QMAODV | ✅ / ⚙️ |

## 5. NBQ-MAODV — `nbqmaodv` module

Currently an exact copy of SA-QMAODV (verified: identical output for identical seeds). The NBQ learning
rule is implemented from Step 10 on.

## 6. Simulation scenario (`scratch/fanet-scenario-<module>.cc`)

| Item | Status | Note |
|---|---|---|
| Common random numbers | ✅ | mobility (streams 1000, 2000) and traffic start times (3000) fixed across protocols; protocol-internal RNGs are auto-assigned |
| Battery model | ✅ | `BasicEnergySource` + `WifiRadioEnergyModel`; UAV dies at the 10% low-battery threshold and its PHY is switched off (Steps 8c–8e) |
| ns-3.48 energy-model defects | ⚠️ worked around | predictive switch-to-OFF fires at ~23% and does not switch the PHY off; direct `SetOffMode` during a reception aborts. See `ns3-patches/README.md` |
| Depleted UAV traffic | ⚠️ | its CBR application keeps generating packets after death (counted as sent, never delivered) |
| Routing overhead | ✅ | every IPv4 transmission of a UDP-654 packet (RREQ, RREP, RERR, HELLO) |
