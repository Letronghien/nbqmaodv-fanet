#!/usr/bin/env bash
# Step 11b pilot -- AODV ONLY, tuning seeds 101-103, Gauss-Markov, 300 s, warm-up 60 s.
#   P6 density at constant total load (80 pkt/s) on K0/K1/K2
#   P7 total-load sweep (40/80/160/320 pkt/s) at 30 UAVs on K0/K1/K2
#   P8 stationarity diagnostics (600 s, window 30 s, distance to BS + neighbours), K0, rwp and gm
# Usage: cd ~/nbqmaodv-fanet/ns-3-nbq && K1TX=<dBm> K2TX=<dBm> bash ~/nbqmaodv-repo/tools/pilot_step11b.sh [WORKERS]
set -u
W="${1:-8}"; : "${K1TX:?set K1TX from calib}"; : "${K2TX:?set K2TX from calib}"
D="${OUT:-$HOME/nbqmaodv-fanet/results/pilot11b}"; mkdir -p "$D"
B=$(ls build/scratch/*fanet-scenario-aodv-optimized | head -1)
C="$B --protocol=AODV --mobility=gm --simTime=300 --warmup=60"
ch(){ case $1 in K0) echo "--channel=range";; K1) echo "--channel=fading --nakagamiM=10 --txPowerDbm=$K1TX";;
                 K2) echo "--channel=fading --nakagamiM=0 --txPowerDbm=$K2TX";; esac; }
jobs=()
for s in 101 102 103; do
  for k in K0 K1 K2; do
    for n in 20 30 40; do jobs+=("P6_${k}_n${n}_s$s|$C $(ch $k) --nUav=$n --totalLoad=80 --run=$s"); done
    for L in 40 160 320; do jobs+=("P7_${k}_L${L}_s$s|$C $(ch $k) --nUav=30 --totalLoad=$L --run=$s"); done
  done
  for m in rwp gm; do
    jobs+=("P8_${m}_s$s|$B --protocol=AODV --mobility=$m --nUav=30 --totalLoad=80 --simTime=600 --windowReport=30 --run=$s"); done
done
echo "running ${#jobs[@]} simulations with $W workers (K1 Tx=$K1TX dBm, K2 Tx=$K2TX dBm) -> $D"
run1(){ IFS='|' read -r name cmd <<< "$1"; nice -n 10 $cmd > "$2/$name.txt" 2>&1; }
export -f run1
printf '%s\n' "${jobs[@]}" | xargs -P "$W" -I{} bash -c 'run1 "$@"' _ {} "$D"
python3 ~/nbqmaodv-repo/tools/summarize_pilot11b.py "$D"
