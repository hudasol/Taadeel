"""Reference baselines for alignment, change classes and point in time answers.

A result such as "2425 of 2425 sections aligned" means little without a reference. This module
defines three deliberately simple methods that were fixed before they were run, and scores them
with the same ground truth and the same scoring code as the engine:

* ``by_number``   match articles that carry the same number and مكرر suffix. No text is read.
* ``greedy_text`` match each article to its most similar article in the other version by text only,
                  one to one, using the engine's own similarity and threshold. No order, no numbers.
* ``latest``      for point in time questions, always serve the newest snapshot.

Every aligner returns an ``AlignmentResult`` so the engine's own ``diff`` classifies the changes.
The change class numbers therefore differ between methods only because of the alignment. Nothing
here is tuned: the thresholds are the engine's, imported, not chosen.

Data: synthetic scenarios (labelled), and the committed UK validation corpus (English, OGL v3.0,
not UAE law). The UK ground truth is the stable section id, as in ``uk_validate``.
"""
from __future__ import annotations

import gzip
import json
import random
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from . import align as engine_v1
from . import align_v2
from .align import T_MATCH, Alignment, AlignmentResult, text_similarity
from .diff import diff
from .model import Expression
from .synthetic import make_pair
from .temporal import Version, as_of
from .uk_corpus import OUT as UK_CORPUS
from .uk_corpus import _expression
from .uk_validate import renumber_variant, truth_changes
from .validate import KINDS, SCENARIOS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "baselines.json"
HELD_START, HELD_N = 910_000, 100      # the seeds of the locked held out synthetic run (read only here)
RENUMBER_RUNS = 5
RENUMBER_SEED = 424242                  # the seed used by uk_validate for its renumbering variant

Aligner = Callable[[Expression, Expression], AlignmentResult]


def _finish(A, B, pairs: list[Alignment]) -> AlignmentResult:
    ma, mb = {p.a_eid for p in pairs}, {p.b_eid for p in pairs}
    return AlignmentResult(pairs=pairs, unaligned_a=[p.eid for p in A if p.eid not in ma],
                           unaligned_b=[p.eid for p in B if p.eid not in mb])


def by_number(a: Expression, b: Expression) -> AlignmentResult:
    A, B = a.articles(), b.articles()
    bk = {p.key: p for p in B}
    pairs = [Alignment(p.eid, bk[p.key].eid, 1.0, "high") for p in A if p.key in bk]
    return _finish(A, B, pairs)


def greedy_text(a: Expression, b: Expression) -> AlignmentResult:
    A, B = a.articles(), b.articles()
    cand = []
    for i, pa in enumerate(A):
        for j, pb in enumerate(B):
            s = text_similarity(pa.text_norm, pb.text_norm)
            if s >= T_MATCH:
                cand.append((s, i, j))
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    used_a, used_b, pairs = set(), set(), []
    for s, i, j in cand:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        pairs.append(Alignment(A[i].eid, B[j].eid, round(s, 4), "high"))
    pairs.sort(key=lambda p: [x.eid for x in A].index(p.a_eid))
    return _finish(A, B, pairs)


ALIGNERS: dict[str, Aligner] = {
    "by_number": by_number,
    "greedy_text": greedy_text,
    "engine_v1": engine_v1.align,
    "engine_v2": align_v2.align,
}


# ---- scoring ----------------------------------------------------------------------------
def _prf(tp: int, fp: int, fn: int) -> dict:
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None}


def evaluate_synthetic(aligner: Aligner, seeds: range, **kw) -> dict:
    tp, fp, fn = Counter(), Counter(), Counter()
    ok = total = 0
    for s in seeds:
        p = make_pair(s, **kw)
        res = aligner(p.a, p.b)
        got = {x.a_eid: x.b_eid for x in res.pairs}
        for a_eid, b_eid in p.gold_pairs.items():
            total += 1
            ok += got.get(a_eid) == b_eid
        pred = {(c.kind, c.a_eid, c.b_eid) for c in diff(p.a, p.b, res)}
        gold = {(g.kind, g.a_eid, g.b_eid) for g in p.gold_changes}
        for k in KINDS:
            pk, gk = {x for x in pred if x[0] == k}, {x for x in gold if x[0] == k}
            tp[k] += len(pk & gk)
            fp[k] += len(pk - gk)
            fn[k] += len(gk - pk)
    return {"documents": len(seeds), "alignment_accuracy": round(ok / total, 4),
            "classes": {k: _prf(tp[k], fp[k], fn[k]) for k in KINDS}}


