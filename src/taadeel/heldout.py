"""Locked held-out evaluation on fresh synthetic seeds.

Protocol (so the numbers are a clean held-out estimate, not a tuned one):

1. ``dev``  : run the five scenarios on the tuning seeds 0-29 -> results/dev_synthetic.json.
              These seeds were used while the engine was developed and tuned.
2. ``lock`` : write results/predictions.json (+ docs/PREDICTIONS.md) BEFORE touching
              the held-out seeds. Point predictions follow a fixed rule: the dev value,
              tolerance +/- TOL absolute. Directional claims are fixed here too. The file
              records sha256 of every engine/generator source file and the frozen
              scenario parameters. It is committed, then ``run`` is executed once.
3. ``run``  : refuses to run if any engine file hash differs from the lock, or if
              results/heldout_synthetic.json already exists. Runs the held-out seeds ONCE,
              scores every prediction (hit / miss, with the delta) and writes
              results/heldout_synthetic.json + docs/HELDOUT_RESULTS.md.

All data here is SYNTHETIC. These numbers show whether the engine recovers operations it
was given on fresh random documents; they say nothing about real legislation.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from . import validate

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
DOCS = ROOT / "docs"
SRC = Path(__file__).resolve().parent

ENGINE_FILES = ["align.py", "diff.py", "synthetic.py", "normalize.py", "model.py", "parse.py", "temporal.py"]
DEV_SEEDS = range(0, 30)
HELD_START, HELD_N = 910_000, 100          # never used before the lock
TOL = 0.05
KINDS = validate.KINDS


def engine_hashes() -> dict[str, str]:
    return {f: hashlib.sha256((SRC / f).read_bytes()).hexdigest() for f in ENGINE_FILES}


def _flat(res: dict) -> dict[str, float | None]:
    """Flatten one scenario result into named metrics."""
    out: dict[str, float | None] = {"align_acc": res["alignment_accuracy"]}
    rt = res["repealed_total"]
    out["forced_rate"] = res["forced_matches_on_repealed"] / rt if rt else None
    for k in KINDS:
        out[f"{k}.P"] = res["per_class"][k]["precision"]
        out[f"{k}.R"] = res["per_class"][k]["recall"]
    return out


def _run_all(seeds: range, scenarios: dict) -> dict:
    return {name: validate.run(seeds, **kw) for name, kw in scenarios.items()}


# ---- directional claims (fixed at lock time) -----------------------------
SC = list(validate.SCENARIOS)   # order: easy, templated small, 40%, 70%, many ins/rep

DIRECTIONAL = {
    "D1": "easy scenario: every defined precision/recall/alignment metric >= 0.999",
    "D2": "alignment accuracy is non-increasing across the five scenarios in listed order",
    "D3": "high-confidence forced matches on repealed articles are <= 3% of repealed articles in every scenario",
    "D4": "repealed recall < 0.75 in every templated scenario",
    "D5": "inserted precision < 0.50 in the 70%-edited scenario",
    "D6": "mean alignment accuracy over the five scenarios is not higher than the dev mean + 0.01",
}


def check_directional(held: dict[str, dict], dev: dict[str, dict]) -> dict[str, dict]:
    flat = {n: _flat(r) for n, r in held.items()}
    dflat = {n: _flat(r) for n, r in dev.items()}
    res: dict[str, dict] = {}
    easy = flat[SC[0]]
    vals = [v for v in easy.values() if v is not None]
    res["D1"] = {"ok": all(v >= 0.999 for v in vals), "detail": f"min={min(vals):.3f}"}
    accs = [flat[n]["align_acc"] for n in SC]
    res["D2"] = {"ok": all(accs[i] >= accs[i + 1] for i in range(4)), "detail": [round(a, 3) for a in accs]}
    fr = {n: flat[n]["forced_rate"] for n in SC}
    res["D3"] = {"ok": all((v or 0) <= 0.03 for v in fr.values()), "detail": {n: (None if v is None else round(v, 3)) for n, v in fr.items()}}
    rr = {n: flat[n]["repealed.R"] for n in SC[1:]}
    res["D4"] = {"ok": all(v is not None and v < 0.75 for v in rr.values()), "detail": {n: (None if v is None else round(v, 3)) for n, v in rr.items()}}
    ip = flat[SC[3]]["inserted.P"]
    res["D5"] = {"ok": ip is not None and ip < 0.50, "detail": None if ip is None else round(ip, 3)}
    hm = sum(accs) / 5
    dm = sum(dflat[n]["align_acc"] for n in SC) / 5
    res["D6"] = {"ok": hm <= dm + 0.01, "detail": f"held mean={hm:.3f} dev mean={dm:.3f}"}
    return res


# ---- commands ------------------------------------------------------------
def cmd_dev() -> Path:
    RESULTS.mkdir(exist_ok=True)
    out = {"data": "SYNTHETIC tuning seeds (used during development)", "seeds": [DEV_SEEDS.start, DEV_SEEDS.stop],
           "scenarios": validate.SCENARIOS, "results": _run_all(DEV_SEEDS, validate.SCENARIOS)}
    p = RESULTS / "dev_synthetic.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return p


def cmd_lock() -> Path:
    lock_path = RESULTS / "predictions.json"
    if lock_path.exists():
        raise SystemExit("predictions.json already exists: the lock is not rewritten")
    dev = json.loads((RESULTS / "dev_synthetic.json").read_text(encoding="utf-8"))
    preds = {name: _flat(r) for name, r in dev["results"].items()}
    lock = {
        "protocol": "Point prediction = dev (seeds 0-29) value; hit iff |actual - predicted| <= tolerance. "
                    "A None prediction is a hit only if the actual is also None.",
        "tolerance": TOL,
        "heldout_seeds": [HELD_START, HELD_START + HELD_N],
        "scenarios": validate.SCENARIOS,
        "engine_sha256": engine_hashes(),
        "predictions": preds,
        "directional": DIRECTIONAL,
        "note": "Synthetic data only. Written before any held-out seed was run.",
    }
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    DOCS.joinpath("PREDICTIONS.md").write_text(render_predictions(lock), encoding="utf-8")
    return lock_path


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def render_predictions(lock: dict) -> str:
    lines = [
        "# Predictions for the locked held-out synthetic set",
        "",
        "**Committed before the held-out run.** Generated by `python -m taadeel.heldout lock` from `results/predictions.json`.",
        "All data is SYNTHETIC; this measures whether the engine recovers known operations on fresh random documents, not accuracy on real law.",
        "",
        f"* Held-out seeds: {lock['heldout_seeds'][0]} to {lock['heldout_seeds'][1] - 1} per scenario (never used before this file was written).",
        f"* Rule: {lock['protocol']} Tolerance: +/- {lock['tolerance']}.",
        "* Engine and generator files are hash-locked (below). The run script aborts if any hash differs, and refuses to run twice.",
        "* Why the rule is conservative: the ambiguity margin (0.05) was chosen after looking at seeds 0-99 and 1000-1059, so dev values may be optimistic.",
        "",
        "## Point predictions (dev value)",
        "",
        "| scenario | align acc | forced rate | replaced P/R | repealed P/R | inserted P/R | renumbered P/R | clarified P/R |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, m in lock["predictions"].items():
        pr = lambda k: f"{_fmt(m[k + '.P'])} / {_fmt(m[k + '.R'])}"
        lines.append(f"| {name} | {_fmt(m['align_acc'])} | {_fmt(m['forced_rate'])} | {pr('replaced')} | {pr('repealed')} | {pr('inserted')} | {pr('renumbered')} | {pr('clarified')} |")
    lines += ["", "## Directional claims", ""]
    lines += [f"* **{k}**: {v}" for k, v in lock["directional"].items()]
    lines += ["", "## Locked source hashes (sha256)", ""]
    lines += [f"* `{f}`: `{h}`" for f, h in lock["engine_sha256"].items()]
    lines += ["", "Scenario parameters are frozen in `results/predictions.json`.", ""]
    return "\n".join(lines)


def cmd_run() -> Path:
    lock = json.loads((RESULTS / "predictions.json").read_text(encoding="utf-8"))
    out_path = RESULTS / "heldout_synthetic.json"
    if out_path.exists():
        raise SystemExit("heldout_synthetic.json exists: the held-out set is run once. Not re-running.")
    now = engine_hashes()
    changed = [f for f in ENGINE_FILES if now[f] != lock["engine_sha256"][f]]
    if changed:
        raise SystemExit(f"engine files changed after lock: {changed}. Held-out numbers would not be clean; aborting.")
    seeds = range(*lock["heldout_seeds"])
    held = _run_all(seeds, lock["scenarios"])
    dev = json.loads((RESULTS / "dev_synthetic.json").read_text(encoding="utf-8"))["results"]
    score: dict[str, dict] = {}
    hits = total = 0
    for name, res in held.items():
        fl = _flat(res)
        sc = {}
        for metric, pred in lock["predictions"][name].items():
            act = fl[metric]
            if pred is None:
                ok = act is None
                delta = None
            elif act is None:
                ok, delta = False, None
            else:
                delta = act - pred
                ok = abs(delta) <= lock["tolerance"] + 1e-12
            sc[metric] = {"pred": pred, "actual": act, "delta": delta, "hit": ok}
            hits += ok
            total += 1
        score[name] = sc
    out = {"data": "SYNTHETIC held-out seeds (locked before run)", "seeds": lock["heldout_seeds"],
           "engine_sha256": now, "results": held, "score": score,
           "directional": check_directional(held, dev), "hits": hits, "total": total}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    DOCS.joinpath("HELDOUT_RESULTS.md").write_text(render_results(out, lock), encoding="utf-8")
    return out_path


def render_results(out: dict, lock: dict) -> str:
    L = [
        "# Held-out results (synthetic)",
        "",
        "Generated by `python -m taadeel.heldout run` from `results/heldout_synthetic.json`. Do not edit by hand.",
        "SYNTHETIC data only. Predictions were committed first (`docs/PREDICTIONS.md`); the set was run once; engine hashes matched the lock.",
        "",
        f"**Point predictions: {out['hits']} hits of {out['total']} (tolerance +/- {lock['tolerance']}).**",
        "",
        "## Metrics (actual) with prediction outcome",
        "",
        "| scenario | align acc | forced rate | replaced P/R | repealed P/R | inserted P/R | renumbered P/R | clarified P/R |",
        "|---|---|---|---|---|---|---|---|",
    ]

    def cell(sc, m):
        x = sc[m]
        return f"{_fmt(x['actual'])}{'' if x['hit'] else ' (miss ' + ('%+.3f' % x['delta'] if x['delta'] is not None else 'n/a') + ')'}"

    for name, sc in out["score"].items():
        two = lambda k: f"{cell(sc, k + '.P')} / {cell(sc, k + '.R')}"
        L.append(f"| {name} | {cell(sc, 'align_acc')} | {cell(sc, 'forced_rate')} | {two('replaced')} | {two('repealed')} | {two('inserted')} | {two('renumbered')} | {two('clarified')} |")
    L += ["", "## Misses", ""]
    misses = [(n, m, x) for n, sc in out["score"].items() for m, x in sc.items() if not x["hit"]]
    if not misses:
        L.append("None.")
    for n, m, x in misses:
        d = "n/a" if x["delta"] is None else f"{x['delta']:+.3f}"
        L.append(f"* {n} / {m}: predicted {_fmt(x['pred'])}, actual {_fmt(x['actual'])} (delta {d})")
    L += ["", "## Directional claims", ""]
    for k, v in out["directional"].items():
        L.append(f"* **{k}** {'HIT' if v['ok'] else 'MISS'}: {lock['directional'][k]} ({v['detail']})")
    L += ["", "## Support (events per class, held-out)", ""]
    for name, r in out["results"].items():
        sup = ", ".join(f"{k} {r['per_class'][k]['support']}" for k in KINDS)
        L.append(f"* {name}: {sup}; repealed total {r['repealed_total']}")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"dev": cmd_dev, "lock": cmd_lock, "run": cmd_run}.get(cmd)
    if fn is None:
        raise SystemExit("usage: python -m taadeel.heldout dev|lock|run")
    print(fn())
