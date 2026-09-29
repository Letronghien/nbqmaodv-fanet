"""
run_ns3_batch.py -- run the NS-3 experiment matrix of the NBQ-MAODV paper in parallel.

    source ~/nbq-project/env.sh
    cd ~/nbq-project/results
    python3 ../tools/run_ns3_batch.py --exp E3_load --workers 4
    python3 ../tools/run_ns3_batch.py --exp all     --workers 4

Output: results_ns3.csv (resumable; finished rows are skipped on restart).
Each simulation runs with 'nice 10' so that other projects on the VM keep priority.
Protocol-specific attributes are passed as --routingAttrs "Name=Value;..." and must
exist in your module (check GetTypeId() of each RoutingProtocol).
"""
import argparse, csv, glob, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

PROTOS = ["AODV", "PMAODV", "QMAODV", "SA-QMAODV", "NBQ-MAODV"]
LEARNERS = ["SA-QMAODV", "NBQ-MAODV"]
FIELDS = ["exp", "x", "variant", "seed", "protocol", "nUav", "vmax", "rate", "tx", "rx",
          "pdr", "delay_ms", "thr_kbps", "ctrl", "nrl", "dead", "first_death", "args"]


def jobs_for(exp, protos, a):
    """(exp, x, variant, protocol, seed, scenario-args dict, routingAttrs)"""
    J = []
    if exp == "E1_density":
        for N in [10, 15, 20, 25, 30]:
            for s in range(1, 21):
                for P in protos: J.append((exp, N, P, P, s, dict(nUav=N), ""))
    elif exp == "E2_speed":
        for v in [10, 20, 30, 40, 50]:
            for s in range(1, 16):
                for P in protos: J.append((exp, v, P, P, s, dict(nUav=20, vmin=v / 4, vmax=v), ""))
    elif exp == "E3_load":
        for r in [2, 4, 8, 12, 16]:
            for s in range(1, 16):
                for P in protos: J.append((exp, r, P, P, s, dict(nUav=20, rate=r), ""))
    elif exp == "E4_energy":   # STEP8: energy-constrained swarm
        for s in range(1, 21):
            for P in protos: J.append((exp, a.energy_j, P, P, s, dict(nUav=20, rate=6, energyJ=a.energy_j), ""))
    elif exp == "E5_ablation":
        comps = [("SA-full", ""), ("SA-noEps", f"{a.attr_eps}=false"),
                 ("SA-noAlpha", f"{a.attr_alpha}=false"), ("SA-noReward", f"{a.attr_reward}=false")]
        for r in [4, 12]:
            for s in range(1, 21):
                for name, attrs in comps:
                    for P in LEARNERS:
                        J.append((f"E5_ablation_r{r}", name, f"{P}|{name}", P, s, dict(nUav=20, rate=r), attrs))
    elif exp == "E6_K":
        for K in [2, 3, 4]:
            for s in range(1, 16):
                for P in ["PMAODV", "NBQ-MAODV"]:
                    J.append((exp, K, P, P, s, dict(nUav=20, rate=8), f"{a.attr_k}={K}"))
    else:
        sys.exit("unknown experiment " + exp)
    return J


MODS = {"AODV": "aodv", "PMAODV": "qmaodv", "PMAODV-AOMDV": "pmaodv", "QMAODV": "qmaodv", "SA-QMAODV": "saqmaodv", "NBQ-MAODV": "nbqmaodv"}


def find_binaries(ns3, protos):
    """one scenario binary per protocol: build/scratch/.../*fanet-scenario-<module>-*"""
    out = {}
    for P in protos:
        mod = MODS[P]
        c = [p for p in glob.glob(os.path.join(ns3, "build", "scratch", "**", f"*fanet-scenario-{mod}-*"), recursive=True)
             if os.path.isfile(p) and os.access(p, os.X_OK)]
        if not c:
            sys.exit(f"Binary for {P} not found (fanet-scenario-{mod}). Run ./ns3 build in {ns3}")
        out[P] = sorted(c, key=len)[0]
    return out


