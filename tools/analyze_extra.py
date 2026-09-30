#!/usr/bin/env python3
"""
analyze_extra.py -- Step 13a: analyses added after the frozen plan (reported as post-hoc).

    python3 ~/nbqmaodv-repo/tools/analyze_extra.py ~/nbqmaodv-fanet/results/main/runs.csv [outdir]

1. Control overhead (E3, 30 UAVs): NRL, control transmissions per second by type, per protocol/channel/load.
2. Estimated on-air cost of the information that the simulation carries in ns-3 packet tags
   (packet tags are NOT transmitted, so the simulated airtime does not include them):
     - control packets: NeighborInfoTag 4 B (SA-QMAODV, NBQ-MAODV) + QValueTag 1+8n B (NBQ-MAODV, n = 2)
     - data packets:    PrevHopTag 4 B per hop (all multipath variants)
   expressed relative to the on-air size of AODV control packets (~85 B incl. UDP/IP/LLC/MAC headers).
3. Effect sizes for NBQ-MAODV - AODV in E2: paired Cohen's d_z and relative PDR change.
4. PDF versions of the E1/E3 curves and the E2 regime maps.
"""
import math, os, sys
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(RUNS)), "analysis_extra")
os.makedirs(OUT, exist_ok=True)
df = pd.read_csv(RUNS)
df["exps"] = df["exps"].fillna("")
for c in ("rreq", "rrep", "rerr", "ctrl", "nrl", "pdr", "rx", "tx", "delayP95Ms", "sim", "warm"):
    if c in df:
        df[c] = pd.to_numeric(df[c], errors="coerce")
df["window"] = df["sim"] - df["warm"]
KS = ["K0", "K1", "K2"]
ALL5 = ["AODV", "PMAODV", "QMAODV", "SA-QMAODV", "NBQ-MAODV"]
REP = []


def say(*a):
    s = " ".join(str(x) for x in a); print(s); REP.append(s)


def exp(e):
    return df[df.exps.str.contains(fr"(?:^|;){e}(?:$|;)", regex=True)]


# ---------------------------------------------------------------- 1. overhead
e3 = exp("E3").copy()
if not e3.empty:
    for c in ("rreq", "rrep", "rerr", "ctrl"):
        e3[c + "_s"] = e3[c] / e3["window"]
    t = e3.groupby(["K", "L", "proto"])[["nrl", "ctrl_s", "rreq_s", "rrep_s", "rerr_s"]].mean().round(2)
    t.to_csv(os.path.join(OUT, "overhead_E3.csv"))
    say("[1] Control overhead, E3 (30 UAVs): mean NRL and control transmissions per second")
    for K in KS:
        say(f"\n  {K}")
        say(t.loc[K].reset_index().pivot(index="proto", columns="L", values="nrl").reindex(ALL5).round(2)
            .rename(columns=lambda L: f"NRL L={L}").to_string())
        say(t.loc[K].reset_index().pivot(index="proto", columns="L", values="ctrl_s").reindex(ALL5).round(0)
            .rename(columns=lambda L: f"ctrl/s L={L}").to_string())

# ---------------------------------------------------------------- 2. tag bytes
CTRL_ONAIR = 85.0     # approx. AODV control packet on air: 20-24 B AODV + 8 UDP + 20 IP + 8 LLC + 28 MAC/FCS
DATA_ONAIR = 576.0    # 512 B payload + 8 UDP + 20 IP + 8 LLC + 28 MAC/FCS
TAG_CTRL = {"AODV": 0, "PMAODV": 0, "QMAODV": 0, "SA-QMAODV": 4, "NBQ-MAODV": 4 + 1 + 8 * 2}
TAG_DATA = {"AODV": 0, "PMAODV": 4, "QMAODV": 4, "SA-QMAODV": 4, "NBQ-MAODV": 4}
say("\n[2] Information carried in packet tags (not on air in ns-3): estimated extra on-air bytes")
say(f"  assumed on-air sizes: control ~{CTRL_ONAIR:.0f} B, data ~{DATA_ONAIR:.0f} B")
rows = []
for p in ALL5:
    rows.append(dict(protocol=p, extra_B_per_ctrl=TAG_CTRL[p], ctrl_bytes_pct=100 * TAG_CTRL[p] / CTRL_ONAIR,
                     extra_B_per_data_hop=TAG_DATA[p], data_bytes_pct=100 * TAG_DATA[p] / DATA_ONAIR))
say(pd.DataFrame(rows).round(1).to_string(index=False))
if not e3.empty:
    # share of control bytes in (control + delivered-data) bytes, AODV-free estimate per cell (lower bound of hops)
    e3["ctrl_share"] = e3["ctrl"] * CTRL_ONAIR / (e3["ctrl"] * CTRL_ONAIR + e3["rx"] * DATA_ONAIR)
    s = e3[e3.proto == "NBQ-MAODV"].groupby(["K", "L"])["ctrl_share"].mean()
    say("\n  NBQ-MAODV: control bytes as a share of (control + delivered data) bytes, one hop per packet (lower bound for data):")
    say((100 * s).round(1).unstack("L").to_string())
    say("  -> the untransmitted QValueTag/NeighborInfoTag would add ~25 % to control bytes; where control dominates\n"
        "     (K2) this is a material, unmodelled cost. See the TagsOnAir sensitivity experiment (Step 13c).")

