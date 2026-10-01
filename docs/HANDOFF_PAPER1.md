# HANDOFF — Paper 1 (NBQ-MAODV), finalisation and submission

Attach this file at the start of a new conversation and write: "Continue Paper 1 from this handoff."

## 1. People, repo, documents

- Authors: Trong-Hien Le, Khoa Tran Thi-Minh, Huu-Dung Ngo (Industrial University of Ho Chi Minh City).
- Code, data, design: https://github.com/Letronghien/nbqmaodv-fanet (public). Key files:
  `docs/PROTOCOL_AUDIT.md`, `docs/EXPERIMENT_DESIGN.md` (frozen, Step 11c), `docs/EXPERIMENT_ADDENDUM.md`
  (post-hoc, frozen before running, Step 13b), `ns3-patches/README.md`, `tools/run_main.py`,
  `tools/analyze_main.py`, `tools/analyze_extra.py`, `tools/figures_paper.py`, `tools/run_addendum.py`,
  `tools/analyze_addendum.py`.
- **Current manuscript (Claude Doc): https://claude.ai/code/artifact/d4f8f6c7-ed69-44c0-937a-b7c280fdb60c**
  ("Paper 1 — NBQ-MAODV — SUBMISSION DRAFT v1"). Older drafts are history only.
- VM: Google Cloud, Ubuntu, 8 vCPU, user `letronghien`; ns-3.48 tree `~/nbqmaodv-fanet/ns-3-nbq`
  (optimized build, patched WifiRadioEnergyModel). Results: `~/nbqmaodv-fanet/results/main/` (3,860 runs,
  `runs.csv`, `analysis/`, `analysis_extra/`, `figures/`) and `~/nbqmaodv-fanet/results/addendum/` (1,560 runs).
- Figure files: `analysis/E1_density.png`, `E3_load.png`, `E2_regime_pdr.png`, `E2_regime_delayP95Ms.png`;
  `figures/fig_linkcal, fig_ablation, fig_indicator, fig_r600, fig_e6` (.png/.pdf);
  `analysis_extra/*.pdf` (vector versions of E1/E3/E2); Fig. 1 schematic `fig1_nbq_mechanism.pdf`
  (generated in the old conversation — regenerate if missing).

## 2. Working rules agreed with the author

- Vietnamese in chat; manuscript in English.
- Step by step; Claude writes patches checked against ns-3.48 headers; the author applies with `git apply`,
  builds, runs, pastes outputs. Every code change behind an attribute whose default reproduces old results.
- No change of design or parameters after seeing results; post-hoc analyses are labelled as such and
  committed before running. Report negative results honestly. Critique results like a reviewer.

## 3. What the paper now claims (final numbers)

- Five protocols on one multipath AODV core: AODV, PMAODV, QMAODV, SA-QMAODV, NBQ-MAODV.
  Channels at equal effective range 250 m: K0 ideal disc, K1 Nakagami m=10 (−1.9 dBm), K2 m=3/2/1.5 (−2.0 dBm).
  Gauss–Markov mobility, 1000×1000 m, ground BS at centre, 300 s (metrics 60–300 s), 20 seeds.
- Own-table bootstrap learners (QMAODV, SA-QMAODV) are worse than PMAODV (no learning).
- NBQ-MAODV: best learner almost everywhere; ablation: removing neighbour bootstrap −1.2…−7.1 points;
  RERR ε-bump harmful; exploration level secondary; source-only selection +1.8* on K0 high load.
- Regime map E2 (NBQ − AODV PDR): K0 3 AODV-better/9 equiv (−7.7…−0.9); K1 12 equiv; K2 7 NBQ-better/5 equiv
  (+0.6…+2.3, mean +1.7, +19.5 % rel., d_z ≈ 1.1, 82 % of seeds). Oracle +0.58 points vs always-AODV.
  MAC ACK ratio ρ = −0.85 (separates channels, weak within a channel).
- Post-hoc A1 (TagsOnAir): K2 advantage halves to +0.9 (+11 %), 12/12 positive, 2 significant;
  K0 −5.2, K1 −2.0. A2 Liu et al. 2026 Q-Learning AODV: ≈ AODV on K2, NBQ better than it by 1.0–1.8*.
  A3 K2 at +3 dBm: NBQ ≈ AODV (−0.9…+1.6*), Liu −3…−14*.
- Energy: no protocol extends lifetime (always-on radios). E6 harder topologies: direction kept, n.s.
  R600: K0/K2 stable; K1 becomes AODV-better late (−5.2*).
- Ideal disc overestimates AODV ≈ 3× (56.1 % K0 vs 15.9 % K1).

## 4. Open tasks (in order)

1. Author: read the draft; fill placeholders [7], [8], [9], [30], CRediT, Funding; confirm framing.
2. Commit addendum results; create a Zenodo release + DOI for ref [27].
3. Choose target journal (Q2/Q3 wireless/communications first; check SJR of the current year).
4. Claude: optional figure — A1 regime map with tags on air next to Fig. 3 (needs a small script using
   `results/addendum/runs.csv` + main `runs.csv`).
5. Claude: convert to the journal's LaTeX template with BibTeX (renumbers refs [29]–[32] automatically),
   vector figures, highlights, cover letter, response-to-reviewers template.
6. Language proofreading.

## 5. Acceptance estimate given in the old conversation

Q4 ≈ 75–80 %, Q3 ≈ 55–65 % (likely after major revision), provided the paper is framed as a controlled
empirical study, not as "a new protocol that beats AODV". Main residual risks: low absolute PDR on K1/K2,
802.11b, mechanism not novel (handled by framing), self-citation of unpublished SA-QMAODV [9].
