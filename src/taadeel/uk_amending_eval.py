"""Measure English amendment pattern parsing against recorded effects (UK, OGL v3.0).

Sample: amending Act sections fetched by uk_amending.py. Selection of instruction bearing sections is by
keyword (independent of the parser). Split dev/test by SHA-1 parity of the URL. Patterns were extended
after reading the DEV half only; the TEST half is measured once for each pattern set.
Truth: a recorded effect (Commentary Type F) naming the amending section. An effect is "found" when the
parser returns an instruction whose target (or anchor, for insertions) matches an affected section label
of that effect; for whole section effects the operation must also agree. Text level effects accept any op.
Precision is a lower bound: instructions aimed at Acts outside the 7 validated ones have no recorded
effect here and count as unmatched.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import amend_en
from .uk_fetch import ROOT

SRC = ROOT / "data" / "uk" / "amending_sample.json"
OUT = ROOT / "results" / "uk_amending.json"
KW = re.compile(r"\b(substitute|insert|omit|repealed|is amended|are amended|for section)\b", re.I)
KIND_OP = {"section_inserted": "insert", "section_repealed": "repeal", "section_substituted": "substitute"}


def split(r: dict) -> str:
    return "dev" if int(hashlib.sha1(r["url"].encode()).hexdigest(), 16) % 2 == 0 else "test"


def _base(lbl: str) -> str:
    return re.match(r"\d+", lbl).group(0) if re.match(r"\d+", lbl) else lbl


def evaluate(rows: list[dict], extended: bool) -> dict:
    eff_total = eff_found = 0
    instr = instr_match = 0
    secs_with_instr = 0
    for r in rows:
        am = amend_en.parse(r["text"] or "", extended=extended)
        if am:
            secs_with_instr += 1
        keys = []
        for a in am:
            keys.append((a.op, a.target, a.anchor))
        matched_instr = set()
        for e in r["effects"]:
            eff_total += 1
            ok = False
            for i, a in enumerate(am):
                tl = [x for x in e["sections"]]
                hit = any(a.target == t or (a.op == "insert" and a.anchor and _base(t) == _base(a.anchor)) for t in tl)
                if not hit:
                    continue
                if e["kind"] in KIND_OP and a.op != KIND_OP[e["kind"]]:
                    continue
                ok = True
                matched_instr.add(i)
            eff_found += ok
        instr += len(am)
        instr_match += len(matched_instr)
    return {"sections": len(rows), "sections_with_parsed_instruction": secs_with_instr,
            "recorded_effects": eff_total, "effects_found": eff_found,
            "recall": round(eff_found / eff_total, 4) if eff_total else None,
            "parsed_instructions": instr, "instructions_matching_a_recorded_effect": instr_match,
            "precision_lower_bound": round(instr_match / instr, 4) if instr else None}


def run() -> dict:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    ok = [r for r in data if r["status"] == "ok" and r["text"]]
    bearing = [r for r in ok if KW.search(r["text"])]
    out = {"scope": "English UK Acts, OGL v3.0; not UAE law", "fetched": len(data), "readable": len(ok),
           "instruction_bearing": len(bearing), "split_rule": "sha1(url) parity: even=dev, odd=test"}
    for part in ("dev", "test"):
        rows = [r for r in bearing if split(r) == part]
        out[part] = {"original_patterns": evaluate(rows, False), "extended_patterns": evaluate(rows, True)}
    return out


if __name__ == "__main__":
    import sys
    r = run()
    if "--dev-only" in sys.argv:
        print(json.dumps(r["dev"], indent=1)); print({k: v for k, v in r.items() if k not in ("dev", "test")})
    else:
        OUT.write_text(json.dumps(r, indent=1), encoding="utf-8"); print(json.dumps(r, indent=1))
