#!/usr/bin/env bash
# Step 11 pilot -- AODV ONLY, tuning seeds 101-103. Used to fix the scenario (warm-up, load range,
# density, energy budget) BEFORE the main experiments; never used to tune NBQ-MAODV.
# Usage: cd ~/nbqmaodv-fanet/ns-3-nbq && bash ~/nbqmaodv-repo/tools/pilot_step11.sh [WORKERS]
set -u
W="${1:-8}"; D="${OUT:-$HOME/nbqmaodv-fanet/results/pilot11}"; mkdir -p "$D"
B=$(ls build/scratch/*fanet-scenario-aodv-optimized | head -1)
C="$B --protocol=AODV --mobility=gm"
jobs=()
for s in 101 102 103; do
  for m in rwp gm; do   # P1 stationarity: 600 s, cumulative counters every 30 s
    jobs+=("P1_${m}_s$s|$B --protocol=AODV --mobility=$m --nUav=30 --rate=4 --simTime=600 --windowReport=30 --run=$s"); done
  for ch in range fading; do
    for r in 2 4 8 12 16; do  # P2 load
      jobs+=("P2_${ch}_r${r}_s$s|$C --channel=$ch --txPowerDbm=-1 --nUav=30 --rate=$r --simTime=300 --warmup=60 --run=$s"); done
    for n in 20 40; do        # P3 density (30 is in P2)
      jobs+=("P3_${ch}_n${n}_s$s|$C --channel=$ch --txPowerDbm=-1 --nUav=$n --rate=4 --simTime=300 --warmup=60 --run=$s"); done
    jobs+=("P4_${ch}_edge_s$s|$C --channel=$ch --txPowerDbm=-1 --nUav=30 --rate=4 --bsPos=edge --simTime=300 --warmup=60 --run=$s")
  done
  jobs+=("P5_energy_s$s|$C --channel=fading --txPowerDbm=-1 --nUav=30 --rate=4 --simTime=300 --warmup=60 --energyJ=280 --energyRandMin=0.5 --run=$s")
done
echo "running ${#jobs[@]} simulations with $W workers -> $D"
run1(){ IFS='|' read -r name cmd <<< "$1"; nice -n 10 $cmd > "$2/$name.txt" 2>&1; }
export -f run1
printf '%s\n' "${jobs[@]}" | xargs -P "$W" -I{} bash -c 'run1 "$@"' _ {} "$D"
python3 ~/nbqmaodv-repo/tools/summarize_pilot11.py "$D"
