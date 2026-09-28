import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
import json, os, sys
INFILE = sys.argv[1] if len(sys.argv) > 1 else "results_ns3.csv"
df = pd.read_csv(INFILE)
# public name of the fourth generation (internal simulator key: "SA-QMAODV+")
df["variant"] = df["variant"].str.replace("SA-QMAODV+", "NBQ-MAODV", regex=False)
os.makedirs("figs", exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.grid": True, "grid.alpha": .3,
                     "legend.fontsize": 7.5, "figure.dpi": 150})
PROTOS = [p for p in ["AODV", "AOMDV", "PMAODV", "QMAODV", "SA-QMAODV", "NBQ-MAODV"] if p in set(df.variant.str.split("|").str[0])]
STY = {"AODV": ("o", "--", "#7f7f7f"), "AOMDV": ("v", "--", "#bcbd22"), "PMAODV": ("s", "-.", "#1f77b4"),
       "QMAODV": ("^", ":", "#2ca02c"), "SA-QMAODV": ("D", "-", "#ff7f0e"), "NBQ-MAODV": ("*", "-", "#d62728")}
LAB = {"pdr": "Packet delivery ratio (%)", "delay_ms": "End-to-end delay (ms)", "nrl": "Normalised routing load",
       "thr_kbps": "Throughput (kbps)", "energy": "Energy consumed (units)", "hops": "Average hop count"}

LAB = {k: v for k, v in LAB.items() if k in df.columns}

def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 2: return np.nan
    return stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))

def agg(exp):
    d = df[df.exp == exp]
    g = d.groupby(["variant", "x"])
    out = g.agg(**{m: (m, "mean") for m in LAB}, n=("pdr", "size")).reset_index()
    for m in LAB:
        out[m + "_ci"] = g[m].apply(ci).values
    return out

def lineplot(exp, metrics, xlabel, fname):
    a = agg(exp)
    fig, axs = plt.subplots(1, len(metrics), figsize=(3.3 * len(metrics), 2.6))
    for ax, m in zip(np.atleast_1d(axs), metrics):
        for P in PROTOS:
            s = a[a.variant == P].sort_values("x")
            if s.empty: continue
            mk, ls, c = STY[P]
            ax.errorbar(s.x.astype(float), s[m], yerr=s[m + "_ci"], marker=mk, ls=ls, color=c, ms=4.5,
                        lw=1.2, capsize=2, label=P)
        ax.set_xlabel(xlabel); ax.set_ylabel(LAB[m])
    np.atleast_1d(axs)[0].legend(loc="best", ncol=2)
    fig.tight_layout(); fig.savefig("figs/" + fname, dpi=300); plt.close(fig)
    return a

summary = {}
if (df.exp == "E1_density").any():
    summary["E1"] = lineplot("E1_density", [m for m in ["pdr", "delay_ms", "nrl", "thr_kbps"] if m in LAB], "Number of UAVs", "fig2_density.png")
if (df.exp == "E2_speed").any():
    summary["E2"] = lineplot("E2_speed", [m for m in ["pdr", "delay_ms", "nrl"] if m in LAB], "Maximum UAV speed (m/s)", "fig3_speed.png")
if (df.exp == "E3_load").any():
    summary["E3"] = lineplot("E3_load", [m for m in ["pdr", "delay_ms", "thr_kbps"] if m in LAB], "Offered load per UAV (packets/s)", "fig4_load.png")

# paired Wilcoxon: SA-QMAODV+ and SA-QMAODV vs each baseline, per experiment x
def paired(exp, ref, metric):
    d = df[df.exp == exp]
    rows = []
    for x, dx in d.groupby("x"):
        p = dx.pivot_table(index="seed", columns="variant", values=metric)
        for b in PROTOS:
            if b == ref or b not in p or ref not in p: continue
            q = p[[ref, b]].dropna()
            diff = q[ref] - q[b]
            try:
                pv = stats.wilcoxon(q[ref], q[b]).pvalue if (diff != 0).any() else 1.0
            except ValueError:
                pv = 1.0
            rows.append(dict(exp=exp, x=x, ref=ref, vs=b, metric=metric, mean_diff=diff.mean(),
                             rel=100 * diff.mean() / q[b].mean(), p=pv, n=len(q)))
    return pd.DataFrame(rows)