# ---------------------------------------------------------------- 3. effect sizes
e2 = exp("E2")
if not e2.empty:
    rows = []
    for (K, N, L), g in e2.groupby(["K", "N", "L"]):
        a = g[g.proto == "AODV"].set_index("seed")["pdr"]; b = g[g.proto == "NBQ-MAODV"].set_index("seed")["pdr"]
        s_ = a.index.intersection(b.index); d = (b[s_] - a[s_]).astype(float)
        dz = d.mean() / d.std(ddof=1) if d.std(ddof=1) > 0 else np.nan
        rows.append(dict(K=K, N=N, L=L, diff=d.mean(), rel_pct=100 * d.mean() / a[s_].mean(), d_z=dz,
                         frac_seeds_pos=(d > 0).mean()))
    es = pd.DataFrame(rows)
    es.to_csv(os.path.join(OUT, "effect_sizes_E2.csv"), index=False)
    say("\n[3] E2 effect sizes (NBQ-MAODV - AODV, PDR): paired Cohen's d_z, relative change, share of seeds with NBQ ahead")
    say(es.groupby("K")[["diff", "rel_pct", "d_z", "frac_seeds_pos"]].agg(["mean", "min", "max"]).round(2).to_string())

# ---------------------------------------------------------------- 4. PDF figures
def ci95(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else np.nan


def curves(e, x, fname):
    sub = exp(e)
    if sub.empty: return
    fig, axs = plt.subplots(2, 3, figsize=(10, 5.4), sharex=True)
    for col, K in enumerate(KS):
        for row, (m, lab) in enumerate((("pdr", "PDR (%)"), ("delayP95Ms", "95th-pct delay (ms)"))):
            ax = axs[row, col]
            for p in ALL5:
                g = sub[(sub.K == K) & (sub.proto == p)].groupby(x)[m]
                if g.ngroups:
                    ax.errorbar(g.mean().index, g.mean().values, yerr=g.agg(ci95).values, marker="o", ms=3, capsize=2, label=p)
            ax.grid(alpha=.3)
            if row == 0: ax.set_title(K)
            else: ax.set_xlabel("total load (packets/s)" if x == "L" else "UAVs")
            if col == 0: ax.set_ylabel(lab)
    axs[0, 0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, fname), bbox_inches="tight"); plt.close(fig)


curves("E3", "L", "E3_load.pdf"); curves("E1", "N", "E1_density.pdf")
if not e2.empty:
    for metric, title, cmap in (("pdr", "PDR: NBQ-MAODV − AODV (points)", "RdBu"),
                                ("delayP95Ms", "95th-pct delay: NBQ-MAODV − AODV (ms)", "RdBu_r")):
        fig, axs = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
        cells = {}
        for (K, N, L), g in e2.groupby(["K", "N", "L"]):
            a = g[g.proto == "AODV"].set_index("seed")[metric]; b = g[g.proto == "NBQ-MAODV"].set_index("seed")[metric]
            s_ = a.index.intersection(b.index); cells[(K, N, L)] = (b[s_] - a[s_]).mean()
        lim = max(abs(v) for v in cells.values() if not np.isnan(v))
        for ax, K in zip(axs, KS):
            Ns = sorted({k[1] for k in cells if k[0] == K}, reverse=True); Ls = sorted({k[2] for k in cells if k[0] == K})
            M = np.array([[cells.get((K, n, l), np.nan) for l in Ls] for n in Ns])
            im = ax.imshow(M, cmap=cmap, vmin=-lim, vmax=lim, aspect="auto")
            for i in range(len(Ns)):
                for j in range(len(Ls)):
                    ax.text(j, i, f"{M[i, j]:+.1f}", ha="center", va="center", fontsize=8)
            ax.set_xticks(range(len(Ls))); ax.set_xticklabels(Ls); ax.set_yticks(range(len(Ns))); ax.set_yticklabels(Ns)
            ax.set_title(K); ax.set_xlabel("total load (packets/s)")
        axs[0].set_ylabel("UAVs"); fig.suptitle(title + " (significance: see Table 5)", fontsize=9)
        fig.colorbar(im, ax=axs, shrink=.8)
        fig.savefig(os.path.join(OUT, f"E2_regime_{metric}.pdf"), bbox_inches="tight"); plt.close(fig)

with open(os.path.join(OUT, "report_extra.txt"), "w") as f:
    f.write("\n".join(REP) + "\n")
print(f"\nwritten to {OUT}")
