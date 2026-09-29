#!/usr/bin/env python3
"""
run_main.py -- main experiments of docs/EXPERIMENT_DESIGN.md (frozen, Step 11c).

    cd ~/nbqmaodv-fanet/ns-3-nbq
    python3 ~/nbqmaodv-repo/tools/run_main.py --list                  # show experiments and run counts
    python3 ~/nbqmaodv-repo/tools/run_main.py --exp E2 E5 --workers 8
    python3 ~/nbqmaodv-repo/tools/run_main.py --exp all --workers 8   # everything, in the frozen order
    python3 ~/nbqmaodv-repo/tools/run_main.py --collect               # build runs.csv from raw outputs

* Resumable: a run whose output file already holds a CSV line is skipped.
* Deduplicated: a run shared by several experiments is simulated once (same key).
* Raw output of every run: results/main/raw/<key>.txt ; parsed table: results/main/runs.csv
"""
import argparse, csv, glob, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

SEEDS = list(range(1, 21))
CHANNELS = {
    "K0": "--channel=range",
    "K1": "--channel=fading --nakagamiM=10 --txPowerDbm=-1.9",
    "K2": "--channel=fading --nakagamiM=0 --txPowerDbm=-2.0",
}
# protocol label -> (module binary, --protocol value, routingAttrs)
PROTOS = {
    "AODV":        ("aodv", "AODV", ""),
    "PMAODV":      ("qmaodv", "PMAODV", ""),
    "QMAODV":      ("qmaodv", "QMAODV", ""),
    "SA-QMAODV":   ("saqmaodv", "SA-QMAODV", ""),
    "NBQ-MAODV":   ("nbqmaodv", "NBQ-MAODV", ""),
    # E5 ablation variants of NBQ-MAODV
    "NBQ-noBoot":  ("nbqmaodv", "NBQ-MAODV", "NeighbourBootstrap=false"),
    "NBQ-saEps":   ("nbqmaodv", "NBQ-MAODV", "Epsilon0=0.3;EpsilonMin=0.1"),
    "NBQ-bump":    ("nbqmaodv", "NBQ-MAODV", "UseRerrBump=true"),
    "NBQ-srcOnly": ("nbqmaodv", "NBQ-MAODV", "HopByHop=false"),
}
ALL5 = ["AODV", "PMAODV", "QMAODV", "SA-QMAODV", "NBQ-MAODV"]
ABL = ["NBQ-MAODV", "NBQ-noBoot", "NBQ-saEps", "NBQ-bump", "NBQ-srcOnly"]
ORDER = ["E2", "E5", "E1", "E3", "E4", "E6a", "E6b", "R600"]


def cond(proto, K, N, L, seed, area=1000, bs="center", energy=False, sim=300, warm=60):
    return dict(proto=proto, K=K, N=N, L=L, seed=seed, area=area, bs=bs, energy=energy, sim=sim, warm=warm)


def experiments():
    E = {k: [] for k in ORDER}
    for s in SEEDS:
        for K in CHANNELS:
            for N in (20, 30, 40):
                for p in ALL5:
                    E["E1"].append(cond(p, K, N, 80, s))
                for L in (40, 80, 160, 320):
                    for p in ("AODV", "NBQ-MAODV"):
                        E["E2"].append(cond(p, K, N, L, s))
            for L in (40, 80, 160, 320):
                for p in ALL5:
                    E["E3"].append(cond(p, K, 30, L, s))
            for L in (80, 320):
                for p in ABL:
                    E["E5"].append(cond(p, K, 30, L, s))
            for p in ("AODV", "NBQ-MAODV", "SA-QMAODV"):
                E["E6a"].append(cond(p, K, 30, 80, s, bs="edge"))
                for N in (45, 68):
                    E["E6b"].append(cond(p, K, N, 80, s, area=1500))
            for p in ("AODV", "NBQ-MAODV"):
                E["R600"].append(cond(p, K, 30, 80, s, sim=600, warm=300))
        for K in ("K0", "K1"):
            for p in ALL5:
                E["E4"].append(cond(p, K, 30, 80, s, energy=True))
    return E


def key(c):
    k = f"{c['proto']}_{c['K']}_N{c['N']}_L{c['L']}_s{c['seed']}"
    if c["area"] != 1000: k += f"_A{c['area']}"
    if c["bs"] != "center": k += f"_bs{c['bs']}"
    if c["energy"]: k += "_E280"
    if c["sim"] != 300: k += f"_T{c['sim']}w{c['warm']}"
    return k


def command(c, ns3):
    mod, proto, attrs = PROTOS[c["proto"]]
    b = sorted(glob.glob(os.path.join(ns3, "build", "scratch", f"*fanet-scenario-{mod}-optimized")), key=len)
    if not b:
        sys.exit(f"binary for module {mod} not found; run ./ns3 build in {ns3}")
    cmd = [b[0], f"--protocol={proto}", "--mobility=gm", f"--simTime={c['sim']}", f"--warmup={c['warm']}",
           f"--nUav={c['N']}", f"--totalLoad={c['L']}", f"--run={c['seed']}", f"--area={c['area']}",
           f"--bsPos={c['bs']}"] + CHANNELS[c["K"]].split()
    if c["energy"]:
        cmd += ["--energyJ=280", "--energyRandMin=0.5"]
    if attrs:
        cmd.append(f"--routingAttrs={attrs}")
    return ["nice", "-n", "10"] + cmd


