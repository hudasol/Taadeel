"""M6 validation harness. Scores the engine on labeled data and prints a report.

IMPORTANT: the built-in run uses SYNTHETIC data only. It measures engine
correctness against known operations, not accuracy on real UAE legislation.
A real hand-checked gold set must be added under data/gold/ once a source with
permitted use exists (see docs/DATA_SOURCES.md).
"""
from __future__ import annotations

import json
import sys
from collections import Counter

from .align import align
from .diff import diff
from .synthetic import make_pair

KINDS = ["inserted", "replaced", "repealed", "renumbered", "clarified"]


def run(seeds: range, **kw) -> dict:
    tp, fp, fn = Counter(), Counter(), Counter()
    align_correct = align_total = 0
    forced_repealed = repealed_total = 0
    low_conf = pairs_total = 0
    for s in seeds:
        p = make_pair(s, **kw)
        res = align(p.a, p.b)
        got = {x.a_eid: x.b_eid for x in res.pairs}
        for a_eid, b_eid in p.gold_pairs.items():
            align_total += 1
            align_correct += got.get(a_eid) == b_eid
        repealed = {g.a_eid for g in p.gold_changes if g.kind == "repealed"}
        repealed_total += len(repealed)
        forced_repealed += len(repealed & set(got))
        pairs_total += len(res.pairs)
        low_conf += sum(1 for x in res.pairs if x.confidence == "low")
        pred = {(c.kind, c.a_eid, c.b_eid) for c in diff(p.a, p.b, res)}
        gold = {(g.kind, g.a_eid, g.b_eid) for g in p.gold_changes}
        for k in KINDS:
            pk = {x for x in pred if x[0] == k}
            gk = {x for x in gold if x[0] == k}
            tp[k] += len(pk & gk)
            fp[k] += len(pk - gk)
            fn[k] += len(gk - pk)
    per_class = {}
    for k in KINDS:
        prec = tp[k] / (tp[k] + fp[k]) if tp[k] + fp[k] else None
        rec = tp[k] / (tp[k] + fn[k]) if tp[k] + fn[k] else None
        per_class[k] = {"precision": prec, "recall": rec, "support": tp[k] + fn[k]}
    return {
        "data": "SYNTHETIC (engine correctness only, not real-world accuracy)",
        "documents": len(seeds),
        "alignment_accuracy": align_correct / align_total,
        "forced_matches_on_repealed": forced_repealed,
        "repealed_total": repealed_total,
        "low_confidence_pair_share": low_conf / pairs_total if pairs_total else None,
        "per_class": per_class,
    }


if __name__ == "__main__":
    out = run(range(int(sys.argv[1]) if len(sys.argv) > 1 else 100))
    print(json.dumps(out, ensure_ascii=False, indent=2))
