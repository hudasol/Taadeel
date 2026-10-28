"""Fetch amending Act sections (politely) to test English amendment by reference parsing.

Real English UK legislation, OGL v3.0. Truth = the recorded effects (Commentary Type F) in the
affected Acts: each effect names the affecting Act (chapter) and affecting section.
Only Public General Acts and body sections are fetched (not Statutory Instruments, not schedules).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from . import clml
from .uk_fetch import ROOT, fetch, make_ingestor, url_current
from .uk_validate import ACTS, effects_for

BASE = "https://www.legislation.gov.uk"
OUT = ROOT / "data" / "uk" / "amending_sample.json"
N_MAX = 48


def candidates() -> list[dict]:
    ing = make_ingestor()
    seen: dict[str, dict] = {}
    for act in ACTS:
        if ing.latest(url_current(act)) is None:
            continue
        for e in effects_for(ing, act):
            if e.status != "ok" or e.kind == "other" or not e.affecting_year or not e.affecting_chapter or not e.affecting_sections:
                continue
            if not re.search(r"\(c\. \d+\)", e.raw) or " Sch." in e.raw.split(" by ", 1)[-1].split(";")[0] and False:
                continue
            m = re.search(r"\(c\. (\d+)\)", e.raw)
            # Public General Acts of the UK only: title ends with Act YYYY and chapter is Arabic numeral
            if not (e.affecting_title or "").endswith(f"Act {e.affecting_year}"):
                continue
            sec = e.affecting_sections[0]
            url = f"{BASE}/ukpga/{e.affecting_year}/{e.affecting_chapter}/section/{sec}/enacted/data.xml"
            rec = seen.setdefault(url, {"url": url, "affecting": e.affecting_title, "section": sec, "effects": []})
            rec["effects"].append({"act": act, "sections": [s.replace("section-", "") for s in e.sections],
                                   "kind": e.kind, "date": str(e.date), "raw": e.raw[:240]})
    allc = sorted(seen.values(), key=lambda r: hashlib.sha1(r["url"].encode()).hexdigest())
    return allc[:N_MAX]


def main() -> None:
    ing = make_ingestor()
    out = []
    for c in candidates():
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
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
