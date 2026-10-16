"""Tune align_v2 weights on the DEV seeds 0-29 only (SYNTHETIC). Held out seeds are never touched here.

Objective (fixed before the search): mean over the five scenarios of
(alignment accuracy + F1 replaced + F1 repealed + F1 inserted) / 4, among settings whose
high confidence forced match rate on repealed articles is <= 3% in every scenario (v1's D3 bound).
Selection (added on 2026-10-16 after seeing only dev results, before any held out seed was run): the
setting with the best objective lets a pair match only with number evidence (0.5 * sim never exceeds
tau = 0.5), which would break on laws renumbered in ways the anchors do not explain. Robustness rule:
a pair with similarity 0.9 must be able to match on text alone (w_sim * 0.9 > tau). Among feasible
settings that satisfy it, the best objective is selected.
Output: results/dev_v2_tuning.json (grid, best setting, top settings, v1 and v2 dev metrics).
"""
from __future__ import annotations

import itertools
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace

from . import align_v2 as v2
from .align import align as align_v1
from .eval_v2 import score_pairs
from .heldout import RESULTS
from .synthetic import make_pair
from .validate import SCENARIOS

DEV = range(0, 30)
GRID = {
    "w_sim": [0.5, 1.0],
    "w_excess": [0.0, 0.5, 1.0],
    "w_num": [0.1, 0.2, 0.3, 0.4, 0.6],
    "w_prior": [0.0, 0.1],
    "tau": [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
}

_DATA: dict | None = None


def _load() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = {}
        for name, kw in SCENARIOS.items():
            ps = [make_pair(s, **kw) for s in DEV]
            _DATA[name] = [(p, v2.similarity_matrix(p.a.articles(), p.b.articles())) for p in ps]
    return _DATA


def _f1(pc: dict) -> float:
    p, r = pc["precision"] or 0.0, pc["recall"] or 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def objective(res: dict) -> tuple[float, bool]:
    vals, ok = [], True
    for r in res.values():
        pc = r["per_class"]
        vals.append((r["alignment_accuracy"] + _f1(pc["replaced"]) + _f1(pc["repealed"]) + _f1(pc["inserted"])) / 4)
        if r["repealed_total"] and r["forced_matches_on_repealed"] / r["repealed_total"] > 0.03:
            ok = False
    return sum(vals) / len(vals), ok


def evaluate(params: v2.Params) -> dict:
    data = _load()
    out = {}
    for name, items in data.items():
        S = {id(p): s for p, s in items}
        out[name] = score_pairs([p for p, _ in items],
                                lambda p: v2.align_matrix(p.a.articles(), p.b.articles(), S[id(p)], params))
    return out


def _job(values: tuple) -> tuple[dict, float, bool]:
    params = replace(v2.DEFAULT, **dict(zip(GRID, values)))
    obj, ok = objective(evaluate(params))
    return asdict(params), obj, ok


def tune(workers: int = 8) -> dict:
    combos = list(itertools.product(*GRID.values()))
    with ProcessPoolExecutor(workers) as ex:
        rows = list(ex.map(_job, combos, chunksize=8))
    feasible = sorted((r for r in rows if r[2]), key=lambda r: -r[1])
    robust = [r for r in feasible if r[0]["w_sim"] * 0.9 > r[0]["tau"]]
    best = v2.Params(**robust[0][0])
    v1_dev = {name: score_pairs([p for p, _ in items], lambda p: align_v1(p.a, p.b)) for name, items in _load().items()}
    out = {"data": "SYNTHETIC dev seeds 0-29 only", "grid": GRID, "objective": __doc__.split("Objective")[1].split("Selection")[0].strip(),
           "evaluated": len(rows), "feasible": len(feasible), "best_unconstrained": feasible[0][0], "best_unconstrained_objective": feasible[0][1],
           "selection_rule": "best objective among feasible settings with w_sim * 0.9 > tau",
           "best": asdict(best), "best_objective": robust[0][1], "robust_feasible": len(robust),
           "top10": [{"params": r[0], "objective": r[1]} for r in feasible[:10]],
           "v1_objective": objective(v1_dev)[0],
           "dev_v2": evaluate(best), "dev_v1": v1_dev}
    (RESULTS / "dev_v2_tuning.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = tune(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
    print(json.dumps({k: r[k] for k in ("evaluated", "feasible", "best", "best_objective", "v1_objective")}, indent=1))
