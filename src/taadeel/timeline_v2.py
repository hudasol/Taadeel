"""Point in time from snapshots: discover change points that recorded effects omit, and say "uncertain".

``temporal.py`` (hash locked) answers a date query from a list of versions with known effective dates.
On UK data, building those versions from recorded effects alone served the wrong text for 17 of 80
queries on the day before a change (docs/VALIDATION_UK.md): the text changed on a date the effects
do not give. This module adds evidence from the snapshots themselves, without editing temporal.py.

Method (per Act):
* Versions V_0 (first snapshot) and V_k (snapshot on the k-th recorded effect date E_k), as before.
* For each step V_{k-1} -> V_k the locked engine (align + diff, v1) lists the changed sections. A
  change is *explained* when a recorded effect dated E_k names that section; otherwise it is
  *unexplained*: it happened at some date in (E_{k-1}, E_k] that the effects do not give.
* A query strictly between E_{k-1} and E_k is answered "uncertain" when step k has an unexplained
  change, with two candidate texts: V_{k-1}, and V_{k-1} with the unexplained changes applied.
  Otherwise it is answered "certain" with V_{k-1}, as before.
* *Conflict*: an effect dated E_k names a section that the snapshots show unchanged at E_k. The
  query on E_k is then flagged "uncertain" (the served text is the snapshot itself, so this is a
  warning, not a different answer).

Evaluation (``run``): the same 80 queries on the day before each effect date, truth = the
independently fetched snapshot on that day, which the method never reads. Effects come from the
current XML retrieved 2026-10-16; snapshots from data/uk/corpus.jsonl.gz (retrieved 2026-10-12).
English UK legislation only (OGL v3.0); nothing here is evidence about UAE law.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from .align import align
from .diff import diff
from .heldout import DOCS, RESULTS
from .heldout_v2 import uk_snapshots
from .model import Expression
from .temporal import Version, as_of
from .uk_fetch import make_ingestor
from .uk_validate import effects_for

OUT = RESULTS / "uk_timeline_v2.json"


@dataclass
class Step:
    date: date
    explained: list[tuple] = field(default_factory=list)
    unexplained: list[tuple] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)      # effect names a section the snapshot shows unchanged


@dataclass
class Answer:
    as_of: date
    certainty: str                   # certain | uncertain | not_in_force
    candidates: list[dict]           # eid -> text, first is the version v1 would serve
    note: str = ""


def _texts(e: Expression) -> dict[str, str]:
    return {p.eid: p.text for p in e.provisions}


def effect_sections(effs, d: date) -> set[str]:
    return {sid for e in effs if e.status == "ok" and e.kind != "other" and e.date == d for sid in e.sections}


def build_steps(versions: list[Expression], effs) -> list[Step]:
    steps = []
    for a, b in zip(versions, versions[1:]):
        named = effect_sections(effs, b.valid_from)
        st = Step(b.valid_from)
        touched = set()
        for c in diff(a, b, align(a, b)):
            sid = c.b_eid or c.a_eid
            touched |= {c.a_eid, c.b_eid}
            (st.explained if (c.a_eid in named or c.b_eid in named) else st.unexplained).append((c.kind, c.a_eid, c.b_eid))
        st.conflicts = sorted(named - touched)
        steps.append(st)
    return steps


def apply_changes(base: dict[str, str], new: dict[str, str], changes: list[tuple]) -> dict[str, str]:
    out = dict(base)
    for kind, a_eid, b_eid in changes:
        if a_eid is not None:
            out.pop(a_eid, None)
        if b_eid is not None:
            out[b_eid] = new[b_eid]
    return out


def answer(versions: list[Expression], steps: list[Step], d: date) -> Answer:
    if d < versions[0].valid_from:
        return Answer(d, "not_in_force", [])
    k = max(i for i, v in enumerate(versions) if v.valid_from <= d)
    cur = _texts(versions[k])
    if k + 1 < len(versions):
        st = steps[k]
        if st.unexplained and d < st.date:
            hyb = apply_changes(cur, _texts(versions[k + 1]), st.unexplained)
            return Answer(d, "uncertain", [cur, hyb],
                          f"{len(st.unexplained)} change(s) visible in the snapshot of {st.date} are not explained by any "
                          f"recorded effect of that date; they took effect on an unknown date after {versions[k].valid_from}.")
    if k >= 1 and steps[k - 1].conflicts and d == versions[k].valid_from:
        return Answer(d, "uncertain", [cur], "a recorded effect of this date names a section the snapshot shows unchanged")
    return Answer(d, "certain", [cur])


def eval_act(act: str, exps: list[Expression], effs) -> dict:
    by_date = {e.valid_from: e for e in exps}
    eff_dates = sorted({e.date for e in effs if e.status == "ok" and e.sections and e.kind != "other" and e.date
                        and e.date in by_date and e.date - timedelta(days=1) in by_date and e.date > exps[0].valid_from})
    versions = [exps[0]] + [by_date[d] for d in eff_dates]
    steps = build_steps(versions, effs)
    old_versions = [Version(v.expression_id, v.valid_from, "known") for v in versions]
    ids = {v.expression_id: v for v in versions}
    c = Counter()
    rows = []
    for d in eff_dates:
        q = d - timedelta(days=1)
        truth = _texts(by_date[q])
        # old method: temporal.as_of over effect versions
        old = as_of(old_versions, q)
        old_ok = old.version_id is not None and _texts(ids[old.version_id]) == truth
        c["queries"] += 1
        c["old_correct"] += old_ok
        a = answer(versions, steps, q)
        hit = [i for i, cand in enumerate(a.candidates) if cand == truth]
        if a.certainty == "certain":
            c["new_certain_correct" if hit else "new_certain_wrong"] += 1
        else:
            c["new_uncertain_truth_in_candidates" if hit else "new_uncertain_truth_missing"] += 1
            if hit == [0]:
                c["new_uncertain_truth_is_first_candidate"] += 1
        rows.append({"query": q.isoformat(), "old_correct": old_ok, "new": a.certainty,
                     "truth_candidate_index": hit[0] if hit else None, "note": a.note})
    c["steps_with_unexplained_change"] = sum(1 for s in steps if s.unexplained)
    c["steps_with_conflict"] = sum(1 for s in steps if s.conflicts)
    c["steps"] = len(steps)
    return {"act": act, **dict(c), "rows": rows}


def run() -> dict:
    if OUT.exists():
        raise SystemExit(f"{OUT.name} exists: run once only. Not re-running.")
    ing = make_ingestor()
    snaps = uk_snapshots()
    acts = [eval_act(act, exps, effects_for(ing, act)) for act, exps in snaps.items()]
    keys = ["queries", "old_correct", "new_certain_correct", "new_certain_wrong", "new_uncertain_truth_in_candidates",
            "new_uncertain_truth_missing", "new_uncertain_truth_is_first_candidate", "steps", "steps_with_unexplained_change",
            "steps_with_conflict"]
    tot = {k: sum(a.get(k, 0) for a in acts) for k in keys}
    out = {"scope": "English UK legislation (OGL v3.0), England and Wales view; not UAE law",
           "effects_retrieved": "current XML of each Act, 2026-10-16", "snapshots": "data/uk/corpus.jsonl.gz (2026-10-12)",
           "total": tot, "acts": acts}
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    return out


if __name__ == "__main__":
    if (sys.argv[1:] or [""])[0] == "run":
        print(json.dumps(run()["total"], indent=1))
    else:
        print("usage: python -m taadeel.timeline_v2 run")
