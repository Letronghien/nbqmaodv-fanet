#!/usr/bin/env python3
"""
run_addendum.py -- post-hoc experiments of docs/EXPERIMENT_ADDENDUM.md (A1, A1b, A2, A3).
Reuses the machinery of run_main.py; results in results/addendum/.

    cd ~/nbqmaodv-fanet/ns-3-nbq
    python3 ~/nbqmaodv-repo/tools/run_addendum.py --list
    python3 ~/nbqmaodv-repo/tools/run_addendum.py --exp all --workers 8
    python3 ~/nbqmaodv-repo/tools/run_addendum.py --collect
"""
import argparse, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_main as rm

rm.CHANNELS["K2h"] = "--channel=fading --nakagamiM=0 --txPowerDbm=3.0"
rm.PROTOS.update({
    "NBQ-onair":    ("nbqmaodv", "NBQ-MAODV", "TagsOnAir=true"),
    "SA-onair":     ("saqmaodv", "SA-QMAODV", "TagsOnAir=true"),
    "PMAODV-onair": ("qmaodv", "PMAODV", "TagsOnAir=true"),
    "QMAODV-onair": ("qmaodv", "QMAODV", "TagsOnAir=true"),
    "LIU-QAODV":    ("nbqmaodv", "NBQ-MAODV", "LiuQAodv=true;TagsOnAir=true"),
})
ORDER = ["A1", "A2", "A3", "A1b"]


def experiments():
    E = {k: [] for k in ORDER}
    c = rm.cond
    for s in rm.SEEDS:
        for K in ("K0", "K1", "K2"):
            for N in (20, 30, 40):
                for L in (40, 80, 160, 320):
                    E["A1"].append(c("NBQ-onair", K, N, L, s))
            for L in (80, 320):
                for p in ("PMAODV-onair", "QMAODV-onair", "SA-onair"):
                    E["A1b"].append(c(p, K, 30, L, s))
            for L in (40, 80, 160, 320):
                E["A2"].append(c("LIU-QAODV", K, 30, L, s))
        for (N, L) in ((20, 80), (30, 80), (40, 80), (30, 320)):
            for p in ("AODV", "NBQ-onair", "LIU-QAODV"):
                E["A3"].append(c(p, "K2h", N, L, s))
    return E


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", nargs="+", default=[])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=6 * 3600)
    ap.add_argument("--ns3", default=os.path.expanduser("~/nbqmaodv-fanet/ns-3-nbq"))
    ap.add_argument("--out", default=os.path.expanduser("~/nbqmaodv-fanet/results/addendum"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--collect", action="store_true")
    a = ap.parse_args()
    raw = os.path.join(a.out, "raw"); os.makedirs(raw, exist_ok=True)
    E = experiments()
    if a.list:
        for e in ORDER:
            ks = list(dict.fromkeys(rm.key(x) for x in E[e]))
            print(f"{e:4s}: {len(ks):4d} runs, {sum(rm.done(os.path.join(raw, k + '.txt')) for k in ks):4d} done")
        print("total:", len({rm.key(x) for v in E.values() for x in v}))
        return
    if a.collect:
        rm.collect(E, raw, os.path.join(a.out, "runs.csv")); return
    exps = ORDER if a.exp == ["all"] else a.exp
    todo, seen = [], set()
    for e in exps:
        for x in E[e]:
            k = rm.key(x)
            if k in seen or rm.done(os.path.join(raw, k + ".txt")): continue
            seen.add(k); todo.append(x)
    print(f"{len(todo)} runs to do with {a.workers} workers -> {raw}", flush=True)
    t0, bad = time.time(), 0
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(rm.run_one, x, a.ns3, raw, a.timeout) for x in todo]
        for i, fu in enumerate(as_completed(futs), 1):
            k, ok, _ = fu.result(); bad += (not ok)
            if not ok: print(f"  FAILED {k}", flush=True)
            if i % 20 == 0 or i == len(todo):
                el = time.time() - t0
                print(f"{i}/{len(todo)} done, {bad} failed, {el/3600:.2f} h, ~{el/i*(len(todo)-i)/3600:.1f} h left", flush=True)
    rm.collect(E, raw, os.path.join(a.out, "runs.csv"))


if __name__ == "__main__":
    main()
