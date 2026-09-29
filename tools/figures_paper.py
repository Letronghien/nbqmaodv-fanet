#!/usr/bin/env python3
"""
figures_paper.py -- publication figures not produced by analyze_main.py.

    python3 ~/nbqmaodv-repo/tools/figures_paper.py ~/nbqmaodv-fanet/results/main/runs.csv \
        --calib ~/nbqmaodv-fanet/results/calib11b.txt --out ~/nbqmaodv-fanet/results/main/figures

Figures (PNG 300 dpi + PDF):
  fig_linkcal     frame success vs distance for K1/K2 at the calibrated Tx power (needs --calib)
  fig_ablation    E5: PDR of each NBQ variant minus NBQ-MAODV default, mean +- 95 % CI
  fig_indicator   E2: MAC ACK ratio of the AODV runs vs NBQ - AODV PDR difference (36 cells)
  fig_r600        R600: NBQ - AODV PDR difference over [60,300] s vs [300,600] s
  fig_e6          E6: NBQ-MAODV and SA-QMAODV minus AODV, edge base station and larger area
"""
import argparse, math, os, re
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": .3, "figure.dpi": 150})
KS = ["K0", "K1", "K2"]
KCOL = {"K0": "#4c72b0", "K1": "#dd8452", "K2": "#55a868"}


