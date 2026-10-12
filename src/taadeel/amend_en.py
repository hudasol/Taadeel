"""English (UK drafting style) amendment by reference patterns.

Status: the English patterns are validated separately against recorded effects (see
uk_validate.py); this module on its own is not evidence of accuracy. The sister module
amend_ar is unvalidated on real UAE text.

Covers four instruction shapes: "For section N substitute ...", "Omit section N",
"After section N insert ...", "section N is repealed". Only whole sections are handled;
subsection, paragraph and word level instructions ("In section 3(2), for ...") are not.
Spans index the raw input string.
"""
from __future__ import annotations

import re

from .amend_common import Amendment

_N = r"\d+(?-i:[A-Z]{0,3})"                       # 3, 3A, 3ZA
_LIST = rf"{_N}(?:\s*(?:,|and)\s*{_N})*"
_SEP = r"[\u2014\u2013:,\-]*\s*"
_FLAGS = re.I

_SUB = re.compile(rf"(?<!\w)for\s+section\s+(?P<n>{_N})\s*,?\s*substitute\b{_SEP}", _FLAGS)
_OMIT = re.compile(rf"(?<!\w)omit\s+sections?\s+(?P<list>{_LIST})", _FLAGS)
_AFTER = re.compile(rf"(?<!\w)after\s+section\s+(?P<n>{_N})\s*,?\s*insert\b{_SEP}", _FLAGS)
_REPEALED = re.compile(rf"(?<!\w)sections?\s+(?P<list>{_LIST})\s+(?:is|are)\s+repealed", _FLAGS)
# Extended patterns (added after reading the DEV half of the amending sample only, see uk_amending_eval.py)
_SUB_OF = re.compile(rf"(?<!\w)for\s+section\s+(?P<n>{_N})\s+of\s+[^\u2014\u2013:]{{0,200}}?,?\s*substitute\b{_SEP}", _FLAGS)
_AFTER_OF = re.compile(rf"(?<!\w)after\s+section\s+(?P<n>{_N})\s+of\s+[^\u2014\u2013:]{{0,200}}?\s*,?\s*insert\b{_SEP}", _FLAGS)
_IN_SECTION = re.compile(rf"(?<!\w)in\s+section\s+(?P<n>{_N})\b(?P<ctx>[^.;]{{0,320}}?)\b(?P<v>substitute|omit|insert)\b", _FLAGS)
_NUMS = re.compile(_N)
_LEAD_NUM = re.compile(r"^[\"'\u201c‘\s]*(?P<n>\d+[A-Z]{1,3})\b")


def _clean(s: str) -> str | None:
    s = s.strip().lstrip("\u2014\u2013:-").strip()
    return s or None


def parse(text: str, extended: bool = True) -> list[Amendment]:
    """Parse English amendment instructions in ``text`` into Amendment records.

    ``extended=False`` uses only the four original whole section shapes (kept for the baseline measurement).
    """
    found = []  # (start, end, kind, match)
    rules = [("sub", _SUB), ("omit", _OMIT), ("after", _AFTER), ("rep", _REPEALED)]
    if extended:
        rules += [("sub", _SUB_OF), ("after", _AFTER_OF), ("insec", _IN_SECTION)]
    for kind, rx in rules:
        for m in rx.finditer(text):
            found.append((m.start(), m.end(), kind, m))
    found.sort(key=lambda f: (f[0], -(f[1] - f[0])))
    kept, last = [], -1
    for f in found:
        if f[0] >= last:
            kept.append(f)
            last = f[1]
    out: list[Amendment] = []
    for i, (s, e, kind, m) in enumerate(kept):
        nxt = kept[i + 1][0] if i + 1 < len(kept) else len(text)
        span = (s, e)
        if kind == "insec":
            op = {"substitute": "substitute", "omit": "repeal", "insert": "insert"}[m.group("v").lower()]
            out.append(Amendment(op, m.group("n"), 0, None, span, "en.in_section.text", 0.6,
                                 paragraph="text", anchor=m.group("n"), lang="en"))
        elif kind in ("omit", "rep"):
            pid = "en.omit.section" if kind == "omit" else "en.repealed.section"
            for n in _NUMS.finditer(m.group("list")):
                out.append(Amendment("repeal", n.group(0), 0, None, span, pid, 0.9, lang="en"))
        elif kind == "sub":
            out.append(Amendment("substitute", m.group("n"), 0, _clean(text[e:nxt]), span,
                                 "en.for.substitute", 0.9, lang="en"))
        else:
            body = _clean(text[e:nxt])
            lead = _LEAD_NUM.match(body) if body else None
            if lead:
                out.append(Amendment("insert", lead.group("n"), 0, body, span, "en.after.insert", 0.85,
                                     anchor=m.group("n"), lang="en"))
            else:  # new number not stated: report the anchor, flagged by lower confidence
                out.append(Amendment("insert", m.group("n"), 0, body, span, "en.after.insert", 0.5,
                                     anchor=m.group("n"), lang="en"))
    return out
