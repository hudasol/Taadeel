"""Pre registered comparison of alignment v2 against the locked v1 on NEW held out seeds and on UK data.

Protocol (mirrors heldout.py; v1 files are not edited):

1. ``tune_v2`` picks v2 weights on dev seeds 0-29 only -> results/dev_v2_tuning.json.
2. ``lock``  writes results/predictions_v2.json and docs/PREDICTIONS_V2.md BEFORE any seed in
             920000-920099 is used and before v2 is run on any UK text. Point predictions: the v2 dev
             value, tolerance +/- 0.05. Directional claims compare v2 with v1 on the same documents.
             sha256 of every engine file and of the v2 files is recorded.
3. ``run``   aborts if any hash differs or if results/heldout_v2.json exists; runs v1 and v2 once on
             the held out seeds and on the UK corpus (one day windows, long gap pairs, renumbering
             variant), scores every prediction and writes results/heldout_v2.json and
             docs/HELDOUT_V2_RESULTS.md.

Synthetic numbers measure engine correctness on generated text. UK numbers are English UK
legislation (OGL v3.0). Neither says anything about UAE law.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import align_v2 as v2
from .align import align as align_v1
from .diff import diff
from .eval_v2 import run as eval_run
from .heldout import DOCS, ENGINE_FILES, RESULTS, SRC, _flat, _fmt
from .uk_corpus import OUT as UK_CORPUS, _expression
from .uk_validate import ADV_SEED, merge, renumber_variant, truth_changes
from .validate import KINDS, SCENARIOS

V2_FILES = ["align_v2.py", "eval_v2.py", "tune_v2.py", "heldout_v2.py"]
HELD_START, HELD_N = 920_000, 100
TOL = 0.05
SC = list(SCENARIOS)
TEMPLATED = SC[1:]

DIRECTIONAL = {
    "V1": "v2 alignment accuracy >= v1 alignment accuracy in every scenario (same held out documents)",
    "V2": "v2 repealed recall >= v1 repealed recall + 0.10 in each of the four templated scenarios",
    "V3": "v2 inserted recall >= v1 inserted recall + 0.10 in the 40% and 70% edited scenarios",
    "V4": "v2 clarified recall >= 0.95 in the many inserts/repeals scenario (v1 held out: 0.909)",
    "V5": "v2 high confidence forced matches on repealed articles <= 3% of repealed articles in every scenario",
    "V6": "easy scenario: every defined v2 precision, recall and alignment accuracy >= 0.999 (forced rate excluded)",
    "V7": "v2 replaced precision >= v1 replaced precision in every templated scenario",
    "U1": "UK one day windows: v2 aligns every shared section correctly, with no false matches",
    "U2": "UK long gap pairs (first to latest snapshot, 7 Acts): v2 correct >= v1 correct and v2 false matches <= v1 false matches",
    "U3": "UK renumbering variant (real text, synthetic renumbering, same seed as v1): v2 accuracy >= 0.99",
}


def hashes() -> dict[str, str]:
    return {f: hashlib.sha256((SRC / f).read_bytes()).hexdigest() for f in ENGINE_FILES + V2_FILES}


def v2_aligner(params: v2.Params):
    return lambda p: v2.align(p.a, p.b, params)


def v1_aligner(p):
    return align_v1(p.a, p.b)


# ---- UK (corpus file, no network) ----------------------------------------------------------
def uk_snapshots() -> dict[str, list]:
    by_act: dict[str, list] = defaultdict(list)
    with gzip.open(UK_CORPUS, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            by_act[r["act"]].append(_expression(r))
    for v in by_act.values():
        v.sort(key=lambda e: e.valid_from)
    return dict(by_act)


def score_uk_pair(a, b, align_fn) -> dict:
    """Same definitions as uk_validate.score_pair, for any aligner."""
    res = align_fn(a, b)
    pred = {(c.a_eid, c.b_eid): c.kind for c in diff(a, b, res)}
    truth = truth_changes(a, b)
    ta = {p.eid for p in a.provisions}
    tb = {p.eid for p in b.provisions}
    shared = ta & tb
    pm = {p.a_eid: p.b_eid for p in res.pairs}
    cls: dict[str, Counter] = defaultdict(Counter)
    for k, v in truth.items():
        cls[v]["tp" if pred.get(k) == v else "fn"] += 1
    for k, v in pred.items():
        if truth.get(k) != v:
            cls[v]["fp"] += 1
    return {"shared": len(shared), "correct": sum(1 for e in shared if pm.get(e) == e),
            "wrong": sum(1 for e in shared if e in pm and pm[e] != e),
            "unmatched_shared": sum(1 for e in shared if e not in pm),
            "false_match": sum(1 for x, y in pm.items() if x not in tb or y not in ta),
            "low_conf_pairs": sum(1 for p in res.pairs if p.confidence == "low"),
            "classes": {k: dict(v) for k, v in cls.items()}}


def uk_eval(align_fn) -> dict:
    snaps = uk_snapshots()
    one_day, long_rows, per_act = [], [], {}
    ren = Counter()
    for act, exps in snaps.items():
        by_date = {e.valid_from: e for e in exps}
        rows = [score_uk_pair(by_date[d - timedelta(days=1)], e, align_fn)
                for d, e in by_date.items() if d - timedelta(days=1) in by_date]
        one_day += rows
        lg = score_uk_pair(exps[0], exps[-1], align_fn)
        long_rows.append(lg)
        per_act[act] = {"one_day_windows": len(rows), "long_gap": merge([lg]),
                        "long_gap_from": exps[0].expression_id, "long_gap_to": exps[-1].expression_id}
        rng = random.Random(f"{ADV_SEED}-{act}")
        base = exps[-1]
        for _ in range(5):
            b, truth = renumber_variant(base, rng)
            res = align_fn(base, b)
            pm = {p.a_eid: p.b_eid for p in res.pairs}
            ren["sections"] += len(truth)
            ren["correct"] += sum(pm.get(a) == bb for a, bb in truth.items())
            ren["inserted_detected"] += sum(1 for c in diff(base, b, res) if c.kind == "inserted" and c.b_eid == "NEW")
            ren["runs"] += 1
    return {"one_day": merge(one_day), "long_gap": merge(long_rows), "per_act": per_act,
            "renumber": {**dict(ren), "accuracy": ren["correct"] / ren["sections"] if ren["sections"] else None}}


# ---- commands --------------------------------------------------------------------------
def cmd_lock() -> str:
    path = RESULTS / "predictions_v2.json"
    if path.exists():
        raise SystemExit("predictions_v2.json exists: the lock is not rewritten")
    tune = json.loads((RESULTS / "dev_v2_tuning.json").read_text(encoding="utf-8"))
    lock = {
        "protocol": "Point prediction = v2 dev (seeds 0-29) value; hit iff |actual - predicted| <= tolerance. "
                    "A None prediction is a hit only if the actual is also None.",
        "tolerance": TOL, "heldout_seeds": [HELD_START, HELD_START + HELD_N], "scenarios": SCENARIOS,
        "params": tune["best"], "sha256": hashes(),
        "predictions": {n: _flat(r) for n, r in tune["dev_v2"].items()},
        "directional": DIRECTIONAL,
        "note": "Synthetic seeds 920000-920099 and v2 on UK text were not run before this file was written.",
    }
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (DOCS / "PREDICTIONS_V2.md").write_text(render_predictions(lock, tune), encoding="utf-8")
    return str(path)


def render_predictions(lock: dict, tune: dict) -> str:
    p = lock["params"]
    L = ["# Predictions for alignment v2 (pre registered)", "",
         "**Committed before the run.** Generated by `python -m taadeel.heldout_v2 lock` from `results/predictions_v2.json` and `results/dev_v2_tuning.json`.",
         "Synthetic data measures engine correctness on generated text; UK data is English UK legislation (OGL v3.0). Neither says anything about UAE law.",
         "",
         f"* v2 weights, chosen on dev seeds 0 to 29 only (`python -m taadeel.tune_v2`, {tune['evaluated']} settings): w_sim {p['w_sim']}, w_excess {p['w_excess']}, w_num {p['w_num']}, w_prior {p['w_prior']}, tau {p['tau']}.",
         f"* Selection: {tune['selection_rule']}. The unconstrained best ({tune['best_unconstrained']['w_sim']} / {tune['best_unconstrained']['w_excess']} / {tune['best_unconstrained']['w_num']} / {tune['best_unconstrained']['w_prior']} / {tune['best_unconstrained']['tau']}, objective {tune['best_unconstrained_objective']:.4f}) could match a pair only with number evidence; the selected setting has objective {tune['best_objective']:.4f}. v1 on the same dev seeds: {tune['v1_objective']:.4f}.",
         "* The background correction feature (w_excess) was evaluated; " + ("the selected weight is 0, so it has no effect." if p["w_excess"] == 0 else f"selected weight {p['w_excess']}."),
         f"* New held out seeds: {lock['heldout_seeds'][0]} to {lock['heldout_seeds'][1] - 1} per scenario (never used before this file). v1 and v2 run on the same documents.",
         f"* Rule: {lock['protocol']} Tolerance: +/- {lock['tolerance']}.",
         "* The run aborts if any hashed file changed and refuses to run twice. v1 remains the default unless the results support v2.",
         "", "## Point predictions for v2 (dev value)", "",
         "| scenario | align acc | forced rate | replaced P/R | repealed P/R | inserted P/R | renumbered P/R | clarified P/R |",
         "|---|---|---|---|---|---|---|---|"]
    for name, m in lock["predictions"].items():
        pr = lambda k: f"{_fmt(m[k + '.P'])} / {_fmt(m[k + '.R'])}"
        L.append(f"| {name} | {_fmt(m['align_acc'])} | {_fmt(m['forced_rate'])} | {pr('replaced')} | {pr('repealed')} | {pr('inserted')} | {pr('renumbered')} | {pr('clarified')} |")
    L += ["", "## Directional claims", ""] + [f"* **{k}**: {v}" for k, v in lock["directional"].items()]
    L += ["", "## Hashed files (sha256)", ""] + [f"* `{f}`: `{h}`" for f, h in lock["sha256"].items()] + [""]
    return "\n".join(L)


def check_directional(h1: dict, h2: dict, uk1: dict, uk2: dict) -> dict:
    f1 = {n: _flat(r) for n, r in h1.items()}
    f2 = {n: _flat(r) for n, r in h2.items()}
    d: dict[str, dict] = {}
    acc = {n: (round(f2[n]["align_acc"], 3), round(f1[n]["align_acc"], 3)) for n in SC}
    d["V1"] = {"ok": all(f2[n]["align_acc"] >= f1[n]["align_acc"] for n in SC), "detail": {n: f"v2 {a} v1 {b}" for n, (a, b) in acc.items()}}
    rr = {n: (f2[n]["repealed.R"], f1[n]["repealed.R"]) for n in TEMPLATED}
    d["V2"] = {"ok": all(a >= b + 0.10 for a, b in rr.values()), "detail": {n: f"v2 {a:.3f} v1 {b:.3f}" for n, (a, b) in rr.items()}}
    ir = {n: (f2[n]["inserted.R"], f1[n]["inserted.R"]) for n in (SC[2], SC[3])}
    d["V3"] = {"ok": all(a >= b + 0.10 for a, b in ir.values()), "detail": {n: f"v2 {a:.3f} v1 {b:.3f}" for n, (a, b) in ir.items()}}
    cr = f2[SC[4]]["clarified.R"]
    d["V4"] = {"ok": cr is not None and cr >= 0.95, "detail": None if cr is None else round(cr, 3)}
    fr = {n: f2[n]["forced_rate"] or 0.0 for n in SC}
    d["V5"] = {"ok": all(v <= 0.03 for v in fr.values()), "detail": {n: round(v, 3) for n, v in fr.items()}}
    easy = {k: v for k, v in f2[SC[0]].items() if k != "forced_rate" and v is not None}
    d["V6"] = {"ok": all(v >= 0.999 for v in easy.values()), "detail": f"min={min(easy.values()):.3f}"}
    rp = {n: (f2[n]["replaced.P"], f1[n]["replaced.P"]) for n in TEMPLATED}
    d["V7"] = {"ok": all(a >= b for a, b in rp.values()), "detail": {n: f"v2 {a:.3f} v1 {b:.3f}" for n, (a, b) in rp.items()}}
    od = uk2["one_day"]["alignment"]
    d["U1"] = {"ok": od["correct"] == od["shared_sections"] and od["false_matches"] == 0,
               "detail": f"{od['correct']} of {od['shared_sections']}, false matches {od['false_matches']}"}
    l1, l2 = uk1["long_gap"]["alignment"], uk2["long_gap"]["alignment"]
    d["U2"] = {"ok": l2["correct"] >= l1["correct"] and l2["false_matches"] <= l1["false_matches"],
               "detail": f"v2 {l2['correct']} of {l2['shared_sections']} (false {l2['false_matches']}), v1 {l1['correct']} of {l1['shared_sections']} (false {l1['false_matches']})"}
    ra = uk2["renumber"]["accuracy"]
    d["U3"] = {"ok": ra is not None and ra >= 0.99, "detail": f"{uk2['renumber']['correct']} of {uk2['renumber']['sections']}"}
    return d


def cmd_run() -> str:
    lock = json.loads((RESULTS / "predictions_v2.json").read_text(encoding="utf-8"))
    out_path = RESULTS / "heldout_v2.json"
    if out_path.exists():
        raise SystemExit("heldout_v2.json exists: run once only. Not re-running.")
    now = hashes()
    changed = [f for f in now if now[f] != lock["sha256"].get(f)]
    if changed:
        raise SystemExit(f"files changed after lock: {changed}; aborting")
    params = v2.Params(**lock["params"])
    seeds = range(*lock["heldout_seeds"])
    h1 = {n: eval_run(seeds, v1_aligner, **kw) for n, kw in lock["scenarios"].items()}
    h2 = {n: eval_run(seeds, v2_aligner(params), **kw) for n, kw in lock["scenarios"].items()}
    uk1 = uk_eval(lambda a, b: align_v1(a, b))
    uk2 = uk_eval(lambda a, b: v2.align(a, b, params))
    score, hits, total = {}, 0, 0
    for name, res in h2.items():
        fl, sc = _flat(res), {}
        for metric, pred in lock["predictions"][name].items():
            act = fl[metric]
            if pred is None:
                ok, delta = act is None, None
            elif act is None:
                ok, delta = False, None
            else:
                delta = act - pred
                ok = abs(delta) <= lock["tolerance"] + 1e-12
            sc[metric] = {"pred": pred, "actual": act, "delta": delta, "hit": ok}
            hits += ok
            total += 1
        score[name] = sc
    direc = check_directional(h1, h2, uk1, uk2)
    out = {"data": "SYNTHETIC held out seeds 920000-920099 and English UK legislation (OGL v3.0); not UAE law",
           "sha256": now, "params": lock["params"], "heldout_v1": h1, "heldout_v2": h2, "uk_v1": uk1, "uk_v2": uk2,
           "score_v2": score, "hits": hits, "total": total, "directional": direc,
           "directional_hits": sum(v["ok"] for v in direc.values()), "directional_total": len(direc)}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (DOCS / "HELDOUT_V2_RESULTS.md").write_text(render_results(out, lock), encoding="utf-8")
    return str(out_path)


def render_results(out: dict, lock: dict) -> str:
    L = ["# Alignment v2 against v1: held out results", "",
         "Generated by `python -m taadeel.heldout_v2 run` from `results/heldout_v2.json`. Do not edit by hand.",
         "Predictions were committed first (`docs/PREDICTIONS_V2.md`); the run happened once; hashes matched the lock.",
         "Synthetic rows are SYNTHETIC (generated text). UK rows are English UK legislation (OGL v3.0, England and Wales view). Nothing here is evidence about UAE law.",
         "",
         f"**v2 point predictions: {out['hits']} hits of {out['total']} (tolerance +/- {lock['tolerance']}). Directional claims: {out['directional_hits']} of {out['directional_total']} hold.**",
         "", "## Synthetic held out seeds 920000 to 920099: v2 (v1 on the same documents)", "",
         "| scenario | align acc | forced rate | replaced P/R | repealed P/R | inserted P/R | clarified P/R |",
         "|---|---|---|---|---|---|---|"]
    for name in out["score_v2"]:
        a, b = _flat(out["heldout_v2"][name]), _flat(out["heldout_v1"][name])
        c = lambda k: f"{_fmt(a[k])} ({_fmt(b[k])})"
        two = lambda k: f"{c(k + '.P')} / {c(k + '.R')}"
        L.append(f"| {name} | {c('align_acc')} | {c('forced_rate')} | {two('replaced')} | {two('repealed')} | {two('inserted')} | {two('clarified')} |")
    L += ["", "## v2 prediction misses", ""]
    misses = [(n, m, x) for n, sc in out["score_v2"].items() for m, x in sc.items() if not x["hit"]]
    L += ["None."] if not misses else [
        f"* {n} / {m}: predicted {_fmt(x['pred'])}, actual {_fmt(x['actual'])} (delta {'n/a' if x['delta'] is None else format(x['delta'], '+.3f')})"
        for n, m, x in misses]
    L += ["", "## Directional claims", ""]
    for k, v in out["directional"].items():
        L.append(f"* **{k}** {'HIT' if v['ok'] else 'MISS'}: {lock['directional'][k]} ({v['detail']})")
    L += ["", "## UK (English, England and Wales view): v1 and v2 on the same pairs", "",
          "| view | v1 correct / shared | v1 false matches | v2 correct / shared | v2 false matches |", "|---|---|---|---|---|"]
    for key, label in (("one_day", "one day windows"), ("long_gap", "long gap (first to latest snapshot)")):
        x, y = out["uk_v1"][key]["alignment"], out["uk_v2"][key]["alignment"]
        L.append(f"| {label} | {x['correct']} / {x['shared_sections']} | {x['false_matches']} | {y['correct']} / {y['shared_sections']} | {y['false_matches']} |")
    r1, r2 = out["uk_v1"]["renumber"], out["uk_v2"]["renumber"]
    L.append(f"| renumbering variant (synthetic renumbering of real text) | {r1['correct']} / {r1['sections']} | n/a | {r2['correct']} / {r2['sections']} | n/a |")
    L += ["", "Long gap class counts (TP/FP/FN):", ""]
    for ver in ("uk_v1", "uk_v2"):
        cl = out[ver]["long_gap"]["classes"]
        L.append(f"* {ver[3:]}: " + "; ".join(f"{k} {v['tp']}/{v['fp']}/{v['fn']}" for k, v in cl.items()))
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"lock": cmd_lock, "run": cmd_run}.get(cmd)
    if fn is None:
        raise SystemExit("usage: python -m taadeel.heldout_v2 lock|run")
    print(fn())