def ci95(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else np.nan


def exp(df, e):
    return df[df.exps.fillna("").str.contains(fr"(?:^|;){e}(?:$|;)", regex=True)]


def pdiff(sub, ref, cmp, metric="pdr"):
    a = sub[sub.proto == ref].set_index("seed")[metric]
    b = sub[sub.proto == cmp].set_index("seed")[metric]
    s = a.index.intersection(b.index)
    d = (b[s] - a[s]).astype(float)
    return d.mean(), ci95(d), len(s)


def save(fig, out, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out, f"{name}.{ext}"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


def fig_linkcal(path, out, k1tx=-2.0, k2tx=-2.0):
    curves = {}; cur = None
    for line in open(path):
        if line.startswith("# channel="):
            kv = dict(x.split("=") for x in line[2:].split())
            cur = (float(kv.get("nakagamiM", 0)), float(kv["txPowerDbm"])); curves[cur] = []
        elif cur and re.match(r"^\d", line):
            d, fs, _ = line.strip().split(","); curves[cur].append((float(d), float(fs)))
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    ax.plot([0, 250, 250, 500], [1, 1, 0, 0], color=KCOL["K0"], lw=1.6, label="K0 ideal disc")
    for (m, tx), lab, col in (((10.0, k1tx), "K1 Nakagami m=10", KCOL["K1"]),
                              ((0.0, k2tx), "K2 Nakagami m=3/2/1.5", KCOL["K2"])):
        if (m, tx) in curves:
            pts = sorted(curves[(m, tx)])
            ax.plot([d for d, _ in pts], [p for _, p in pts], "o-", ms=3, color=col, label=f"{lab} ({tx:+g} dBm)")
    ax.axvline(250, ls=":", color="grey")
    ax.set_xlabel("distance (m)"); ax.set_ylabel("frame success probability")
    ax.set_xlim(0, 500); ax.set_ylim(-0.02, 1.02); ax.legend(fontsize=7)
    save(fig, out, "fig_linkcal")


def fig_ablation(df, out):
    sub = exp(df, "E5")
    if sub.empty: return
    variants = [("NBQ-noBoot", "no neighbour bootstrap"), ("NBQ-bump", "RERR ε bump"),
                ("NBQ-saEps", "SA exploration (0.3/0.1)"), ("NBQ-srcOnly", "source-only selection")]
    conds = [(K, L) for K in KS for L in (80, 320)]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    w = 0.2
    for i, (v, lab) in enumerate(variants):
        m, c = [], []
        for K, L in conds:
            mm, cc, _ = pdiff(sub[(sub.K == K) & (sub.L == L)], "NBQ-MAODV", v); m.append(mm); c.append(cc)
        ax.bar(np.arange(len(conds)) + (i - 1.5) * w, m, w, yerr=c, capsize=2, label=lab)
    ax.axhline(0, color="k", lw=.8)
    ax.set_xticks(range(len(conds))); ax.set_xticklabels([f"{K}\nL={L}" for K, L in conds])
    ax.set_ylabel("PDR: variant − NBQ-MAODV (points)")
    ax.legend(fontsize=7, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.22), frameon=False)
    save(fig, out, "fig_ablation")


def fig_indicator(df, out):
    sub = exp(df, "E2")
    if sub.empty: return
    a = sub[sub.proto == "AODV"].groupby(["K", "N", "L"])["macAckRatio"].mean()
    rows = []
    for (K, N, L), g in sub.groupby(["K", "N", "L"]):
        m, c, _ = pdiff(g, "AODV", "NBQ-MAODV"); rows.append((K, N, L, a.get((K, N, L), np.nan), m, c))
    r = pd.DataFrame(rows, columns=["K", "N", "L", "ack", "diff", "ci"])
    rho = stats.spearmanr(r.ack, r["diff"]).correlation
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    for K in KS:
        q = r[r.K == K]
        ax.errorbar(q.ack, q["diff"], yerr=q.ci, fmt="o", ms=4, capsize=2, color=KCOL[K], label=K)
    ax.axhline(0, color="k", lw=.8)
    ax.set_xlabel("MAC ACK ratio of the AODV runs"); ax.set_ylabel("PDR: NBQ-MAODV − AODV (points)")
    ax.set_title(f"36 regime-map cells, Spearman ρ = {rho:.2f}", fontsize=9); ax.legend(fontsize=7)
    save(fig, out, "fig_indicator")


def fig_r600(df, out):
    late = exp(df, "R600"); early = exp(df, "E2")
    if late.empty or early.empty: return
    early = early[(early.N == 30) & (early.L == 80)]
    fig, ax = plt.subplots(figsize=(4.2, 2.8)); w = 0.35
    for j, (sub, lab) in enumerate(((early, "[60, 300] s"), (late, "[300, 600] s"))):
        mc = [pdiff(sub[sub.K == K], "AODV", "NBQ-MAODV")[:2] for K in KS]
        ax.bar(np.arange(3) + (j - .5) * w, [m for m, _ in mc], w, yerr=[c for _, c in mc], capsize=3, label=lab)
    ax.axhline(0, color="k", lw=.8); ax.set_xticks(range(3)); ax.set_xticklabels(KS)
    ax.set_ylabel("PDR: NBQ-MAODV − AODV (points)"); ax.legend(fontsize=7, title="measurement window", title_fontsize=7)
    save(fig, out, "fig_r600")


def fig_e6(df, out):
    a = exp(df, "E6a"); b = exp(df, "E6b")
    if a.empty and b.empty: return
    groups = [("edge BS, 30 UAV", a)] + [(f"1500 m, {N} UAV", b[b.N == N]) for N in (45, 68)]
    fig, axs = plt.subplots(1, 3, figsize=(8.4, 2.8), sharey=True)
    for ax, K in zip(axs, KS):
        for i, p in enumerate(("NBQ-MAODV", "SA-QMAODV")):
            mc = [pdiff(g[g.K == K], "AODV", p)[:2] if not g.empty else (np.nan, np.nan) for _, g in groups]
            ax.bar(np.arange(3) + (i - .5) * .35, [m for m, _ in mc], .35, yerr=[c for _, c in mc], capsize=2, label=p)
        ax.axhline(0, color="k", lw=.8); ax.set_title(K)
        ax.set_xticks(range(3)); ax.set_xticklabels([g for g, _ in groups], fontsize=7, rotation=15)
    axs[0].set_ylabel("PDR − AODV (points)"); axs[0].legend(fontsize=7)
    save(fig, out, "fig_e6")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("runs"); ap.add_argument("--calib"); ap.add_argument("--out")
    ap.add_argument("--k1tx", type=float, default=-2.0, help="calibration curve closest to the K1 power")
    ap.add_argument("--k2tx", type=float, default=-2.0, help="calibration curve closest to the K2 power")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.runs)), "figures"); os.makedirs(out, exist_ok=True)
    df = pd.read_csv(a.runs)
    if a.calib and os.path.exists(a.calib):
        fig_linkcal(a.calib, out, a.k1tx, a.k2tx)
    fig_ablation(df, out); fig_indicator(df, out); fig_r600(df, out); fig_e6(df, out)
