"""Score an alignment function on SYNTHETIC scenarios with the same metrics as validate.run.

validate.py is used by the locked v1 protocol, so it is not edited; this module repeats its metric
definitions for any aligner (checked by tests/test_align_v2.py: v1 through this module equals
validate.run). Synthetic numbers measure engine correctness on generated text, not real law.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable

from .align import AlignmentResult
from .diff import diff
from .synthetic import SyntheticPair, make_pair
from .validate import KINDS

Aligner = Callable[[SyntheticPair], AlignmentResult]


def score_pairs(pairs: list[SyntheticPair], aligner: Aligner) -> dict:
    tp, fp, fn = Counter(), Counter(), Counter()
    align_correct = align_total = 0
    forced_repealed = forced_any = repealed_total = 0
    low_conf = pairs_total = 0
    for p in pairs:
        res = aligner(p)
        got = {x.a_eid: x.b_eid for x in res.pairs}
        for a_eid, b_eid in p.gold_pairs.items():
            align_total += 1
            align_correct += got.get(a_eid) == b_eid
        repealed = {g.a_eid for g in p.gold_changes if g.kind == "repealed"}
        repealed_total += len(repealed)
        forced_repealed += len(repealed & {x.a_eid for x in res.pairs if x.confidence == "high"})
        forced_any += len(repealed & set(got))
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
        "documents": len(pairs),
        "alignment_accuracy": align_correct / align_total,
        "forced_matches_on_repealed": forced_repealed,
        "forced_matches_on_repealed_incl_low": forced_any,
        "repealed_total": repealed_total,
        "low_confidence_pair_share": low_conf / pairs_total if pairs_total else None,
        "per_class": per_class,
    }


def run(seeds: range, aligner: Aligner, **kw) -> dict:
    return score_pairs([make_pair(s, **kw) for s in seeds], aligner)
