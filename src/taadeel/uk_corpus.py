"""Derived UK corpus for the validation view (corpus 'uk-validation').

Real English UK legislation, England and Wales view, Open Government Licence v3.0.
Contains public sector information licensed under the Open Government Licence v3.0.
It exists to validate the engine and is NOT UAE law. Raw XML is not committed; this module writes a
compact derived file (section text per dated snapshot, with the source URL and retrieval time of each
snapshot) that the demo store loads.
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

from .labels import suffix_value

ROOT = Path(os.environ.get("TAADEEL_ROOT") or Path(__file__).resolve().parents[2])

OUT = ROOT / "data" / "uk" / "corpus.jsonl.gz"
CHANGES = ROOT / "data" / "uk" / "changes.jsonl.gz"   # engine output (locked engine) for consecutive snapshots
LICENCE = "OGL-3.0 (Open Government Licence v3.0, https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)"
ATTRIBUTION = ("Contains public sector information licensed under the Open Government Licence v3.0. "
               "Source: legislation.gov.uk. England and Wales view; schedules omitted.")


def build(acts: list[str] | None = None, out: Path = OUT) -> int:
    from . import clml
    from .uk_fetch import make_ingestor, plan_snapshots, url_at, url_current
    from .uk_validate import ACTS

    ing = make_ingestor()
    n = 0
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for act in acts or ACTS:
            cur = ing.latest(url_current(act))
            if cur is None:
                continue
            import re
            title = re.search(r"<dc:title>([^<]*)", Path(cur.path).read_text(encoding="utf-8")).group(1)
            for d in sorted(plan_snapshots(act, ing)):
                s = ing.latest(url_at(act, d))
                if s is None:
                    continue
                secs = [x for x in clml.parse_sections(clml.load(s.path)) if not x.placeholder]
                f.write(json.dumps({"act": act, "title": title, "date": d, "source_url": s.url,
                                    "retrieved_at": s.retrieved_at, "sha256": s.sha256,
                                    "sections": [[x.eid, x.number, x.suffix, x.text] for x in secs]},
                                   ensure_ascii=False) + "\n")
                n += 1
    return n


def _expression(r: dict):
    from datetime import date

    from .model import Expression, Provision

    provs = [Provision(eid=e, kind="article", number=num, bis=suffix_value(suf), text=t)
             for e, num, suf, t in r["sections"]]
    return Expression(work_id=f"uk/{r['act']}", expression_id=f"uk/{r['act']}@{r['date']}",
                      source_url=r["source_url"], retrieved_at=r["retrieved_at"], language="en",
                      valid_from=date.fromisoformat(r["date"]), effective_status="known", provisions=provs)


def build_changes(path: Path = OUT, out: Path = CHANGES) -> int:
    """Run the locked engine on consecutive snapshots and save the changes (slow, run offline)."""
    from dataclasses import asdict

    from .align import align
    from .diff import diff

    prev: dict = {}
    n = 0
    with gzip.open(path, "rt", encoding="utf-8") as f, gzip.open(out, "wt", encoding="utf-8") as g:
        for line in f:
            ex = _expression(json.loads(line))
            a = prev.get(ex.work_id)
            if a is not None and a.valid_from != ex.valid_from:
                ch = [asdict(c) for c in diff(a, ex, align(a, ex))]
                g.write(json.dumps({"work_id": ex.work_id, "from": a.expression_id, "to": ex.expression_id,
                                    "changes": ch}, ensure_ascii=False) + "\n")
                n += len(ch)
            prev[ex.work_id] = ex
    return n


def load_into(store, path: Path = OUT, changes: Path = CHANGES) -> int:
    if not path.exists():
        return 0
    n = 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            store.add_expression(_expression(r), "uk-validation", title=r["title"] + " (England and Wales view)",
                                 jurisdiction="GB", licence=LICENCE, attribution=ATTRIBUTION)
            n += 1
    if changes.exists():
        with gzip.open(changes, "rt", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                store.add_changes(c["work_id"], c["from"], c["to"], c["changes"])
    return n


if __name__ == "__main__":
    print("snapshots written:", build())
    print("changes written:", build_changes())
