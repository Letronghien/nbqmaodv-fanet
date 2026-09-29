# Experiment design — FROZEN (Step 11c)

This document was committed **before** any main run. The main experiments are executed exactly as
written below, whatever their outcome. Any later change is recorded in §7 with date and reason.
Tuning seeds 101–103 (Steps 10b–11b) are never reported as results; evaluation seeds are 1–20.

## 1. Research questions

- **RQ1** Does neighbour-value bootstrapping (NBQ-MAODV) remove the weaknesses of learning-based
  multipath AODV (PMAODV, QMAODV, SA-QMAODV)?
- **RQ2** In which operating regions (density × load × channel) is NBQ-MAODV better than, equivalent
  to, or worse than AODV? (regime map)
- **RQ3** How much would an oracle that picks the better of AODV / NBQ-MAODV per condition gain over
  always using one of them? (value of adaptive strategy selection — motivates follow-up work)
- **RQ4** Which components of NBQ-MAODV matter? (ablation)

## 2. Fixed scenario

| Item | Value |
|---|---|
| Area | 1000 × 1000 m (E6b: 1500 × 1500 m) |
| Mobility | Gauss–Markov: α = 0.85, mean speed U[5, 20] m/s, 1 s step, altitude 80–120 m, reflecting borders |
| Base station | ground (z = 0); area centre (E6a: middle of an edge) |
| Traffic | every UAV → base station, CBR/UDP, 512 B; **total offered load L** split equally (rate = L / N) |
| MAC / PHY | IEEE 802.11b ad hoc, 2 Mbit/s data, 1 Mbit/s control |
| Duration | 300 s; all traffic metrics over [60, 300] s (warm-up 60 s) |
| Seeds | 1–20, common random numbers (mobility, traffic start, battery draw identical across protocols) |

### Channel axis (same effective range R_eff = 250 m, R_eff² = ∫ p(d)·2d dd, p = frame success)

| Level | Model | Tx power | 90 % range | 50 % range |
|---|---|---|---|---|
| **K0** | ideal disc (`RangePropagationLossModel`, 250 m); no interference beyond 250 m | 16 dBm | 250 m | 250 m |
| **K1** | log-distance (n = 2, 40.09 dB @1 m) + Nakagami m = 10, cut 500 m | **−1.9 dBm** | 200 m | 250 m |
| **K2** | log-distance (n = 2) + Nakagami m = 3 / 2 / 1.5 (< 80 / 80–200 / > 200 m), cut 500 m | **−2.0 dBm** | 125 m | 225 m |

K1/K2: CCA −92 dBm, preamble detection min RSSI −95 dBm / 4 dB. Calibration: `tools/calib_step11b.sh`.
Interpretation: K0 → K1 = realistic interference and soft coverage edge; K1 → K2 = fading gray zone.

### Protocol parameters

As in `docs/PROTOCOL_AUDIT.md`. NBQ-MAODV: NeighbourBootstrap true, γ′ 0.95, V_fail 5, HopCostPrior 0.3,
Epsilon0 0.1, EpsilonMin 0.02, UseRerrBump false (chosen on tuning seeds, Steps 10b–10c).

## 3. Experiments

Channel K ∈ {K0, K1, K2}; N UAVs; total load L (packets/s). Runs shared between experiments are simulated once.

| Id | Purpose | Conditions | Protocols |
|---|---|---|---|
| **E1** density | N ∈ {20, 30, 40}, L = 80, all K | AODV, PMAODV, QMAODV, SA-QMAODV, NBQ-MAODV |
| **E2** regime map | N ∈ {20, 30, 40} × L ∈ {40, 80, 160, 320} × all K (36 cells) | AODV, NBQ-MAODV |
| **E3** load | N = 30, L ∈ {40, 80, 160, 320}, all K | all five |
| **E4** energy | N = 30, L = 80, K ∈ {K0, K1}, battery 280 J × U[0.5, 1] (stream 4000) | all five |
| **E5** ablation | N = 30, L ∈ {80, 320}, all K | NBQ default, no bootstrap, SA ε (0.3/0.1), RERR bump on, source-only |
| **E6a** BS at edge | N = 30, L = 80, all K | AODV, NBQ-MAODV, SA-QMAODV |
| **E6b** larger area | 1500 × 1500 m, N ∈ {45, 68} (same density as 20, 30), L = 80, all K | AODV, NBQ-MAODV, SA-QMAODV |
| **R600** robustness | N = 30, L = 80, all K, 600 s, metrics over [300, 600] s | AODV, NBQ-MAODV |

