#!/usr/bin/env bash
# Step 9 verification matrix: 5 protocols x 3 seeds x 2 configurations (no energy / 150 J).
# Usage:  cd ~/nbqmaodv-fanet/ns-3-nbq && bash ~/nbqmaodv-repo/tools/verify_step9.sh [WORKERS]
set -u
W="${1:-4}"; OUT="${OUT:-$HOME/nbqmaodv-fanet/results/verify_step9.txt}"
mkdir -p "$(dirname "$OUT")"; : > "$OUT"
bin(){ ls build/scratch/*fanet-scenario-$1-optimized 2>/dev/null | head -1; }
jobs=()
for cfg in noE E150; do for s in 1 2 3; do
  for pm in AODV:aodv PMAODV:qmaodv QMAODV:qmaodv SA-QMAODV:saqmaodv NBQ-MAODV:nbqmaodv; do
    p="${pm%%:*}"; m="${pm##*:}"; b=$(bin "$m"); [ -z "$b" ] && { echo "missing binary for $m"; exit 1; }
    extra=""; [ "$cfg" = E150 ] && extra="--energyJ=150 --energyDebug=1"
    jobs+=("$cfg|$p|$s|$b --protocol=$p --nUav=20 --rate=4 --simTime=200 --run=$s $extra")
  done; done; done
echo "running ${#jobs[@]} simulations with $W workers -> $OUT"
run1(){ IFS='|' read -r cfg p s cmd <<< "$1"
  out=$(nice -n 10 $cmd 2>&1); rc=$?
  csv=$(echo "$out" | grep -E "^[A-Z-]+,[0-9]+," | tail -1)
  fr=$(echo "$out" | grep "ALL avgRemainFrac" | tail -1 | sed -n 's/.*avgFracAtDeath=\([-0-9.e]*\).*/\1/p')
  err=$(echo "$out" | grep -E "died with|NS_FATAL|msg=|Segmentation" | head -1 | tr ',' ';')
  echo "$cfg,$s,$rc,${fr:-NA},${err:-OK},${csv:-NOCSV}"; }
export -f run1
printf '%s\n' "${jobs[@]}" | xargs -P "$W" -I{} bash -c 'run1 "$@"' _ {} >> "$OUT"
echo "done: $(wc -l < "$OUT") lines"; python3 ~/nbqmaodv-repo/tools/summarize_verify.py "$OUT"
