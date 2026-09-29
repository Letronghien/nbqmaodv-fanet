#!/usr/bin/env python3
"""
analyze_main.py -- analysis plan of docs/EXPERIMENT_DESIGN.md §5 (frozen, Step 11c).

    python3 ~/nbqmaodv-repo/tools/analyze_main.py ~/nbqmaodv-fanet/results/main/runs.csv [outdir]

Writes tables (CSV + a printed summary) and figures (PNG) to outdir (default: next to runs.csv).
Paired tests use the seed as the pairing variable; Holm correction per experiment.
"""
import os, sys, math
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(RUNS)), "analysis")
os.makedirs(OUT, exist_ok=True)
df = pd.read_csv(RUNS)
for c in ("delayMedMs", "delayP95Ms", "pdrAlive", "macAckRatio", "avgNeighbours", "avgMacQueue", "avgDistBs",
          "rreq", "rrep", "rerr"):
    if c in df:
        df[c] = pd.to_numeric(df[c], errors="coerce")
df["exps"] = df["exps"].fillna("")
ALL5 = ["AODV", "PMAODV", "QMAODV", "SA-QMAODV", "NBQ-MAODV"]
KS = ["K0", "K1", "K2"]
REPORT = []


def say(*a):
    s = " ".join(str(x) for x in a); print(s); REPORT.append(s)


