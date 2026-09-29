#!/usr/bin/env bash
# Step 10c: all five protocols, two channels, two loads, TUNING seeds 101-103, 120 s.
# Usage: cd ~/nbqmaodv-fanet/ns-3-nbq && TXDBM=0 bash ~/nbqmaodv-repo/tools/diag_step10c.sh [WORKERS]
set -u
W="${1:-8}"; TXDBM="${TXDBM:-0}"; T="${SIMTIME:-120}"
OUT="${OUT:-$HOME/nbqmaodv-fanet/results/diag_step10c.txt}"; mkdir -p "$(dirname "$OUT")"; : > "$OUT"
bin(){ ls build/scratch/*fanet-scenario-$1-optimized 2>/dev/null | head -1; }
declare -a CFG=("AODV|aodv|AODV" "PMAODV|qmaodv|PMAODV" "QMAODV|qmaodv|QMAODV" "SA-QMAODV|saqmaodv|SA-QMAODV" "NBQ-MAODV|nbqmaodv|NBQ-MAODV")
jobs=()
for chn in range fading; do for rate in 4 12; do for s in 101 102 103; do for c in "${CFG[@]}"; do
  IFS='|' read -r name m p <<< "$c"; b=$(bin "$m"); [ -z "$b" ] && { echo "missing $m"; exit 1; }
  cmd="$b --protocol=$p --nUav=20 --rate=$rate --simTime=$T --run=$s --channel=$chn"
  [ "$chn" = fading ] && cmd="$cmd --txPowerDbm=$TXDBM"
  jobs+=("$name|$chn|$rate|$s|$cmd")
done; done; done; done
echo "running ${#jobs[@]} simulations with $W workers (fading txPower=$TXDBM dBm, $T s) -> $OUT"
run1(){ IFS='|' read -r name chn rate s cmd <<< "$1"
  out=$(nice -n 10 $cmd 2>&1); csv=$(echo "$out" | grep -E "^[A-Z-]+,[0-9]+," | tail -1)
  err=$(echo "$out" | grep -E "died with|NS_FATAL|msg=" | head -1 | tr ',' ';')
  echo "$name,$chn,$rate,$s,${err:-OK},${csv:-NOCSV}"; }
export -f run1
printf '%s\n' "${jobs[@]}" | xargs -P "$W" -I{} bash -c 'run1 "$@"' _ {} >> "$OUT"
python3 ~/nbqmaodv-repo/tools/summarize_diag10c.py "$OUT"
