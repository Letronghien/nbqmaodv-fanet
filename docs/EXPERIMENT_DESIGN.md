# Experiment design (pre-registration draft, Step 11)

Status: DRAFT. Items marked **[pilot]** are fixed from the AODV-only pilot (tools/pilot_step11.sh,
tuning seeds 101-103) and then frozen. This file is committed before any main run; the main
experiments are executed exactly as written, whatever their outcome.

## 1. Research questions

- RQ1. Does neighbour-value bootstrapping (NBQ-MAODV) remove the weaknesses of learning-based
  multipath AODV (PMAODV, QMAODV, SA-QMAODV)?
- RQ2. In which operating regions (density x load x link quality) is NBQ-MAODV better than, equal to,
  or worse than AODV? (regime map)
- RQ3. How much could an oracle that picks the better of AODV / NBQ-MAODV per condition gain over
  always using one of them? (value of adaptive strategy selection; motivates follow-up work)
- RQ4. Which components of NBQ-MAODV matter? (ablation)

## 2. Fixed scenario

| Item | Value |
|---|---|
| Area | 1000 x 1000 m (E6: 1500 x 1500 m) |
| Mobility | Gauss-Markov, alpha 0.85, mean speed U[5,20] m/s, 1 s step, altitude 80-120 m, reflecting borders |
| Base station | ground (z = 0), area centre (E6: middle of an edge) |
| Traffic | every UAV -> base station, CBR/UDP 512 B |
| MAC/PHY | 802.11b ad hoc, 2 Mbit/s data, 1 Mbit/s control |
| Channels | `range` (ideal 250 m disc) and `fading` (log-distance n = 2 + Nakagami m = 3/2/1.5, Tx -1 dBm: 50 % frame success at 250 m, fanet-linkcal) |
| Duration | 300 s, metrics over [60, 300] s **[pilot: warm-up length]** |
| Seeds | 1-20 (tuning seeds 101-103 never reported as results) |
| Routing parameters | as in docs/PROTOCOL_AUDIT.md; NBQ-MAODV: Epsilon0 0.1, EpsilonMin 0.02, UseRerrBump false (chosen on tuning seeds, Step 10b) |

## 3. Experiments

| Id | Purpose | Factors | Protocols | Runs |
|---|---|---|---|---|
| E1 | density | N = 20, 30, 40 **[pilot: add 10?]**; 4 pkt/s; 2 channels | all five | 3x2x5x20 = 600 |
| E2 | regime map | N = 20, 30, 40 x load 2, 4, 8, 12 **[pilot: 16?]** x 3 channel qualities (range, fading +3 dBm, fading -1 dBm) | AODV, NBQ-MAODV | 36x2x20 = 1440 (E1 cells reused) |
| E3 | load | 30 UAV, load 2-12, 2 channels | all five | 4x2x5x20 = 800 (partly shared with E2) |
| E4 | energy | 30 UAV, fading, 4 pkt/s, battery 280 J x U[0.5,1] **[pilot]** | all five | 100 |
| E5 | ablation | 30 UAV, 2 channels, 4 and 12 pkt/s; NBQ variants: default, no bootstrap, SA epsilon (0.3/0.1), RerrBump on, source-only | NBQ-MAODV | 2x2x5x20 = 400 |
| E6 | harder topology | 1500 x 1500 m (45 and 68 UAV) and base station at the edge (1000 x 1000, 30 UAV); 4 pkt/s; 2 channels | AODV, NBQ-MAODV (+ SA-QMAODV) | ~360 |

## 4. Metrics

PDR (all generated packets) and PDR of live UAVs (`pdrAlive`), mean / median / 95th-percentile
end-to-end delay, throughput, NRL and control mix (RREQ, RREP/HELLO, RERR), energy (depleted UAVs,
first depletion). Local indicators logged for follow-up work: MAC ACK ratio, mean neighbours within
250 m, mean MAC queue length.

## 5. Analysis plan

- Per condition: mean and 95 % CI over 20 seeds; paired differences vs AODV (same seed) with the
  two-sided Wilcoxon signed-rank test; Holm correction within each experiment.
- Regime map: for every cell of E2, "NBQ better / equivalent / worse" = sign of the paired mean
  difference when p < 0.05 after Holm, otherwise "equivalent".
- Oracle: per cell pick the protocol with the higher mean PDR; report the gain over always-AODV and
  always-NBQ, averaged over cells.
- Correlation of local indicators with the sign of (NBQ - AODV), as input for the follow-up paper.

## 6. Deviations

Any change after the freeze is listed here with date and reason.
