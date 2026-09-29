"""Summarise tools/verify_step9.sh output and flag anomalies."""
import sys, statistics as st, collections
rows = []
for line in open(sys.argv[1]):
    f = line.strip().split(",")
    if len(f) < 6: continue
    cfg, seed, rc, frac, err = f[:5]; csv = f[5:]
    r = dict(cfg=cfg, seed=seed, rc=rc, frac=frac, err=err, ok=(csv[0] != "NOCSV"))
    if r["ok"]:
        r.update(proto=csv[0], tx=int(csv[5]), rx=int(csv[6]), pdr=float(csv[7]), delay=float(csv[8]),
                 thr=float(csv[9]), ctrl=int(csv[10]), nrl=float(csv[11]),
                 dead=int(csv[12]) if len(csv) > 12 else 0, first=float(csv[13]) if len(csv) > 13 else float("nan"))
    rows.append(r)
flags = []
bad = [r for r in rows if not r["ok"] or r["err"] != "OK" or r["rc"] != "0"]
for r in bad: flags.append(f"CRASH/ERROR cfg={r['cfg']} seed={r['seed']} rc={r['rc']} {r['err']}")
good = [r for r in rows if r["ok"]]
g = collections.defaultdict(list)
for r in good: g[(r["cfg"], r["proto"])].append(r)
m = lambda xs: st.mean(xs) if xs else float("nan")
sd = lambda xs: st.stdev(xs) if len(xs) > 1 else 0.0
print(f"{'cfg':5s} {'protocol':10s} {'n':>2s} {'PDR%':>12s} {'delay ms':>14s} {'NRL':>10s} {'dead':>5s} {'1st death':>9s} {'frac@death':>10s}")
for (cfg, p), rs in sorted(g.items()):
    pdr = [r["pdr"] for r in rs]; d = [r["delay"] for r in rs]; nrl = [r["nrl"] for r in rs]
    fr = [float(r["frac"]) for r in rs if r["frac"] not in ("NA", "-1")]
    print(f"{cfg:5s} {p:10s} {len(rs):2d} {m(pdr):6.2f}±{sd(pdr):4.2f} {m(d):7.1f}±{sd(d):5.1f} {m(nrl):5.2f}±{sd(nrl):3.2f}"
          f" {m([r['dead'] for r in rs]):5.1f} {m([r['first'] for r in rs]):9.1f} {m(fr) if fr else float('nan'):10.3f}")
    for r in rs:
        if r["rx"] > r["tx"]: flags.append(f"rx>tx {cfg} {p} seed {r['seed']}")
        if cfg == "noE" and r["dead"] != 0: flags.append(f"deaths without energy model {p} seed {r['seed']}")
    if cfg == "E150" and fr and abs(m(fr) - 0.10) > 0.02: flags.append(f"{p}: UAVs die at {m(fr):.3f} of battery, expected ~0.10")
    if cfg == "E150" and m([r['dead'] for r in rs]) == 0: flags.append(f"{p}: no UAV died with 150 J / 200 s")
# NBQ-MAODV must equal SA-QMAODV (still a copy)
for cfg in ("noE", "E150"):
    for s in ("1", "2", "3"):
        a = [r for r in good if r["cfg"] == cfg and r["seed"] == s and r["proto"] == "SA-QMAODV"]
        b = [r for r in good if r["cfg"] == cfg and r["seed"] == s and r["proto"] == "NBQ-MAODV"]
        if a and b and (a[0]["rx"], a[0]["ctrl"]) != (b[0]["rx"], b[0]["ctrl"]):
            flags.append(f"NBQ-MAODV != SA-QMAODV ({cfg}, seed {s}) although nbqmaodv is still a copy")
expected = 30
print(f"\nruns: {len(good)} ok / {len(rows)} lines / {expected} expected")
print("FLAGS:" if flags else "FLAGS: none"); [print("  -", x) for x in flags]
