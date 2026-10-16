"""Second, larger English amendment sample (fetched 2026-10-16), measured once with frozen patterns.

Real English UK legislation, OGL v3.0. Not UAE law. The first sample (uk_amending.py, 48 sections) is
kept unchanged; this module adds NEW amending Act sections under a selection rule declared in
docs/DECISIONS.md before any of them was fetched:

* Candidates: the same rule as uk_amending.candidates() (recorded effects in the current XML of the 7
  validated Acts that name a UK Public General Act section), with no cap, minus every URL already in
  data/uk/amending_sample.json.
* Order: sha1(url) hex ascending; the first N_NEW are fetched (one request per 6 s, through the ingestor).
* Split: sha1(url) parity, as before (even = dev, odd = test).
* Patterns: amend_en.parse as frozen in the commit "Freeze English amendment patterns before the test
  half is measured" (the file hash is recorded in the result). None of the new sections was read before
  the patterns were frozen, so BOTH halves are out of sample for the frozen patterns; the split is kept
  so that any later pattern change can be tuned on dev and measured on test.
* Truth: recorded effects naming the amending section. Effects whose citation also names a schedule
  ("s. 159(3), Sch. 10 para. 48") are reported separately: their wording sits in the schedule, which is
  not fetched, so a parser reading the section text cannot find them.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys

from . import amend_en, clml
from .uk_amending import BASE
from .uk_amending_eval import KW, evaluate, split
from .uk_fetch import ROOT, fetch, make_ingestor, url_current
from .uk_validate import ACTS, effects_for

OLD = ROOT / "data" / "uk" / "amending_sample.json"
OUT = ROOT / "data" / "uk" / "amending_sample_2.json"
RESULT = ROOT / "results" / "uk_amending_2.json"
N_NEW = 150
_SCH = re.compile(r"\bSch(?:s)?\.\s*\d")


def candidates() -> list[dict]:
    ing = make_ingestor()
    old = {r["url"] for r in json.loads(OLD.read_text(encoding="utf-8"))}
    seen: dict[str, dict] = {}
    for act in ACTS:
        if ing.latest(url_current(act)) is None:
            continue
        for e in effects_for(ing, act):
            if e.status != "ok" or e.kind == "other" or not e.affecting_year or not e.affecting_chapter or not e.affecting_sections:
                continue
            if not re.search(r"\(c\. \d+\)", e.raw):
                continue
            if not (e.affecting_title or "").endswith(f"Act {e.affecting_year}"):
                continue
            sec = e.affecting_sections[0]
            url = f"{BASE}/ukpga/{e.affecting_year}/{e.affecting_chapter}/section/{sec}/enacted/data.xml"
            if url in old:
                continue
            cite = e.raw.split(" by ", 1)[-1].split(";")[0]
            rec = seen.setdefault(url, {"url": url, "affecting": e.affecting_title, "section": sec, "effects": []})
            rec["effects"].append({"act": act, "sections": [s.replace("section-", "") for s in e.sections],
                                   "kind": e.kind, "date": str(e.date), "via_schedule": bool(_SCH.search(cite)),
                                   "raw": e.raw[:240]})
    allc = sorted(seen.values(), key=lambda r: hashlib.sha1(r["url"].encode()).hexdigest())
    return allc


def fetch_sample() -> None:
    ing = make_ingestor()
    for act in ACTS:   # current XML (effects) of the 7 validated Acts; raw XML stays in snapshots/ (gitignored)
        fetch(ing, url_current(act))
    allc = candidates()
    print(f"candidates after excluding the first sample: {len(allc)}; fetching {min(N_NEW, len(allc))}", flush=True)
    out = []
    for c in allc[:N_NEW]:
        p = fetch(ing, c["url"])
        if p is None:
            c["text"], c["status"] = None, "not_available"
        else:
            root = clml.load(p)
            ps = [x for x in root.iter(clml.L + "P1") if (x.get("id") or "").startswith("section-")]
            c["text"] = clml.element_text(ps[0]) if ps else clml.element_text(root)
            c["status"] = "ok"
        out.append(c)
        print(c["status"], c["url"], flush=True)
    OUT.write_text(json.dumps({"candidates_total": len(allc), "n_new": N_NEW, "rows": out},
                              indent=1, ensure_ascii=False), encoding="utf-8")


def run() -> dict:
    if RESULT.exists():
        raise SystemExit(f"{RESULT.name} exists: the second sample is measured once. Not re-running.")
    data = json.loads(OUT.read_text(encoding="utf-8"))
    rows = data["rows"]
    ok = [r for r in rows if r["status"] == "ok" and r["text"]]
    bearing = [r for r in ok if KW.search(r["text"])]
    direct = lambda rs: [dict(r, effects=[e for e in r["effects"] if not e["via_schedule"]]) for r in rs]
    out = {"scope": "English UK Acts, OGL v3.0; not UAE law",
           "amend_en_sha256": hashlib.sha256((ROOT / "src" / "taadeel" / "amend_en.py").read_bytes()).hexdigest(),
           "candidates_total": data["candidates_total"], "fetched": len(rows), "readable": len(ok),
           "instruction_bearing": len(bearing), "split_rule": "sha1(url) parity: even=dev, odd=test"}
    for part in ("dev", "test", "all"):
        rs = bearing if part == "all" else [r for r in bearing if split(r) == part]
        out[part] = {"extended_patterns": evaluate(rs, True), "original_patterns": evaluate(rs, False),
                     "extended_patterns_direct_effects_only": evaluate(direct(rs), True)}
    RESULT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fetch":
        fetch_sample()
    elif cmd == "run":
        print(json.dumps(run(), indent=1))
    else:
        print("usage: fetch | run")
