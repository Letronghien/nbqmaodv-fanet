# Experiment addendum — post-hoc analyses (Step 13c)

Written and committed **before** these runs, after the main results of `docs/EXPERIMENT_DESIGN.md`
were known. The paper reports these experiments separately, as post-hoc checks, and does not replace
any pre-registered result with them. Seeds 1–20; scenario, metrics and statistics as in the main design.

## Why

| Id | Question | Trigger |
|---|---|---|
| **A1** | Does the NBQ-MAODV advantage survive when the information carried in ns-3 packet tags is paid for on air? | Packet tags are not transmitted in ns-3. NBQ-MAODV carries 4 + 1 + 8n bytes per control packet (energy + values), all multipath variants 4 bytes per data packet (previous hop). On K1/K2 control traffic dominates airtime. |
| **A2** | How does an external learning baseline of the same family compare? | Novelty check: the Q-Learning AODV of Liu et al. (Electronics 15(16):3721, 2026) already uses a neighbour-value bootstrap. |
| **A3** | Is the regime conclusion specific to the low delivery level of K2? | Reviewers may attribute the K2 result to floor effects. |

## Protocol variants

- `*-onair`: attribute `TagsOnAir=true` — every packet is padded with the bytes its tags would occupy as real fields (data: +4 B once at the source; control: +4 B energy for SA-QMAODV/NBQ-MAODV, +1+8n B values for NBQ-MAODV, +28 B state for LIU).
- `LIU-QAODV`: nbqmaodv module with `LiuQAodv=true;TagsOnAir=true`. Implemented from the paper: Eq. (14) update Q_x(y,z) ← α[R(x,z) + γ max_n Q_z(y,n)] + (1−α)Q_x(y,z) on reception of RREQ/RREP/HELLO from z, α = 0.5, γ = 1; Eq. (15) reward = equal-weight mean of link stability RQ (Eq. (16), c = 0.94, R = 250 m), residual energy of z, free share of z's route-discovery buffer and the velocity term Cv (Eq. (12)), divided by the hop count; position/velocity/buffer exchanged on control packets; greedy selection of the highest-valued path at the source; no MAC feedback, no exploration, no dead-end signalling; elevation term inactive (single medium). **Choices not fixed by the paper** (documented as deviations): the buffer term uses the AODV route-discovery queue; H_k is the hop count of the candidate route; routes without a usable next hop are not advertised; entries start at Q = 0.
- `K2h`: channel K2 with Tx power +3 dBm (effective range ≈ 390 m instead of 250 m) — deliberately **not** at equal effective range; it moves the operating point to higher delivery.

## Runs (`tools/run_addendum.py`)

| Id | Conditions | Protocols | Runs |
|---|---|---|---|
| A1 | E2 grid: N ∈ {20,30,40} × L ∈ {40,80,160,320} × K0–K2 | NBQ-onair (AODV and NBQ from the main runs) | 720 |
| A1b | N = 30, L ∈ {80, 320}, K0–K2 | PMAODV-onair, QMAODV-onair, SA-onair | 360 |
| A2 | N = 30, L ∈ {40, 80, 160, 320}, K0–K2 | LIU-QAODV (onair) | 240 |
| A3 | K2h: N ∈ {20,30,40} at L = 80, and N = 30 at L = 320 | AODV, NBQ-onair, LIU-QAODV | 240 |

## Analysis (`tools/analyze_addendum.py`)

Paired Wilcoxon over seeds, Holm within each of A1, A1b, A2, A3.
A1: regime counts of NBQ-onair − AODV on the E2 grid, and the cost of the tags (NBQ-onair − NBQ).
A2: LIU − AODV and LIU − NBQ-onair. A3: NBQ-onair − AODV and LIU − AODV on K2h.
Reported in the paper as Section 5.8 (post-hoc), whatever the outcome.