Execution order: E2, E5, E1, E3, E4, E6a, E6b, R600 (`tools/run_main.py`).

## 4. Metrics

PDR (all generated packets); PDR of live UAVs (`pdrAlive`, E4); delay mean, **median and 95th
percentile** (95th percentile is the primary delay metric); throughput; NRL and control mix (RREQ,
RREP/HELLO, RERR); E4: depleted UAVs, first depletion. Local indicators (for follow-up work): MAC ACK
ratio, mean neighbours within 250 m, mean MAC queue, mean distance to the base station.

## 5. Analysis plan (`tools/analyze_main.py`)

1. Per condition: mean and 95 % CI over 20 seeds.
2. Paired difference vs AODV (same seed), two-sided Wilcoxon signed-rank; Holm correction over all
   comparisons within one experiment.
3. Regime map (E2): per cell and channel, NBQ **better / worse** = sign of the paired mean difference in
   PDR when Holm-adjusted p < 0.05, otherwise **equivalent**; the same for 95th-percentile delay.
4. Oracle (RQ3): per cell take the protocol with the higher mean PDR; report the mean gain over
   always-AODV and always-NBQ, per channel and overall.
5. Ablation (E5): paired difference of each variant vs NBQ default, Wilcoxon + Holm.
6. Indicators: Spearman correlation between the AODV-run local indicators of a cell and the
   NBQ − AODV PDR difference (input for the adaptive-selection paper).
7. Robustness (R600): sign of NBQ − AODV over [300, 600] s vs over [60, 300] s (E2 cells, N = 30, L = 80).

## 6. Pilot findings that fixed this design (AODV only, tuning seeds 101–103)

- **P1/P8 stationarity:** Random Waypoint concentrates UAVs near the centre (mean distance to BS
  ≈ 300 m vs ≈ 400 m uniform) and gives an optimistic PDR (≈ 95 % vs ≈ 70–85 % with Gauss–Markov).
  With Gauss–Markov the spatial distribution is stationary, but PDR still rises slowly over 600 s
  (68 → 86 %, cause not identified) → warm-up 60 s + R600 robustness check.
- **P2 → P6 density confounded with load:** with a fixed per-UAV rate the total load grows with N;
  with a constant total load the K0 PDR rises monotonically with N (54.6 → 59.9 → 68.8 %).
- **P6/P7 channel:** at equal R_eff, AODV PDR drops from ≈ 60 % (K0) to ≈ 18 % (K1) and ≈ 11 % (K2)
  at N = 30, L = 80; K0 ignores interference beyond 250 m and strongly overestimates AODV.
- **P5 energy:** 280 J × U[0.5, 1] gives the first depletion at ≈ 150 s and almost all UAVs depleted by 300 s.

## 7. Deviations from earlier drafts (all decided before any main run)

| Date | Change | Reason |
|---|---|---|
| Step 11 | Random Waypoint → Gauss–Markov | RWP centre bias / non-stationarity (Yoon et al., INFOCOM 2003) |
| Step 11b | fading calibration "50 % at 250 m" → "R_eff = 250 m"; K1 level added | channels must have equal mean connectivity; separate interference/edge effects from fading |
| Step 11b | density at constant **total** load | per-UAV rate confounded density with load |
| Step 11b | E4 on K0 and K1 (not on the old fading channel) | old fading channel gave PDR ≈ 10 %, energy effects not observable |
