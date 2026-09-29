#!/usr/bin/env bash
# Step 10b diagnostics on TUNING seeds (101-103), never on the evaluation seeds (1-20).
# Usage: cd ~/nbqmaodv-fanet/ns-3-nbq && bash ~/nbqmaodv-repo/tools/diag_step10b.sh [WORKERS]
set -u
W="${1:-4}"; OUT="${OUT:-$HOME/nbqmaodv-fanet/results/diag_step10b.txt}"
mkdir -p "$(dirname "$OUT")"; : > "$OUT"
bin(){ ls build/scratch/*fanet-scenario-$1-optimized 2>/dev/null | head -1; }
A=$(bin aodv); N=$(bin nbqmaodv)
LOW="Epsilon0=0.1;EpsilonMin=0.02"
declare -a CFG=(
  "AODV|$A|AODV|"
  "NBQ|$N|NBQ-MAODV|"
  "NBQ-lowEps|$N|NBQ-MAODV|$LOW"
  "NBQ-srcOnly|$N|NBQ-MAODV|HopByHop=false"
  "NBQ-lowEps-srcOnly|$N|NBQ-MAODV|$LOW;HopByHop=false"
)
jobs=()
for T in 60 200; do for s in 101 102 103; do for c in "${CFG[@]}"; do
  IFS='|' read -r name b p attrs <<< "$c"
  cmd="$b --protocol=$p --nUav=20 --rate=12 --simTime=$T --run=$s"
  [ -n "$attrs" ] && cmd="$cmd --routingAttrs=$attrs"
  jobs+=("$name|$T|$s|$cmd")
done; done; done
echo "running ${#jobs[@]} simulations with $W workers -> $OUT"
run1(){ IFS='|' read -r name T s cmd <<< "$1"
  out=$(nice -n 10 $cmd 2>&1); csv=$(echo "$out" | grep -E "^[A-Z-]+,[0-9]+," | tail -1)
  err=$(echo "$out" | grep -E "died with|NS_FATAL|msg=" | head -1 | tr ',' ';')
  echo "$name,$T,$s,${err:-OK},${csv:-NOCSV}"; }
export -f run1
printf '%s\n' "${jobs[@]}" | xargs -P "$W" -I{} bash -c 'run1 "$@"' _ {} >> "$OUT"
python3 ~/nbqmaodv-repo/tools/summarize_diag.py "$OUT"
