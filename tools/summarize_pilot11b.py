"""Summarise the Step-11b pilot (AODV only)."""
import sys, os, glob, re, statistics as st, collections
D = sys.argv[1]
def load(path):
    txt = open(path).read()
    csv = [l for l in txt.splitlines() if re.match(r"^[A-Z-]+,\d+,", l)]
    met = [l for l in txt.splitlines() if l.startswith("# METRICS")]
    win = [dict(kv.split("=") for kv in l[6:].split()) for l in txt.splitlines() if l.startswith("# WIN")]
    r = dict(err=bool(re.search(r"died with|NS_FATAL|msg=", txt)) or not csv, win=win)
    if csv:
        f = csv[-1].split(","); r.update(pdr=float(f[7]), nrl=float(f[11]))
    if met:
        r.update({k: v for k, v in (kv.split("=") for kv in met[-1][10:].split())})
    return r
R = {os.path.basename(p)[:-4]: load(p) for p in glob.glob(os.path.join(D, "*.txt"))}
m = lambda xs: st.mean(xs) if xs else float("nan")
def grp(prefix):
    g = collections.defaultdict(list)
    for k, v in R.items():
        if k.startswith(prefix) and not v["err"]:
            g[k.rsplit("_s", 1)[0]].append(v)
    return g
def row(k, vs):
    f = lambda key: m([float(v[key]) for v in vs])
    return (f"  {k:14s} PDR {m([v['pdr'] for v in vs]):5.1f} | med/p95 {f('delayMedMs'):6.1f}/{f('delayP95Ms'):6.1f} ms"
            f" | NRL {m([v['nrl'] for v in vs]):5.2f} | ack {f('macAckRatio'):.3f} | nb {f('avgNeighbours'):4.2f}"
            f" | distBs {f('avgDistBs'):5.0f} | rreq {f('rreq'):6.0f} rerr {f('rerr'):5.0f}")
print("=== P6 density at constant total load 80 pkt/s (AODV, gm)")
for k in ("K0", "K1", "K2"):
    for n in (20, 30, 40):
        vs = grp("P6_").get(f"P6_{k}_n{n}")
        if vs: print(row(f"{k} N={n}", vs))
print("\n=== P7 total load at 30 UAVs (AODV, gm)   [L = 80 is P6 N=30]")
for k in ("K0", "K1", "K2"):
    for L in (40, 80, 160, 320):
        vs = grp("P6_").get(f"P6_{k}_n30") if L == 80 else grp("P7_").get(f"P7_{k}_L{L}")
        if vs: print(row(f"{k} L={L}", vs))
print("\n=== P8 stationarity (AODV, 30 UAV, K0, 80 pkt/s): per 60-s block  PDR% | mean distance to BS (m) | neighbours")
for mob in ("rwp", "gm"):
    runs = [v for k, v in R.items() if k.startswith(f"P8_{mob}_") and not v["err"]]
    if not runs: continue
    nw = min(len(r["win"]) for r in runs); out = []
    for w in range(2, nw, 2):
        pdrs, ds, nbs = [], [], []
        for r in runs:
            a, b = r["win"][w - 2], r["win"][w]
            dtx = int(b["tx"]) - int(a["tx"]); drx = int(b["rx"]) - int(a["rx"])
            if dtx > 0: pdrs.append(100 * drx / dtx)
            ds.append(float(b["distBs"])); nbs.append(float(b["nb"]))
        out.append(f"{float(runs[0]['win'][w]['t']):.0f}s:{m(pdrs):.0f}%/{m(ds):.0f}m/{m(nbs):.1f}")
    print(f"  {mob}: " + "  ".join(out))
bad = [k for k, v in R.items() if v["err"]]
print(f"\nruns: {len(R)} (expected 60), errors: {len(bad)}", *bad, sep="\n  ")
