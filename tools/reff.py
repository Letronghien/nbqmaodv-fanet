"""R_eff of measured link curves: R_eff^2 = integral of p(d) * 2d dd (p = PHY frame success).
Groups curves by Nakagami m and returns the Tx power that gives R_eff = target (default 250 m)."""
import sys, re, math, collections
target = float(sys.argv[2]) if len(sys.argv) > 2 else 250.0
curves = collections.defaultdict(dict)  # (m) -> {tx: [(d, p)]}
cur = None
for line in open(sys.argv[1]):
    if line.startswith("# channel="):
        kv = dict(x.split("=") for x in line[2:].split())
        cur = (float(kv.get("nakagamiM", 0)), float(kv["txPowerDbm"]))
        curves[cur[0]][cur[1]] = []
    elif cur and re.match(r"^\d", line):
        d, fs, ad = line.strip().split(",")
        curves[cur[0]][cur[1]].append((float(d), float(fs)))
def reff(pts):
    pts = sorted(pts)
    xs = [0.0] + [d for d, _ in pts]; ps = [1.0] + [p for _, p in pts]
    xs.append(xs[-1] + 25); ps.append(0.0)              # beyond the last point: 0 (hard cut)
    acc = sum(0.5 * (ps[i] * 2 * xs[i] + ps[i + 1] * 2 * xs[i + 1]) * (xs[i + 1] - xs[i]) for i in range(len(xs) - 1))
    return math.sqrt(acc)
for m in sorted(curves):
    label = "K1 (m=%g)" % m if m > 0 else "K2 (m profile 3/2/1.5)"
    print(f"=== {label}")
    rows = []
    for tx in sorted(curves[m]):
        pts = curves[m][tx]
        r = reff(pts); rows.append((tx, r))
        d90 = next((d for d, p in sorted(pts) if p < 0.9), float("nan"))
        d50 = next((d for d, p in sorted(pts) if p < 0.5), float("nan"))
        print(f"  Tx {tx:+5.1f} dBm: R_eff = {r:5.1f} m | 90%-range {d90:4.0f} m | 50%-range {d50:4.0f} m | "
              + " ".join(f"{d:.0f}:{p:.2f}" for d, p in sorted(pts) if d % 50 == 0))
    # interpolate Tx for R_eff = target on 20*log10(R_eff) vs Tx (free space: slope ~1 dB per dB)
    rows.sort(key=lambda t: t[1])
    for (t1, r1), (t2, r2) in zip(rows, rows[1:]):
        if r1 <= target <= r2 and r2 > r1:
            a = (20 * math.log10(target) - 20 * math.log10(r1)) / (20 * math.log10(r2) - 20 * math.log10(r1))
            print(f"  -> Tx for R_eff = {target:.0f} m: {t1 + a * (t2 - t1):+.2f} dBm (interpolated between {t1:+g} and {t2:+g})")
            break
    else:
        print(f"  -> target {target:.0f} m outside measured range; extend the Tx sweep")
