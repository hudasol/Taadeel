"""Serve the snapshot timeline (timeline_v2) through the API, from committed derived data.

timeline_v2.py holds the method and the pre registered evaluation; it is not edited here. Aligning
every pair of versions takes minutes, so ``build`` runs it once and writes the steps to
data/uk/timeline_steps.json.gz (derived from data/uk/corpus.jsonl.gz and the recorded effects in the
current XML of each Act retrieved 2026-10-16; English UK legislation, OGL v3.0, not UAE law). The API
then answers a date query by reading that file and the corpus, with no network and no alignment.

States: "certain" (one version, every change explained by a recorded effect), "uncertain" (a
snapshot shows changes no recorded effect of that date explains, or an effect names a section the
snapshot shows unchanged; candidate texts are listed, none is chosen), "not_in_force" (date before
the first snapshot). Each article carries the source URL and retrieval time of the snapshot its
text comes from.
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import date
from functools import lru_cache

from .timeline_v2 import Step, answer, build_steps
from .uk_corpus import ROOT

STEPS = ROOT / "data" / "uk" / "timeline_steps.json.gz"
METHOD = ("Versions come from snapshots on recorded effect dates; a change visible between two snapshots that no recorded "
          "effect of that date explains marks the dates before it as uncertain.")


def _eff_dates(exps, effs) -> list[date]:
    by = {e.valid_from for e in exps}
    from datetime import timedelta
    return sorted({e.date for e in effs if e.status == "ok" and e.sections and e.kind != "other" and e.date
                   and e.date in by and e.date - timedelta(days=1) in by and e.date > exps[0].valid_from})


def build() -> int:
    """Run once, offline (slow): needs the current XML of each Act in snapshots/uk (not committed)."""
    from .heldout_v2 import uk_snapshots
    from .uk_fetch import make_ingestor
    from .uk_validate import effects_for

    ing = make_ingestor()
    rows = []
    for act, exps in uk_snapshots().items():
        effs = effects_for(ing, act)
        by = {e.valid_from: e for e in exps}
        versions = [exps[0]] + [by[d] for d in _eff_dates(exps, effs)]
        steps = build_steps(versions, effs)
        rows.append({"work_id": f"uk/{act}", "versions": [v.expression_id for v in versions],
                     "steps": [{"date": s.date.isoformat(), "explained": s.explained, "unexplained": s.unexplained,
                                "conflicts": s.conflicts} for s in steps]})
    with gzip.open(STEPS, "wt", encoding="utf-8") as f:
        json.dump({"data": "derived from data/uk/corpus.jsonl.gz and recorded effects retrieved 2026-10-16; "
                           "English UK legislation, OGL v3.0; not UAE law", "acts": rows}, f, ensure_ascii=False)
    return len(rows)


@lru_cache(maxsize=1)
def _load() -> dict:
    from .heldout_v2 import uk_snapshots

    if not STEPS.exists():
        return {}
    snaps = {f"uk/{a}": {e.expression_id: e for e in exps} for a, exps in uk_snapshots().items()}
    with gzip.open(STEPS, "rt", encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for r in data["acts"]:
        exps = snaps.get(r["work_id"], {})
        versions = [exps[v] for v in r["versions"] if v in exps]
        steps = [Step(date.fromisoformat(s["date"]), [tuple(x) for x in s["explained"]],
                      [tuple(x) for x in s["unexplained"]], s["conflicts"]) for s in r["steps"]]
        if len(versions) == len(r["versions"]):
            out[r["work_id"]] = (versions, steps)
    return out


def works() -> list[str]:
    return sorted(_load())


def example() -> dict | None:
    """First date that falls in an interval with an unexplained snapshot change (shows the uncertain state)."""
    from datetime import timedelta

    for w, (versions, steps) in sorted(_load().items()):
        for k, st in enumerate(steps):
            d = st.date - timedelta(days=1)
            if st.unexplained and d > versions[k].valid_from:
                return {"work": w, "date": d.isoformat()}
    return None


def _articles(texts: dict[str, str], primary, secondary=None) -> list[dict]:
    """Articles of a candidate, each with the provenance of the snapshot its text comes from."""
    prov = {}
    for e in (primary, secondary):
        if e is not None:
            for p in e.provisions:
                if p.text == texts.get(p.eid) and p.eid not in prov:
                    prov[p.eid] = (e, p)
    out = []
    for eid, text in texts.items():
        e, p = prov.get(eid, (primary, None))
        out.append({"eid": eid, "number": None if p is None else p.number, "text": text,
                    "source_url": e.source_url, "retrieved_at": e.retrieved_at})
    return out


def query(work_id: str, d: date) -> dict | None:
    loaded = _load().get(work_id)
    if loaded is None:
        return None
    versions, steps = loaded
    a = answer(versions, steps, d)
    k = max((i for i, v in enumerate(versions) if v.valid_from <= d), default=-1)
    evidence: dict = {"method": METHOD}
    cands = []
    if a.certainty != "not_in_force":
        cur = versions[k]
        evidence["version_from"] = cur.valid_from.isoformat()
        evidence["version_basis"] = "first snapshot" if k == 0 else "recorded effect dated " + cur.valid_from.isoformat()
        cands.append({"label": "version in force by the recorded effects", "basis": "recorded_effect",
                      "version_id": cur.expression_id, "articles": _articles(a.candidates[0], cur)})
        if len(a.candidates) > 1:
            st, nxt = steps[k], versions[k + 1]
            evidence.update({"next_snapshot": nxt.valid_from.isoformat(),
                             "unexplained_changes": [{"kind": c[0], "before": c[1], "after": c[2]} for c in st.unexplained],
                             "explained_changes": len(st.explained)})
            cands.append({"label": "the same version with the unexplained changes already in force", "basis": "snapshot_difference",
                          "version_id": None, "articles": _articles(a.candidates[1], cur, nxt)})
        elif a.certainty == "uncertain" and k >= 1:
            evidence["conflicts"] = steps[k - 1].conflicts
    return {"work_id": work_id, "as_of": d.isoformat(), "certainty": a.certainty, "note": a.note,
            "evidence": evidence, "candidates": cands}


if __name__ == "__main__":
    if (sys.argv[1:] or [""])[0] == "build":
        print("acts written:", build())
    else:
        print("usage: python -m taadeel.timeline_service build")
