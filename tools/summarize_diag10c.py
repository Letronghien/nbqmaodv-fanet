"""Summarise diag_step10c: per (channel, load) mean PDR, per-seed PDR, paired dPDR vs AODV."""
import sys, statistics as st, collections, math
R = collections.defaultdict(dict); errs = []
for line in open(sys.argv[1]):
    f = line.strip().split(",")
    if len(f) < 6: continue
    name, chn, rate, s, err = f[:5]; csv = f[5:]
    if err != "OK" or csv[0] == "NOCSV": errs.append(line.strip()); continue
    R[(chn, rate, name)][s] = dict(pdr=float(csv[7]), delay=float(csv[8]), nrl=float(csv[11]))
def tp(d):
    if len(d) < 2 or st.stdev(d) == 0: return float("nan")
    return st.mean(d) / (st.stdev(d) / math.sqrt(len(d)))
order = ["AODV", "PMAODV", "QMAODV", "SA-QMAODV", "NBQ-MAODV"]
for chn in ("range", "fading"):
    for rate in ("4", "12"):
        base = R.get((chn, rate, "AODV"), {})
        if not base: continue
        print(f"\n=== channel={chn}, {rate} pkt/s, 20 UAVs, tuning seeds 101-103")
        print(f"{'protocol':10s} {'PDR% mean':>9s} {'per seed':>20s} {'dPDR vs AODV':>12s} {'per-seed d':>20s} {'t':>6s} {'delay':>7s} {'NRL':>5s}")
        for name in order:
            d = R.get((chn, rate, name), {})
            if not d: continue
            ss = sorted(d); pdr = [d[s]["pdr"] for s in ss]
            diffs = [d[s]["pdr"] - base[s]["pdr"] for s in ss if s in base]
            isb = name == "AODV"
            print(f"{name:10s} {st.mean(pdr):9.2f} {' / '.join(f'{x:.1f}' for x in pdr):>20s}"
                  f" {0 if isb else st.mean(diffs):+12.2f} {'' if isb else ' / '.join(f'{x:+.1f}' for x in diffs):>20s}"
                  f" {float('nan') if isb else tp(diffs):6.2f} {st.mean(d[s]['delay'] for s in ss):7.1f} {st.mean(d[s]['nrl'] for s in ss):5.2f}")
print(f"\nerrors: {len(errs)}"); [print("  ", e) for e in errs]
