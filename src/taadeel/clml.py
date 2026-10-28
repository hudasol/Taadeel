"""CLML (legislation.gov.uk XML) -> sections and recorded effects.

Real English UK legislation, Open Government Licence v3.0. Used only to validate the engine.
Contains public sector information licensed under the Open Government Licence v3.0.

Scope decisions (documented, deliberate):
* Unit = body section (``P1`` with id ``section-*``); schedules are out of scope.
* England & Wales view: elements restricted to Scotland / Northern Ireland only are dropped.
* A section whose text is only a repeal placeholder (". . . .") is treated as absent.
* Effects come from footnotes of Type F (textual amendments) anchored to a section by the
  position of their inline marker, not by parsing the prose; the prose gives kind and date.
* If an effect's date or extent cannot be parsed with confidence, it is kept with
  ``status != 'ok'`` and is never silently guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from lxml import etree

NS = "http://www.legislation.gov.uk/namespaces/legislation"
L = "{" + NS + "}"

INLINE = {"Addition", "Substitution", "Repeal", "Emphasis", "Abbreviation", "Citation", "CitationSubRef",
          "Term", "Definition", "InlineAmendment", "Underline", "Superior", "Inferior", "Strong", "Span",
          "Acronym", "Character", "Expanded", "Uppercase", "SmallCaps", "Proviso", "Importance"}
SKIP_TAGS = {"CommentaryRef", "Pnumber"}


def _tag(e) -> str:
    return e.tag.replace(L, "") if isinstance(e.tag, str) else ""


def _in_view(e, view: str = "EW") -> bool:
    ext = e.get("RestrictExtent")
    if not ext:
        return True
    toks = {t for t in ext.split("+")}
    return bool(toks & set(view)) if view == "EW" else bool(toks)


def _collect(e, out: list[str], top: bool = True) -> None:
    tag = _tag(e)
    if not top and (tag in SKIP_TAGS or not _in_view(e)):
        return
    block = tag not in INLINE
    if block:
        out.append(" ")
    if e.text:
        out.append(e.text)
    for c in e:
        if isinstance(c.tag, str):
            _collect(c, out, top=False)
        if c.tail:
            out.append(c.tail)
    if block:
        out.append(" ")


_WS = re.compile(r"\s+")


def element_text(e) -> str:
    out: list[str] = []
    _collect(e, out)
    return _WS.sub(" ", "".join(out)).strip()


@dataclass
class Section:
    eid: str                 # e.g. "section-3ZA"
    label: str               # "3ZA"
    number: int
    suffix: str
    title: str
    text: str                # title + body, England & Wales view
    placeholder: bool        # True if the section is only a repeal placeholder
    uri: str


_LABEL = re.compile(r"^(\d+)([A-Z]*)$")


def parse_sections(root) -> list[Section]:
    sections: list[Section] = []
    for p1 in root.iter(L + "P1"):
        pid = p1.get("id") or ""
        if not pid.startswith("section-"):
            continue
        grp0 = p1.getparent()
        if not _in_view(p1) or (grp0 is not None and not _in_view(grp0)):
            continue                                       # e.g. a Northern Ireland only version of the same id
        label = pid[len("section-"):]
        m = _LABEL.match(label)
        if not m:
            continue
        title = ""
        grp = p1.getparent()
        if grp is not None and _tag(grp) == "P1group":
            t = grp.find(L + "Title")
            if t is not None:
                title = element_text(t)
        body = element_text(p1)
        if body.startswith(label):                         # drop the section number itself
            body = body[len(label):].strip()
        has_words = bool(re.search(r"[A-Za-z0-9]", body))
        sections.append(Section(pid, label, int(m.group(1)), m.group(2), title,
                                (title + " " + body).strip() if has_words else "", not has_words,
                                p1.get("IdURI") or p1.get("DocumentURI") or ""))
    return sections


# ---- effects --------------------------------------------------------------
_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_EXTENT_TAG = re.compile(r"\(((?:E\.|W\.|S\.|N\.I\.)+)\)")
_VERBS = r"(inserted|substituted|repealed|omitted)"
_WHOLE = re.compile(r"^Ss?\.\s+(\d+[A-Z]*)(?:\s*(?:-|,|and)\s*(\d+[A-Z]*))*(?:\s+and cross-heading)?\s+" + _VERBS)
_VERB = re.compile(r"\b" + _VERBS + r"\b")
_AFFECTING = re.compile(r"\bby ([A-Z][A-Za-z0-9 ,'’&\-]*? (?:Act|Order|Regulations?|Measure) (\d{4})) \(c\. (\d+)\)")


def _d(m) -> date:
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


@dataclass
class Effect:
    cid: str
    raw: str
    kind: str                     # section_inserted | section_repealed | section_substituted | text_modified | other
    status: str                   # ok | prospective | extent_excluded | undated | ambiguous_date
    date: date | None
    sections: list[str]           # affected section eids (by anchor position)
    affecting_title: str | None = None
    affecting_year: int | None = None
    affecting_chapter: int | None = None
    affecting_sections: list[str] = field(default_factory=list)


def classify_kind(head: str) -> str:
    m = _WHOLE.match(head)
    if m:
        verb = _VERB.search(head).group(1)
        return {"inserted": "section_inserted", "repealed": "section_repealed", "omitted": "section_repealed",
                "substituted": "section_substituted"}[verb]
    if _VERB.search(head):
        return "text_modified"
    return "other"


def _enclosing_parens(text: str, pos: int) -> str | None:
    """Text inside the balanced parentheses that enclose ``pos`` (handles nested groups like '(6)')."""
    depth = 0
    start = None
    for i in range(pos - 1, -1, -1):
        ch = text[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start is None:
        return None
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:j]
    return None


def parse_effect_text(raw: str) -> tuple[str, str, date | None, str | None, int | None, int | None, list[str]]:
    """Return (kind, status, date, affecting title, year, chapter, affecting section labels)."""
    text = _WS.sub(" ", raw).strip()
    head = text.split(" by ", 1)[0]
    head_for_kind = _DATE.split(head)[0]
    # Parenthesised extent or date groups set off by a space are dropped; a group attached to the
    # section number (e.g. "S. 14(2)") marks a subdivision, so the effect is text_modified, not whole section.
    kind = classify_kind(re.sub(r"(?<!\S)\([^)]*\)", " ", head_for_kind).strip())
    am = _AFFECTING.search(text)
    title = year = chapter = None
    asecs: list[str] = []
    if am:
        title, year, chapter = am.group(1), int(am.group(2)), int(am.group(3))
        tail = text[am.end():].split(";", 1)[0]
        mm = re.match(r",\s*(?:ss?\.)\s*(.*)", tail)
        if mm:
            asecs = re.findall(r"(?<![\w(])(\d+[A-Z]*)(?=[\s(,)]|$)", re.split(r"\(with", mm.group(1))[0])
    # extent and prospective markers live before the first date group
    pre = text.split(" by ", 1)[0]
    if re.search(r"prosp", pre):
        return kind, "prospective", None, title, year, chapter, asecs
    ext = _EXTENT_TAG.search(pre)
    if ext and not (set(re.findall(r"[EW]\.", ext.group(1)))):
        return kind, "extent_excluded", None, title, year, chapter, asecs
    first = _DATE.search(pre)
    inside = _enclosing_parens(pre, first.start()) if first else None
    if not inside:
        return kind, "undated", None, title, year, chapter, asecs
    dates = list(_DATE.finditer(inside))
    if "otherwise" in inside or " for " in inside:
        # "d1 for S. and d2 otherwise": England & Wales takes the clause naming E./W., else "otherwise"
        pieces = re.split(r"\s+and\s+(?=\d)", inside)
        chosen = None
        for pc in pieces:
            dm = _DATE.search(pc)
            if not dm:
                return kind, "ambiguous_date", None, title, year, chapter, asecs
            if " for " in pc and re.search(r"\b[EW]\.", pc.split(" for ", 1)[1]):
                chosen = _d(dm)
            # An "otherwise" clause is NOT assumed to mean England and Wales: the meaning of the
            # qualifier (for example "S.") is not stated in the retrieved terms, so it stays ambiguous.
        if chosen is None:
            return kind, "ambiguous_date", None, title, year, chapter, asecs
        return kind, "ok", chosen, title, year, chapter, asecs
    if len(dates) == 1:
        return kind, "ok", _d(dates[0]), title, year, chapter, asecs
    return kind, "ambiguous_date", None, title, year, chapter, asecs


def parse_effects(root) -> list[Effect]:
    comm = {c.get("id"): " ".join("".join(c.itertext()).split())
            for c in root.iter(L + "Commentary") if c.get("Type") == "F"}
    anchors: dict[str, list[str]] = {}
    for e in root.iter():
        if not isinstance(e.tag, str):
            continue
        cid = e.get("CommentaryRef") or (e.get("Ref") if _tag(e) == "CommentaryRef" else None)
        if not cid or cid not in comm:
            continue
        p1 = next((a for a in e.iterancestors() if _tag(a) == "P1"), None)
        if p1 is not None and (p1.get("id") or "").startswith("section-"):
            anchors.setdefault(cid, [])
            if p1.get("id") not in anchors[cid]:
                anchors[cid].append(p1.get("id"))
    out: list[Effect] = []
    for cid, raw in comm.items():
        kind, status, d, t, y, ch, asecs = parse_effect_text(raw)
        out.append(Effect(cid, raw, kind, status, d, anchors.get(cid, []), t, y, ch, asecs))
    return out


def load(path: str | Path):
    return etree.parse(str(path)).getroot()