def ci95(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else np.nan


def holm(p):
    p = np.asarray(p, float); n = len(p); order = np.argsort(p); adj = np.empty(n); run = 0.0
    for i, idx in enumerate(order):
        run = max(run, (n - i) * p[idx]); adj[idx] = min(1.0, run)
    return adj


def paired(sub, a, b, metric, cond_cols):
    """rows: one per condition, paired b - a over seeds."""
    rows = []
    for cond, g in sub.groupby(cond_cols):
        pa = g[g.proto == a].set_index("seed")[metric]
        pb = g[g.proto == b].set_index("seed")[metric]
        s = pa.index.intersection(pb.index)
        if len(s) < 2:
            continue
        d = (pb[s] - pa[s]).astype(float)
        try:
            p = stats.wilcoxon(pb[s], pa[s]).pvalue if (d != 0).any() else 1.0
        except ValueError:
            p = 1.0
        row = dict(zip(cond_cols, cond if isinstance(cond, tuple) else (cond,)))
        row.update(ref=a, cmp=b, metric=metric, n=len(s), mean_a=pa[s].mean(), mean_b=pb[s].mean(),
                   diff=d.mean(), diff_ci=ci95(d), p=p)
        rows.append(row)
    return pd.DataFrame(rows)


def summary(sub, cond_cols, metrics, name):
    g = sub.groupby(cond_cols + ["proto"])
    t = g[metrics].mean().add_suffix("_mean").join(g[metrics].agg(ci95).add_suffix("_ci")).join(g.size().rename("n"))
    t.reset_index().to_csv(os.path.join(OUT, f"{name}_summary.csv"), index=False)
    return t.reset_index()


def exp(e):
    return df[df.exps.str.contains(fr"(?:^|;){e}(?:$|;)", regex=True)]


def compare_vs_aodv(e, protos, cond_cols, metrics=("pdr", "delayP95Ms", "nrl")):
    sub = exp(e)
    if sub.empty:
        say(f"\n[{e}] no data yet"); return None
    summary(sub, cond_cols, list(metrics) + ["delayMedMs", "thr"], e)
    res = pd.concat([paired(sub, "AODV", p, m, cond_cols) for p in protos if p != "AODV" for m in metrics],
                    ignore_index=True)
    if res.empty:
        return res
    res["p_holm"] = holm(res.p.values)
    res.to_csv(os.path.join(OUT, f"{e}_vs_AODV.csv"), index=False)
    m0 = metrics[0]
    say(f"\n[{e}] {m0} difference vs AODV, * = Holm p < 0.05 (paired over seeds)")
    pv = res[res.metric == m0].copy()
    pv["cell"] = pv.apply(lambda r: f"{r['diff']:+5.1f}{'*' if r['p_holm'] < 0.05 else ' '}", axis=1)
    say(pv.pivot_table(index=cond_cols, columns="cmp", values="cell", aggfunc="first").to_string())
    return res


# ------------------------------------------------------------------ E2 regime map + oracle
def regime():
    sub = exp("E2")
    if sub.empty:
        say("\n[E2] no data yet"); return
    res = compare_vs_aodv("E2", ["AODV", "NBQ-MAODV"], ["K", "N", "L"])
    if res is None or res.empty:
        return
    for metric, title, better_high in (("pdr", "PDR: NBQ-MAODV - AODV (points)", True),
                                       ("delayP95Ms", "95th-pct delay: NBQ-MAODV - AODV (ms)", False)):
        r = res[res.metric == metric]
        fig, axs = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
        lim = np.nanmax(np.abs(r["diff"])) or 1
        for ax, K in zip(axs, KS):
            q = r[r.K == K].pivot(index="N", columns="L", values="diff").sort_index(ascending=False)
            s = r[r.K == K].pivot(index="N", columns="L", values="p_holm").reindex_like(q)
            cmap = "RdBu" if better_high else "RdBu_r"
            im = ax.imshow(q.values, cmap=cmap, vmin=-lim, vmax=lim, aspect="auto")
            for i in range(q.shape[0]):
                for j in range(q.shape[1]):
                    v, p = q.values[i, j], s.values[i, j]
                    if not np.isnan(v):
                        ax.text(j, i, f"{v:+.1f}{'*' if p < 0.05 else ''}", ha="center", va="center", fontsize=9)
            ax.set_xticks(range(q.shape[1])); ax.set_xticklabels(q.columns)
            ax.set_yticks(range(q.shape[0])); ax.set_yticklabels(q.index)
            ax.set_xlabel("total load (packets/s)"); ax.set_title(K)
        axs[0].set_ylabel("UAVs")
        fig.suptitle(title + "   (* Holm p < 0.05)"); fig.colorbar(im, ax=axs, shrink=0.8)
        fig.savefig(os.path.join(OUT, f"E2_regime_{metric}.png"), dpi=200, bbox_inches="tight"); plt.close(fig)
    # regime counts
    r = res[res.metric == "pdr"].copy()
    r["regime"] = np.where(r.p_holm < 0.05, np.where(r["diff"] > 0, "NBQ better", "AODV better"), "equivalent")
    say("\n[E2] regime counts (PDR) per channel")
    say(r.groupby(["K", "regime"]).size().unstack(fill_value=0).to_string())
    # oracle (RQ3)
    m = sub.groupby(["K", "N", "L", "proto"]).pdr.mean().unstack("proto")
    m["oracle"] = m[["AODV", "NBQ-MAODV"]].max(axis=1)
    o = pd.DataFrame({"always_AODV": m["AODV"], "always_NBQ": m["NBQ-MAODV"], "oracle": m["oracle"]})
    o.to_csv(os.path.join(OUT, "E2_oracle_cells.csv"))
    say("\n[E2] oracle (mean PDR over cells) -- gain of per-cell best choice")
    agg = o.groupby(level="K").mean()
    agg.loc["all"] = o.mean()
    agg["gain_vs_AODV"] = agg.oracle - agg.always_AODV
    agg["gain_vs_NBQ"] = agg.oracle - agg.always_NBQ
    say(agg.round(2).to_string())
    # indicators (follow-up work): AODV-run local state vs NBQ-AODV difference
    ind = [c for c in ("macAckRatio", "avgNeighbours", "avgMacQueue", "avgDistBs", "nrl", "rerr") if c in sub]
    a = sub[sub.proto == "AODV"].groupby(["K", "N", "L"])[ind].mean()
    d = r.set_index(["K", "N", "L"])["diff"]
    j = a.join(d, how="inner")
    rows = [dict(indicator=c, spearman_rho=stats.spearmanr(j[c], j["diff"]).correlation) for c in ind]
    say("\n[E2] Spearman correlation of AODV-run indicators with (NBQ - AODV) PDR over 36 cells")
    say(pd.DataFrame(rows).round(3).to_string(index=False))


def ablation():
    sub = exp("E5")
    if sub.empty:
        say("\n[E5] no data yet"); return
    summary(sub, ["K", "L"], ["pdr", "delayP95Ms", "nrl"], "E5")
    res = pd.concat([paired(sub, "NBQ-MAODV", v, m, ["K", "L"]) for v in
                     ("NBQ-noBoot", "NBQ-saEps", "NBQ-bump", "NBQ-srcOnly") for m in ("pdr", "delayP95Ms")],
                    ignore_index=True)
    if res.empty:
        say("\n[E5] not enough paired data yet"); return
    res["p_holm"] = holm(res.p.values)
    res.to_csv(os.path.join(OUT, "E5_vs_NBQ.csv"), index=False)
    pv = res[res.metric == "pdr"].copy()
    pv["cell"] = pv.apply(lambda r: f"{r['diff']:+5.1f}{'*' if r['p_holm'] < 0.05 else ' '}", axis=1)
    say("\n[E5] ablation: PDR of variant - NBQ-MAODV default (points), * Holm p < 0.05")
    say(pv.pivot_table(index=["K", "L"], columns="cmp", values="cell", aggfunc="first").to_string())


def energy():
    sub = exp("E4")
    if sub.empty:
        say("\n[E4] no data yet"); return
    t = summary(sub, ["K"], ["pdr", "pdrAlive", "dead", "first_death", "delayP95Ms"], "E4")
    say("\n[E4] energy (means over seeds)")
    say(t.pivot_table(index="proto", columns="K", values=["pdrAlive_mean", "dead_mean", "first_death_mean"]).round(1).to_string())
    compare_vs_aodv("E4", ALL5, ["K"], metrics=("pdrAlive", "first_death"))


def robustness():
    a = exp("R600"); b = exp("E2")
    if a.empty or b.empty:
        say("\n[R600] no data yet"); return
    b = b[(b.N == 30) & (b.L == 80)]
    ra = paired(a, "AODV", "NBQ-MAODV", "pdr", ["K"]).assign(window="[300,600] s")
    if ra.empty:
        say("\n[R600] not enough paired data yet"); return
    rb = paired(b, "AODV", "NBQ-MAODV", "pdr", ["K"]).assign(window="[60,300] s")
    say("\n[R600] NBQ - AODV PDR difference: early vs late measurement window (N=30, L=80)")
    say(pd.concat([rb, ra])[["window", "K", "n", "diff", "diff_ci", "p"]].round(3).to_string(index=False))


def lines(e, x, title, fname, protos):
    sub = exp(e)
    if sub.empty:
        return
    fig, axs = plt.subplots(2, 3, figsize=(13, 6.5), sharex=True)
    for col, K in enumerate(KS):
        for row, (metric, lab) in enumerate((("pdr", "PDR (%)"), ("delayP95Ms", "95th-pct delay (ms)"))):
            ax = axs[row, col]
            for p in protos:
                g = sub[(sub.K == K) & (sub.proto == p)].groupby(x)[metric]
                if g.ngroups:
                    ax.errorbar(g.mean().index, g.mean().values, yerr=g.agg(ci95).values, marker="o", ms=4, capsize=2, label=p)
            ax.set_ylabel(lab); ax.set_title(K) if row == 0 else ax.set_xlabel(x); ax.grid(alpha=.3)
    axs[0, 0].legend(fontsize=8)
    fig.suptitle(title); fig.tight_layout(); fig.savefig(os.path.join(OUT, fname), dpi=200); plt.close(fig)


if __name__ == "__main__":
    say(f"runs loaded: {len(df)} from {RUNS}")
    say(df.groupby("proto").size().to_string())
    regime()
    ablation()
    compare_vs_aodv("E1", ALL5, ["K", "N"]); lines("E1", "N", "E1 density (L = 80 packets/s)", "E1_density.png", ALL5)
    compare_vs_aodv("E3", ALL5, ["K", "L"]); lines("E3", "L", "E3 total load (30 UAVs)", "E3_load.png", ALL5)
    energy()
    compare_vs_aodv("E6a", ["AODV", "NBQ-MAODV", "SA-QMAODV"], ["K"])
    compare_vs_aodv("E6b", ["AODV", "NBQ-MAODV", "SA-QMAODV"], ["K", "N"])
    robustness()
    with open(os.path.join(OUT, "report.txt"), "w") as f:
        f.write("\n".join(REPORT) + "\n")
    print(f"\ntables, figures and report.txt written to {OUT}")
