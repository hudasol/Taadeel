"""Arabic amendment by reference pattern lexicon.

Status: unvalidated on real UAE text. Every pattern below is taken from phrasing
recorded in research/arabic_sources.md (Egyptian, Libyan and Tunisian examples), and
no UAE statute has been used to test them. English patterns (amend_en) are validated
separately against recorded effects; nothing here is.

Input is passed through ``normalize()`` before matching, so templates are written in
normalized form (alef folded, alef maqsura folded to yaa, no diacritics, ASCII digits).
``Amendment.span`` and ``new_text`` therefore refer to the normalized string.
``new_text`` runs from the introducing marker to the next detected instruction or the
end of the input; callers should pass one amending clause or section at a time.

Phrasings in the sources that are deliberately NOT implemented (see the notes at the
bottom): anything not listed in the sources, such as ``يستعاض عن`` and ``يلغى نص المادة``,
is absent on purpose.
"""
from __future__ import annotations

import re

from .amend_common import Amendment
from .normalize import _ORDINALS, normalize

_ORD = "|".join(sorted(_ORDINALS, key=len, reverse=True))
_COLON = r"\s*:?"

# makarrar (bis) suffix. Source: arabic_sources.md Part 2, "add / insert" variants:
# مكرر / مكررا / مكررة, "مكرر 1", "مكرر (1)", "مكرر ثانيا", "مكررا ثانيا".
_BIS = (r"(?:\s*(?P<bis>مكرر)[ةا]?"
        r"(?:\s*\(\s*(?P<bn1>\d+)\s*\)|\s+(?P<bn2>\d+)(?!\d)|\s+(?P<bo>" + _ORD + r")(?!\w))?)?")
_NUM = r"\(?\s*(?P<num>\d+)\s*\)?"
_STEM_FEM_OR_MASC = r"(?<!\w)"


def _bis_value(m: re.Match) -> int:
    if not m.group("bis"):
        return 0
    if m.group("bn1") or m.group("bn2"):
        return int(m.group("bn1") or m.group("bn2"))
    if m.group("bo"):
        return _ORDINALS[m.group("bo")]
    return 1


# Each entry: (pattern_id, regex, op, base confidence, has_new_text_marker)
_PATTERNS: list[tuple[str, re.Pattern, str, float]] = []


def _add(pid: str, rx: str, op: str, conf: float) -> None:
    _PATTERNS.append((pid, re.compile(rx), op, conf))


# ar.replace.article
# Source: Egyptian Constitutional Declaration amendment (raw text), template
# "يستبدل بنص {article} من {instrument} النص الاتي". Variants used: ي/ت prefix, with or
# without ب before نص, النص الاتي / النص التالي. Excerpt: "يستبدل بنص المادة 38 من الاعلان ... النص الاتي".
_add("ar.replace.article",
     _STEM_FEM_OR_MASC + r"[يت]ستبدل\s+ب?نص\s+(?P<unit>المادة|الفصل)\s*" + _NUM + _BIS
     + r"\s+من\s+(?P<inst>[^:]{1,200}?)\s+النص\s+(?:الاتي|التالي)" + _COLON,
     "substitute", 0.9)

# ar.replace.paragraph
# Source: Egyptian presidential decision snippet (search result, wording partly seen):
# "يستبدل بنص المادة (25) فقرة (2) من الاعلان الدستوري ... النص الاتي".
_add("ar.replace.paragraph",
     _STEM_FEM_OR_MASC + r"[يت]ستبدل\s+ب?نص\s+(?P<unit>المادة|الفصل)\s*" + _NUM + _BIS
     + r"\s+فقرة\s*\(?\s*(?P<para>\d+)\s*\)?\s+من\s+(?P<inst>[^:]{1,200}?)\s+النص\s+(?:الاتي|التالي)" + _COLON,
     "substitute", 0.8)

# ar.amend.reword
# Note: normalize() folds alef maqsura, so على is matched as علي.
# Source: same Egyptian text, section "التعديل الاول": "يعدل نص المادة (38) من الاعلان ... ليصبح",
# with template tail "ليصبح على النحو الاتي". The verb يعدل is treated as the same effect as يستبدل.
_add("ar.amend.reword",
     _STEM_FEM_OR_MASC + r"[يت]عدل\s+نص\s+(?P<unit>المادة|الفصل)\s*" + _NUM + _BIS
     + r"\s+من\s+(?P<inst>[^:]{1,200}?)\s+ليصبح(?:\s+علي\s+النحو)?(?:\s+(?:الاتي|التالي))?" + _COLON,
     "substitute", 0.85)

# ar.insert.article
# Source: Egyptian text "تضاف مادة جديدة رقم 39 مكرر للاعلان الدستوري ..." and the template

