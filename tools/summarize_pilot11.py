"""Summarise the Step-11 pilot (AODV only)."""
import sys, os, glob, re, statistics as st, collections
D = sys.argv[1]
def load(path):
    txt = open(path).read()
    err = re.search(r"died with|NS_FATAL|msg=", txt)
    csv = [l for l in txt.splitlines() if re.match(r"^[A-Z-]+,\d+,", l)]
    met = [l for l in txt.splitlines() if l.startswith("# METRICS")]
    win = [dict(kv.split("=") for kv in l[6:].split()) for l in txt.splitlines() if l.startswith("# WIN")]
    r = dict(err=bool(err) or not csv, win=win)
    if csv:
        f = csv[-1].split(","); r.update(pdr=float(f[7]), delay=float(f[8]), nrl=float(f[11]), dead=int(f[12]), first=float(f[13]))
    if met:
        r.update({k: v for k, v in (kv.split("=") for kv in met[-1][10:].split())})
    return r
R = {os.path.basename(p)[:-4]: load(p) for p in glob.glob(os.path.join(D, "*.txt"))}
bad = [k for k, v in R.items() if v["err"]]
m = lambda xs: st.mean(xs) if xs else float("nan")
def grp(prefix):
    g = collections.defaultdict(list)
    for k, v in R.items():
        if k.startswith(prefix) and not v["err"]:
            g[k.rsplit("_s", 1)[0]].append(v)
    return g
print("=== P1 stationarity (AODV, 30 UAV, 4 pkt/s, range): PDR per 30-s window, mean of seeds")
for mob in ("rwp", "gm"):
    runs = [v for k, v in R.items() if k.startswith(f"P1_{mob}_") and not v["err"]]
    if not runs: continue
    rows = []
    for w in range(1, min(len(r["win"]) for r in runs)):
        vals = []
        for r in runs:
            a, b = r["win"][w - 1], r["win"][w]
            dtx = int(b["tx"]) - int(a["tx"]); drx = int(b["rx"]) - int(a["rx"])
            if dtx > 0: vals.append(100 * drx / dtx)
        rows.append((float(runs[0]["win"][w]["t"]), m(vals)))
    print(f"  {mob}: " + "  ".join(f"{t:.0f}s:{p:.0f}" for t, p in rows))
print("\n=== P2 load (AODV, gm, 30 UAV, warm-up 60 s)   PDR% | pdrAlive | delay med/p95 ms | NRL | macAck | queue")
for k, vs in sorted(grp("P2_").items(), key=lambda kv: (kv[0].split("_")[1], int(kv[0].split("_r")[1]))):
    print(f"  {k:18s} {m([v['pdr'] for v in vs]):6.1f} {m([float(v['pdrAlive']) for v in vs]):6.1f}"
          f" {m([float(v['delayMedMs']) for v in vs]):7.1f}/{m([float(v['delayP95Ms']) for v in vs]):7.1f}"
          f" {m([v['nrl'] for v in vs]):5.2f} {m([float(v['macAckRatio']) for v in vs]):5.3f} {m([float(v['avgMacQueue']) for v in vs]):6.2f}")
print("\n=== P3 density (AODV, gm, 4 pkt/s)   PDR% | neighbours | NRL")
for k, vs in sorted(grp("P3_").items()):
    print(f"  {k:18s} {m([v['pdr'] for v in vs]):6.1f} {m([float(v['avgNeighbours']) for v in vs]):6.2f} {m([v['nrl'] for v in vs]):5.2f}")
print("\n=== P4 base station at the edge (AODV, gm, 30 UAV, 4 pkt/s)   PDR% | delay med ms | NRL")
for k, vs in sorted(grp("P4_").items()):
    print(f"  {k:18s} {m([v['pdr'] for v in vs]):6.1f} {m([float(v['delayMedMs']) for v in vs]):7.1f} {m([v['nrl'] for v in vs]):5.2f}")
print("\n=== P5 energy (AODV, gm, fading, 30 UAV, 280 J x U[0.5,1])   dead | first death s | PDR% | pdrAlive")
for k, vs in sorted(grp("P5_").items()):
    print(f"  {k:18s} {m([v['dead'] for v in vs]):5.1f} {m([v['first'] for v in vs]):7.1f} {m([v['pdr'] for v in vs]):6.1f} {m([float(v['pdrAlive']) for v in vs]):6.1f}")
print(f"\nruns: {len(R)} (expected 57), errors: {len(bad)}", *bad, sep="\n  ")