tests = []
for exp in ["E1_density", "E2_speed", "E3_load", "E4_energy"]:
    if (df.exp == exp).any():
        for ref in ["NBQ-MAODV", "SA-QMAODV", "PMAODV"]:
            for m in ["pdr", "delay_ms", "nrl"]:
                tests.append(paired(exp, ref, m))
if tests:
    T = pd.concat(tests); T.to_csv("paired_tests.csv", index=False)

# energy experiment
if (df.exp == "E4_energy").any():
    d = df[df.exp == "E4_energy"]
    g = d.groupby("variant").agg(pdr=("pdr", "mean"), pdr_ci=("pdr", ci), delay=("delay_ms", "mean"),
                                 delay_ci=("delay_ms", ci), dead=("dead", "mean"), dead_ci=("dead", ci),
                                 fd=("first_death", "mean"), fd_ci=("first_death", ci), n=("pdr", "size")).reindex(PROTOS)
    g.to_csv("table_energy.csv")
    fig, axs = plt.subplots(1, 3, figsize=(9.9, 2.6))
    for ax, (m, lab) in zip(axs, [("pdr", "Packet delivery ratio (%)"), ("fd", "First node death (s)"), ("dead", "Depleted UAVs at 200 s")]):
        ax.bar(range(len(PROTOS)), g[m], yerr=g[m + "_ci"], color=[STY[p][2] for p in PROTOS], capsize=2)
        ax.set_xticks(range(len(PROTOS))); ax.set_xticklabels(PROTOS, rotation=35, ha="right", fontsize=7); ax.set_ylabel(lab)
    fig.tight_layout(); fig.savefig("figs/fig5_energy.png", dpi=300); plt.close(fig)

# ablation
abl = df[df.exp.str.startswith("E5")]
if len(abl):
    abl = abl.assign(base=abl.variant.str.split("|").str[0], comp=abl.variant.str.split("|").str[1])
    g = abl.groupby(["exp", "base", "comp"]).agg(pdr=("pdr", "mean"), pdr_ci=("pdr", ci), delay=("delay_ms", "mean"),
                                                  delay_ci=("delay_ms", ci), nrl=("nrl", "mean"), n=("pdr", "size")).reset_index()
    g.to_csv("table_ablation.csv", index=False)
    comps = ["SA-full", "SA-noEps", "SA-noAlpha", "SA-noReward"]
    exps = [e for e in ["E5_ablation_r4", "E5_ablation_r12"] if (g.exp == e).any()]
    fig, axs = plt.subplots(1, len(exps), figsize=(3.6 * len(exps), 2.7), squeeze=False)
    axs = axs[0]
    for ax, exp in zip(axs, exps):
        for k, base in enumerate([b for b in ["SA-QMAODV", "NBQ-MAODV"] if (g.base == b).any()]):
            s = g[(g.exp == exp) & (g.base == base)].set_index("comp").reindex(comps)
            ax.bar(np.arange(4) + (k - .5) * .38, s.pdr, .38, yerr=s.pdr_ci, capsize=2, color=STY[base][2], label=base)
        ax.set_xticks(range(4)); ax.set_xticklabels(["full", "no adapt. \u03b5", "no adapt. \u03b1", "no adapt. reward"], fontsize=7.5)
        ax.set_ylabel("PDR (%)"); ax.set_title("load %s pkt/s per UAV" % exp[-1 if exp.endswith("4") else -2:], fontsize=8.5)
        lo = s.pdr.min(); ax.set_ylim(max(0, g[g.exp == exp].pdr.min() - 4), g[g.exp == exp].pdr.max() + 3)
    axs[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig("figs/fig6_ablation.png", dpi=300); plt.close(fig)

# sensitivity
sens = df[df.exp.isin(["E6_lambda", "E6_K"])]
if len(sens):
    g = sens.groupby(["exp", "variant", "x"]).agg(pdr=("pdr", "mean"), pdr_ci=("pdr", ci), delay=("delay_ms", "mean"),
                                                   delay_ci=("delay_ms", ci), nrl=("nrl", "mean"), n=("pdr", "size")).reset_index()
    g.to_csv("table_sensitivity.csv", index=False)

for k, a in summary.items():
    a.to_csv(f"table_{k}.csv", index=False)
print(df.groupby("exp").size())