def _eid_map(res: AlignmentResult) -> dict[str, str]:
    return {p.a_eid: p.b_eid for p in res.pairs}


def score_uk_pair(aligner: Aligner, a: Expression, b: Expression) -> dict:
    res = aligner(a, b)
    ta, tb = {p.eid: p.text for p in a.provisions}, {p.eid: p.text for p in b.provisions}
    shared = ta.keys() & tb.keys()
    pm = _eid_map(res)
    pred = {(c.a_eid, c.b_eid): c.kind for c in diff(a, b, res)}
    truth = truth_changes(a, b)
    cls: dict[str, Counter] = defaultdict(Counter)
    for k, v in truth.items():
        cls[v]["tp" if pred.get(k) == v else "fn"] += 1
    for k, v in pred.items():
        if truth.get(k) != v:
            cls[v]["fp"] += 1
    return {"shared": len(shared), "correct": sum(pm.get(e) == e for e in shared),
            "classes": {k: dict(v) for k, v in cls.items()}}


def _merge_uk(rows: list[dict]) -> dict:
    shared = sum(r["shared"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    cls: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for c, d in r["classes"].items():
            cls[c].update(d)
    return {"pairs": len(rows), "shared_sections": shared, "correct": correct,
            "alignment_accuracy": round(correct / shared, 4) if shared else None,
            "classes": {c: _prf(d.get("tp", 0), d.get("fp", 0), d.get("fn", 0)) for c, d in sorted(cls.items())}}


def load_uk(path: Path = UK_CORPUS) -> dict[str, list[Expression]]:
    out: dict[str, list[Expression]] = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["act"]].append(_expression(r))
    for v in out.values():
        v.sort(key=lambda e: e.valid_from)
    return dict(out)


def uk_windows(versions: list[Expression]) -> list[tuple[Expression, Expression]]:
    by = {e.valid_from: e for e in versions}
    return [(by[d - timedelta(days=1)], e) for d, e in sorted(by.items()) if d - timedelta(days=1) in by]


def evaluate_uk(aligner: Aligner, corpus: dict[str, list[Expression]]) -> dict:
    one_day, long_gap = [], []
    renum_ok = renum_total = 0
    for act, vs in sorted(corpus.items()):
        one_day += [score_uk_pair(aligner, a, b) for a, b in uk_windows(vs)]
        if len(vs) > 1:
            long_gap.append(score_uk_pair(aligner, vs[0], vs[-1]))
        rng = random.Random(f"{RENUMBER_SEED}-{act}")
        for _ in range(RENUMBER_RUNS):
            b, truth = renumber_variant(vs[-1], rng)
            pm = _eid_map(aligner(vs[-1], b))
            for a_eid, b_eid in truth.items():
                renum_total += 1
                renum_ok += pm.get(a_eid) == b_eid
    return {"one_day": _merge_uk(one_day), "long_gap": _merge_uk(long_gap),
            "renumbering_variant": {"sections": renum_total, "correct": renum_ok,
                                    "alignment_accuracy": round(renum_ok / renum_total, 4)}}


# ---- point in time ----------------------------------------------------------------------
def _same(a: Expression, b: Expression) -> bool:
    return {p.eid: p.text for p in a.provisions} == {p.eid: p.text for p in b.provisions}


def evaluate_point_in_time(corpus: dict[str, list[Expression]]) -> dict:
    """Query the day before and the day of each effect date; truth is the snapshot of that day."""
    tot = Counter()
    for vs in (v for _, v in sorted(corpus.items())):
        by = {e.valid_from: e for e in vs}
        effect_dates = [d for d in sorted(by) if d - timedelta(days=1) in by]
        timeline = [Version(by[vs[0].valid_from].expression_id, vs[0].valid_from, "known")]
        timeline += [Version(by[d].expression_id, d, "known") for d in effect_dates]
        ids = {e.expression_id: e for e in vs}
        for d in effect_dates:
            for q, kind in ((d - timedelta(days=1), "prior_day"), (d, "on_date")):
                truth = by[q]
                tot[f"{kind}_queries"] += 1
                served = ids.get(as_of(timeline, q).version_id or "")
                tot[f"{kind}_effect_dates"] += served is not None and _same(served, truth)
                tot[f"{kind}_latest"] += _same(vs[-1], truth)
    out = {}
    for method in ("effect_dates", "latest"):
        for kind in ("prior_day", "on_date"):
            n = tot[f"{kind}_queries"]
            out[f"{method}.{kind}"] = {"queries": n, "correct": tot[f"{kind}_{method}"],
                                       "accuracy": round(tot[f"{kind}_{method}"] / n, 4)}
    return out


def run() -> dict:
    held = range(HELD_START, HELD_START + HELD_N)
    corpus = load_uk()
    syn = {name: {sc: evaluate_synthetic(fn, held, **kw) for sc, kw in SCENARIOS.items()}
           for name, fn in ALIGNERS.items()}
    uk = {name: evaluate_uk(fn, corpus) for name, fn in ALIGNERS.items()}
    return {
        "scope": "Baselines scored with the same ground truth as the engine. Synthetic: the seeds of the locked "
                 "held out run, labelled synthetic. UK: committed corpus (English, OGL v3.0), not UAE law.",
        "methods": {"by_number": "same number and suffix, no text", "greedy_text": "best text match, one to one, no order or numbers",
                    "engine_v1": "locked default engine", "engine_v2": "pre registered v2, not the default"},
        "tuned": False,
        "synthetic": syn, "uk": uk, "point_in_time": evaluate_point_in_time(corpus),
    }


DOC = ROOT / "docs" / "BASELINES.md"
LABEL = {"by_number": "by number", "greedy_text": "greedy text", "engine_v1": "engine v1 (default)", "engine_v2": "engine v2"}


def _p(x) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def markdown(res: dict) -> str:
    M = list(ALIGNERS)
    L = ["<!-- Generated by `python -m taadeel.baselines` from results/baselines.json. Do not edit by hand. -->", "",
         "# Baselines", "",
         "Each method below is scored with the same ground truth and the same scoring code. Baselines were fixed before "
         "they were run and nothing was tuned. They are described in `src/taadeel/baselines.py`.", "",
         "* **by number**: match articles with the same number and suffix. Reads no text.",
         "* **greedy text**: match each article to its most similar article, one to one, by text only, at the engine's own threshold.",
         "* **engine v1 / v2**: the locked default engine and the pre registered v2.",
         "* All methods use the engine's own change classifier on top of their alignment, so differences come from alignment alone.", "",
         "## Synthetic, the seeds of the locked held out run", "",
         f"SYNTHETIC data, {res['synthetic'][M[0]][next(iter(SCENARIOS))]['documents']} documents per scenario. "
         "Alignment accuracy, then repealed recall and inserted recall.", "",
         "| scenario | " + " | ".join(LABEL[m] for m in M) + " |", "|---|" + "---|" * len(M)]
    for sc in SCENARIOS:
        cells = []
        for m in M:
            r = res["synthetic"][m][sc]
            cells.append(f"{_p(r['alignment_accuracy'])} / {_p(r['classes']['repealed']['recall'])} / {_p(r['classes']['inserted']['recall'])}")
        L.append(f"| {sc} | " + " | ".join(cells) + " |")
    L += ["", "## UK legislation, committed corpus", "",
          "English UK Acts, England and Wales view, Open Government Licence v3.0. Not UAE law. Ground truth is the stable section id. "
          "Alignment accuracy over sections present in both versions.", "",
          "| condition | " + " | ".join(LABEL[m] for m in M) + " |", "|---|" + "---|" * len(M)]
    for key, name in (("one_day", "one day windows (real edits)"), ("long_gap", "first against last snapshot (real edits)")):
        L.append(f"| {name} | " + " | ".join(
            f"{_p(res['uk'][m][key]['alignment_accuracy'])} ({res['uk'][m][key]['correct']} of {res['uk'][m][key]['shared_sections']})"
            for m in M) + " |")
    L.append("| real text, synthetic renumbering | " + " | ".join(
        f"{_p(res['uk'][m]['renumbering_variant']['alignment_accuracy'])} ({res['uk'][m]['renumbering_variant']['correct']} of {res['uk'][m]['renumbering_variant']['sections']})"
        for m in M) + " |")
    pit = res["point_in_time"]
    L += ["", "## Point in time, UK corpus", "",
          "Questions are the day before and the day of each effect date. Truth is the snapshot of that day.", "",
          "| method | day before | on the day |", "|---|---|---|"]
    for m, name in (("latest", "always serve the newest snapshot"), ("effect_dates", "version in force by effect dates (engine, `temporal.as_of`)")):
        a, b = pit[f"{m}.prior_day"], pit[f"{m}.on_date"]
        L.append(f"| {name} | {_p(a['accuracy'])} ({a['correct']} of {a['queries']}) | {_p(b['accuracy'])} ({b['correct']} of {b['queries']}) |")
    u, s1 = res["uk"], res["synthetic"]
    tm = "templated near-duplicates, small edits"
    L += ["", "## Reading these results", "",
          f"* On real UK edits, matching by number alone scores {_p(u['by_number']['one_day']['alignment_accuracy'])} on one day windows and "
          f"{_p(u['by_number']['long_gap']['alignment_accuracy'])} on long gaps, against {_p(u['engine_v1']['one_day']['alignment_accuracy'])} and "
          f"{_p(u['engine_v1']['long_gap']['alignment_accuracy'])} for engine v1. UK sections keep their numbers, so these two results do not "
          "separate the engine from a number lookup.",
          f"* Where numbers move, number matching breaks: with renumbering inserted into real text it scores "
          f"{_p(u['by_number']['renumbering_variant']['alignment_accuracy'])}, engine v1 {_p(u['engine_v1']['renumbering_variant']['alignment_accuracy'])} "
          f"and greedy text {_p(u['greedy_text']['renumbering_variant']['alignment_accuracy'])}. The renumbering is synthetic: it shows the mechanism, "
          "not how often UAE amendments renumber.",
          f"* Greedy text matching is a strong aligner when articles are distinct and the edits are small, and it matches or beats engine v1 on alignment accuracy in "
          f"{'; '.join(n for n in SCENARIOS if s1['greedy_text'][n]['alignment_accuracy'] >= s1['engine_v1'][n]['alignment_accuracy'])}. "
          f"It cannot tell a repealed article from a heavily edited one, so it forces matches: on the templated small edits scenario its repealed recall is "
          f"{_p(s1['greedy_text'][tm]['classes']['repealed']['recall'])} against {_p(s1['engine_v1'][tm]['classes']['repealed']['recall'])} for engine v1 "
          f"and {_p(s1['engine_v2'][tm]['classes']['repealed']['recall'])} for engine v2.",
          f"* Under heavy edits, order and position start to matter: with 40% of words edited greedy text scores "
          f"{_p(s1['greedy_text']['templated, 40% of words edited']['alignment_accuracy'])}, engine v1 "
          f"{_p(s1['engine_v1']['templated, 40% of words edited']['alignment_accuracy'])} and engine v2 "
          f"{_p(s1['engine_v2']['templated, 40% of words edited']['alignment_accuracy'])}.",
          f"* Serving the newest snapshot is a weak baseline for point in time questions ({_p(pit['latest.prior_day']['accuracy'])} the day before an effect date). "
          "The effect date method is much better but not certain, which is why the snapshot timeline reports uncertainty (`docs/VALIDATION_UK.md`).",
          "* No UAE data is involved anywhere on this page.", ""]
    return "\n".join(L)


def main() -> None:
    res = run()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    DOC.write_text(markdown(res), encoding="utf-8")
    print(f"wrote {OUT} and {DOC}")


if __name__ == "__main__":
    main()