# The instrument and the "نصها الاتي" marker are optional in the match; new_text is only set when present.
_add("ar.insert.article",
     _STEM_FEM_OR_MASC + r"[يت]ضاف\s+مادة\s+جديدة\s+(?:برقم|رقم)\s*" + _NUM + _BIS
     + r"(?:\s+(?P<inst>[^:]{1,200}?)\s+نصها\s+(?:الاتي|التالي)" + _COLON + r")?",
     "insert", 0.9)

# ar.repeal.list
# Source: Egyptian law 354/1954 snippet ("تلغي المواد"), "تلغى المواد 348 و 349 و 350",
# Tunisian "تلغى احكام الفصول 2 و3 و21 ..." (WebFetch summary only, lower confidence for الفصل).
# Template: "تلغى احكام {unit} {n} و{n}". The optional leading و follows "ويلغى" seen for Libyan law.
_ITEM = r"\(?\s*\d+\s*\)?" + r"(?:\s*مكرر[ةا]?(?:\s*\(\s*\d+\s*\)|\s+\d+(?!\d)|\s+(?:" + _ORD + r")(?!\w))?)?"
_add("ar.repeal.list",
     r"(?<!\w)و?[يت]لغي\s+(?:احكام\s+)?(?P<unit>المواد|المادة|الفصول|الفصل)\s+(?P<list>"
     + _ITEM + r"(?:(?:\s*,\s*(?:و\s*)?|\s*و\s*)" + _ITEM + r")*)",
     "repeal", 0.75)

_LIST_ITEM = re.compile(
    r"(?P<num>\d+)(?:\s*\)?\s*(?P<bis>مكرر)[ةا]?"
    r"(?:\s*\(\s*(?P<bn1>\d+)\s*\)|\s+(?P<bn2>\d+)(?!\d)|\s+(?P<bo>" + _ORD + r")(?!\w))?)?")

# General repeal clause, not an amendment of a named target (hazard 8 in the sources).
# Source: Libyan law 6/2003 "يلغى كل حكم يخالف احكام هذا القانون"; "كل نص يخالف" listed as a variant.
# "يتعارض" is marked UNVERIFIED in the sources, so it is not included.
_GENERAL_REPEAL = re.compile(r"(?<!\w)و?[يت]لغي\s+كل\s+(?:حكم|نص)\s+يخالف")


def has_general_repeal(text: str) -> bool:
    """True if the text holds a general repeal clause (not a named-target amendment)."""
    return bool(_GENERAL_REPEAL.search(normalize(text)))


def _from_match(pid: str, m: re.Match, op: str, conf: float, t: str) -> list[Amendment]:
    unit = m.groupdict().get("unit")
    if unit and unit.startswith("الفص"):
        conf = round(conf - 0.15, 2)  # Tunisian usage rests on a summary only
    span = (m.start(), m.end())
    if pid == "ar.repeal.list":
        out = []
        for it in _LIST_ITEM.finditer(m.group("list")):
            out.append(Amendment("repeal", it.group("num"), _bis_value(it), None, span, pid, conf))
        return out
    has_text = pid != "ar.insert.article" or bool(m.group("inst"))
    para = m.groupdict().get("para")
    # new_text is filled in by parse() once the next match boundary is known
    return [Amendment(op, m.group("num"), _bis_value(m), "" if has_text else None, span, pid, conf,
                      paragraph=para)]


def parse(text: str) -> list[Amendment]:
    """Parse Arabic amendment sentences in ``text`` into Amendment records."""
    t = normalize(text)
    found: list[tuple[int, int, str, re.Match, str, float]] = []
    for pid, rx, op, conf in _PATTERNS:
        for m in rx.finditer(t):
            found.append((m.start(), m.end(), pid, m, op, conf))
    found.sort(key=lambda f: (f[0], -(f[1] - f[0])))
    kept = []
    last_end = -1
    for f in found:  # drop matches overlapping an earlier (longer, same start) match
        if f[0] >= last_end:
            kept.append(f)
            last_end = f[1]
    out: list[Amendment] = []
    for i, (s, e, pid, m, op, conf) in enumerate(kept):
        nxt = kept[i + 1][0] if i + 1 < len(kept) else len(t)
        recs = _from_match(pid, m, op, conf, t)
        for r in recs:
            if r.new_text is not None:
                body = t[e:nxt].strip().lstrip(":").strip()
                r = Amendment(**{**r.__dict__, "new_text": body or None})
            out.append(r)
    return out


# Not implemented, because the sources give no usable phrasing or only unverified text:
#  - يستعاض عن and يلغى نص المادة (not retrieved; the sources list يستعاض عن as "not retrieved").
#  - "يضاف الى {instrument} مادة جديدة برقم ..." (only the paragraph form "فقرة ثالثة للمادة 30" is seen).
#  - Ordinal-word article numbers (Libyan "المادة التاسعة عشرة") and "مكررة مرتين".
#  - Word-level swaps (تعوض عبارة X بعبارة Y) and "بحيث تكون على النحو التالي" rewrites.
#  - Effective dates ("بعد {n} يوما") are UNVERIFIED and belong to temporal.py anyway.