def run(binaries, ns3, job, timeout):
    exp, x, variant, P, seed, kw, attrs = job
    args = ["nice", "-n", "10", binaries[P], f"--protocol={P}", f"--run={seed}"]
    args += [f"--{k}={v}" for k, v in kw.items()]
    if attrs:
        args.append(f"--routingAttrs={attrs}")
    out = subprocess.run(args, cwd=ns3, capture_output=True, text=True, timeout=timeout)
    lines = [l for l in out.stdout.strip().splitlines() if l.count(",") in (11, 13)]
    if out.returncode != 0 or not lines:
        raise RuntimeError((out.stderr or out.stdout)[-400:])
    p = lines[-1].split(",")
    return dict(exp=exp, x=x, variant=variant, seed=seed, protocol=p[0], nUav=p[1], vmax=p[2], rate=p[3],
                tx=p[5], rx=p[6], pdr=p[7], delay_ms=p[8], thr_kbps=p[9], ctrl=p[10], nrl=p[11],
                dead=p[12] if len(p) > 12 else "", first_death=p[13] if len(p) > 13 else "",
                args=" ".join(args[3:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", default="E3_load", help="E1_density|E2_speed|E3_load|E4_energy|E5_ablation|E6_K|all")
    ap.add_argument("--protocols", default=",".join(PROTOS))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help="default: half of the vCPUs, leaving the rest to the other project")
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--out", default="results_ns3.csv")
    # attribute names in YOUR modules (change if GetTypeId() uses other names)
    ap.add_argument("--attr-eps", default="AdaptiveEpsilon")
    ap.add_argument("--attr-alpha", default="AdaptiveAlpha")
    ap.add_argument("--attr-reward", default="AdaptiveReward")
    ap.add_argument("--attr-k", default="MaxPaths")
    ap.add_argument("--energy-j", type=float, default=150.0, help="E4: initial energy per UAV (J)")
    a = ap.parse_args()

    ns3 = os.path.expanduser(os.environ.get("NS3_DIR", "~/nbq-project/ns-3-nbq"))
    protos = a.protocols.split(",")
    exps = ["E3_load", "E5_ablation", "E4_energy", "E1_density", "E2_speed", "E6_K"] if a.exp == "all" else [a.exp]
    jobs = [j for e in exps for j in jobs_for(e, protos, a)]
    binaries = find_binaries(ns3, sorted({j[3] for j in jobs}))

    done = set()
    if os.path.exists(a.out):
        for r in csv.DictReader(open(a.out)):
            done.add((r["exp"], r["x"], r["variant"], r["seed"]))
    todo = [j for j in jobs if (j[0], str(j[1]), j[2], str(j[4])) not in done]
    print("binaries:\n  " + "\n  ".join(f"{k}: {v}" for k, v in binaries.items()) + f"\nruns   : {len(todo)} to do of {len(jobs)}\nworkers: {a.workers}", flush=True)

    new = not os.path.exists(a.out) or os.path.getsize(a.out) == 0
    t0, fails = time.time(), 0
    with open(a.out, "a", newline="") as f, ThreadPoolExecutor(a.workers) as ex:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        fut = {ex.submit(run, binaries, ns3, j, a.timeout): j for j in todo}
        for k, fu in enumerate(as_completed(fut), 1):
            try:
                w.writerow(fu.result()); f.flush()
            except Exception as e:
                fails += 1
                print("FAILED", fut[fu][:5], str(e).strip()[-300:], flush=True)
            if k % 10 == 0 or k == len(todo):
                el = time.time() - t0
                print(f"{k}/{len(todo)}  {el/60:.1f} min, ~{el / k * (len(todo) - k) / 60:.1f} min left, "
                      f"{fails} failed", flush=True)


if __name__ == "__main__":
    main()