def done(path):
    if not os.path.exists(path):
        return False
    with open(path, errors="ignore") as f:
        return any(re.match(r"^[A-Z-]+,\d+,", l) for l in f)


def run_one(c, ns3, raw, timeout):
    path = os.path.join(raw, key(c) + ".txt")
    t0 = time.time()
    try:
        out = subprocess.run(command(c, ns3), cwd=ns3, capture_output=True, text=True, timeout=timeout)
        txt = out.stdout + out.stderr
    except subprocess.TimeoutExpired:
        txt = "TIMEOUT"
    with open(path + ".tmp", "w") as f:
        f.write(" ".join(command(c, ns3)) + "\n" + txt)
    os.replace(path + ".tmp", path)
    return key(c), done(path), time.time() - t0


def parse(path):
    with open(path, errors="ignore") as f:
        lines = f.read().splitlines()
    csvl = [l for l in lines if re.match(r"^[A-Z-]+,\d+,", l)]
    met = [l for l in lines if l.startswith("# METRICS")]
    if not csvl:
        return None
    v = csvl[-1].split(",")
    r = dict(tx=int(v[5]), rx=int(v[6]), pdr=float(v[7]), delay=float(v[8]), thr=float(v[9]), ctrl=int(v[10]),
             nrl=float(v[11]), dead=int(v[12]), first_death=float(v[13]))
    if met:
        r.update({k: v for k, v in (kv.split("=", 1) for kv in met[-1][len("# METRICS "):].split())})
    return r


def collect(E, raw, out_csv):
    member = {}
    for e, cs in E.items():
        for c in cs:
            member.setdefault(key(c), (c, set()))[1].add(e)
    rows, missing = [], 0
    for k, (c, exps) in member.items():
        p = os.path.join(raw, k + ".txt")
        r = parse(p) if os.path.exists(p) else None
        if r is None:
            missing += 1
            continue
        row = dict(key=k, exps=";".join(sorted(exps)), **{x: c[x] for x in c}); row.update(r)
        rows.append(row)
    fields = sorted({f for r in rows for f in r}, key=lambda f: (f not in ("key", "exps", "proto", "K", "N", "L", "seed"), f))
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"collected {len(rows)} runs -> {out_csv} ({missing} not available yet)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", nargs="+", default=[], help="experiments to run (E1..E6b, R600) or 'all'")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=6 * 3600)
    ap.add_argument("--ns3", default=os.path.expanduser("~/nbqmaodv-fanet/ns-3-nbq"))
    ap.add_argument("--out", default=os.path.expanduser("~/nbqmaodv-fanet/results/main"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--collect", action="store_true")
    a = ap.parse_args()
    raw = os.path.join(a.out, "raw"); os.makedirs(raw, exist_ok=True)
    E = experiments()
    if a.list:
        seen = set(); tot = 0
        for e in ORDER:
            ks = [key(c) for c in E[e]]; new = [k for k in dict.fromkeys(ks) if k not in seen]
            ok = sum(done(os.path.join(raw, k + ".txt")) for k in dict.fromkeys(ks))
            print(f"{e:5s}: {len(set(ks)):5d} runs ({len(new):5d} not shared with earlier experiments), {ok:5d} done")
            seen.update(ks); tot += len(new)
        print(f"total unique runs: {tot}")
        return
    if a.collect:
        collect(E, raw, os.path.join(a.out, "runs.csv"))
        return
    exps = ORDER if a.exp == ["all"] else a.exp
    todo, seen = [], set()
    for e in exps:
        for c in E[e]:
            k = key(c)
            if k in seen or done(os.path.join(raw, k + ".txt")):
                continue
            seen.add(k); todo.append(c)
    print(f"{len(todo)} runs to do for {' '.join(exps)} with {a.workers} workers -> {raw}", flush=True)
    t0, n_ok, n_bad = time.time(), 0, 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(run_one, c, a.ns3, raw, a.timeout) for c in todo]
        for i, fu in enumerate(as_completed(futs), 1):
            k, ok, dt = fu.result()
            n_ok += ok; n_bad += (not ok)
            if not ok:
                print(f"  FAILED {k} (see raw/{k}.txt)", flush=True)
            if i % 20 == 0 or i == len(todo):
                el = time.time() - t0
                print(f"{i}/{len(todo)} done, {n_bad} failed, {el/3600:.2f} h elapsed, "
                      f"~{el / i * (len(todo) - i) / 3600:.1f} h left", flush=True)
    collect(E, raw, os.path.join(a.out, "runs.csv"))


if __name__ == "__main__":
    main()
