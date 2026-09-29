#!/usr/bin/env bash
# Step 11b channel calibration: link curves for K1 (Nakagami m=10) and K2 (m profile 3/2/1.5)
# at several Tx powers; then tools/reff.py computes R_eff and the Tx power giving R_eff = 250 m.
# Usage: cd ~/nbqmaodv-fanet/ns-3-nbq && bash ~/nbqmaodv-repo/tools/calib_step11b.sh
set -u
OUT="${OUT:-$HOME/nbqmaodv-fanet/results/calib11b.txt}"; mkdir -p "$(dirname "$OUT")"; : > "$OUT"
B=$(ls build/scratch/*fanet-linkcal-optimized | head -1)
jobs=()
for p in -6 -4 -2 0; do jobs+=("$B --channel=fading --nakagamiM=10 --txPowerDbm=$p"); done
for p in -3 -2 -1 1; do jobs+=("$B --channel=fading --nakagamiM=0 --txPowerDbm=$p"); done
printf '%s\n' "${jobs[@]}" | xargs -P 8 -I{} bash -c 'nice -n 10 {} 2>&1 | grep -E "^#|^[0-9]"' > "$OUT"
python3 ~/nbqmaodv-repo/tools/reff.py "$OUT"
