"""Summarise diag_step10b output: mean per config and paired difference vs AODV (same seed)."""
import sys, statistics as st, collections, math
R = collections.defaultdict(dict); errs = []
for line in open(sys.argv[1]):
    f = line.strip().split(",")
    if len(f) < 5: continue
    name, T, s, err = f[:4]; csv = f[4:]
    if err != "OK" or csv[0] == "NOCSV": errs.append(line.strip()); continue
    R[(T, name)][s] = dict(pdr=float(csv[7]), delay=float(csv[8]), nrl=float(csv[11]))
def tp(d):  # paired t statistic
    if len(d) < 2 or st.stdev(d) == 0: return float("nan")
    return st.mean(d) / (st.stdev(d) / math.sqrt(len(d)))
order = ["AODV", "NBQ", "NBQ-lowEps", "NBQ-srcOnly", "NBQ-lowEps-srcOnly"]
for T in ("60", "200"):
    print(f"\n=== simTime {T} s, 12 pkt/s, tuning seeds 101-103")
    print(f"{'config':20s} {'PDR% mean':>10s} {'per seed':>22s} {'dPDR vs AODV':>13s} {'t':>6s} {'delay ms':>9s} {'NRL':>6s}")
    base = R.get((T, "AODV"), {})
    for name in order:
        d = R.get((T, name), {})
        if not d: continue
        seeds = sorted(d)
        pdr = [d[s]["pdr"] for s in seeds]
        diffs = [d[s]["pdr"] - base[s]["pdr"] for s in seeds if s in base]
        print(f"{name:20s} {st.mean(pdr):10.2f} {' / '.join(f'{x:.1f}' for x in pdr):>22s}"
              f" {st.mean(diffs) if diffs and name != 'AODV' else 0:+13.2f} {tp(diffs) if name != 'AODV' else float('nan'):6.2f}"
              f" {st.mean(d[s]['delay'] for s in seeds):9.1f} {st.mean(d[s]['nrl'] for s in seeds):6.2f}")
print(f"\nerrors: {len(errs)}"); [print("  ", e) for e in errs]
