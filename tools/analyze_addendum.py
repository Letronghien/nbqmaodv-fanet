#!/usr/bin/env python3
"""analyze_addendum.py MAIN_RUNS.csv ADDENDUM_RUNS.csv -- post-hoc analyses A1, A1b, A2, A3."""
import sys, numpy as np, pandas as pd
from scipy import stats
m = pd.read_csv(sys.argv[1]); a = pd.read_csv(sys.argv[2])
m = m[(m.area == 1000) & (m.bs == "center") & (~m.energy.astype(bool)) & (m.sim == 300)]
df = pd.concat([m, a], ignore_index=True).drop_duplicates(subset=["key"])
KS = ["K0", "K1", "K2"]


def holm(p):
    p = np.asarray(p, float); o = np.argsort(p); adj = np.empty(len(p)); run = 0
    for i, j in enumerate(o):
        run = max(run, (len(p) - i) * p[j]); adj[j] = min(1, run)
    return adj


def paired(sub, ref, cmp, cols, metric="pdr"):
    rows = []
    for cond, g in sub.groupby(cols):
        x = g[g.proto == ref].set_index("seed")[metric]; y = g[g.proto == cmp].set_index("seed")[metric]
        s = x.index.intersection(y.index)
        if len(s) < 2: continue
        d = (y[s] - x[s]).astype(float)
        p = stats.wilcoxon(y[s], x[s]).pvalue if (d != 0).any() else 1.0
        rows.append(dict(zip(cols, cond if isinstance(cond, tuple) else (cond,)), ref=ref, cmp=cmp, n=len(s),
                         diff=d.mean(), p=p))
    r = pd.DataFrame(rows)
    return r


def show(title, r, cols):
    if r.empty:
        print(f"\n{title}: no data"); return
    r = r.copy(); r["p_holm"] = holm(r.p.values)
    r["cell"] = r.apply(lambda x: f"{x['diff']:+5.1f}{'*' if x['p_holm'] < .05 else ' '}", axis=1)
    print(f"\n{title}  (* Holm p < 0.05)")
    print(r.pivot_table(index=cols, columns="cmp", values="cell", aggfunc="first").to_string())
    return r


grid = df[(df.K.isin(KS)) & (df.proto.isin(["AODV", "NBQ-MAODV", "NBQ-onair"]))]
r1 = show("[A1] NBQ-onair - AODV on the E2 grid", paired(grid, "AODV", "NBQ-onair", ["K", "N", "L"]), ["K", "N", "L"])
if r1 is not None and not r1.empty:
    r1["regime"] = np.where(r1.p_holm < .05, np.where(r1["diff"] > 0, "NBQ better", "AODV better"), "equivalent")
    print("\n[A1] regime counts (NBQ-onair vs AODV)"); print(r1.groupby(["K", "regime"]).size().unstack(fill_value=0).to_string())
    c = paired(grid, "NBQ-MAODV", "NBQ-onair", ["K", "N", "L"])  # paired per cell, then averaged
    print("\n[A1] cost of the tags on air: NBQ-onair - NBQ-MAODV (PDR points; mean, min, max over the 12 cells)")
    print(c.groupby("K")["diff"].agg(["mean", "min", "max"]).round(2).to_string())
e3 = df[(df.N == 30) & (df.K.isin(KS))]
rb = pd.concat([paired(e3[e3.L.isin([80, 320])], p, p + "-onair" if p != "SA-QMAODV" else "SA-onair", ["K", "L"])
                for p in ("PMAODV", "QMAODV", "SA-QMAODV")], ignore_index=True)
show("[A1b] cost of the tags for the other learners (onair - free)", rb, ["K", "L"])
r2 = pd.concat([paired(e3, "AODV", "LIU-QAODV", ["K", "L"]), paired(e3, "NBQ-onair", "LIU-QAODV", ["K", "L"]),
                paired(e3, "AODV", "NBQ-onair", ["K", "L"])], ignore_index=True)
r2["cmp"] = r2["cmp"] + " vs " + r2["ref"]
show("[A2] external baseline (Liu et al. 2026), 30 UAVs", r2, ["K", "L"])
k2h = df[df.K == "K2h"]
r3 = pd.concat([paired(k2h, "AODV", "NBQ-onair", ["N", "L"]), paired(k2h, "AODV", "LIU-QAODV", ["N", "L"])], ignore_index=True)
show("[A3] K2 at +3 dBm (higher operating point)", r3, ["N", "L"])
if not k2h.empty:
    print("\n[A3] mean PDR on K2h"); print(k2h.groupby(["N", "L", "proto"]).pdr.mean().unstack().round(1).to_string())
