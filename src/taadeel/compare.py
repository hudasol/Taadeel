"""Compare two plain text versions of a law supplied by the caller.

Input is text the caller already holds. Nothing is fetched. Articles are found by their headings:
Arabic (المادة 5, المادة (5) مكرر) through the project parser, English ("Article 5", "Section 5A",
"5. Title") through a small parser here. The engine files are used unchanged.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import date

from .align import align
from .diff import diff
from .labels import suffix_value
from .model import Expression, Provision
from .parse import parse_structure

MAX_CHARS = 2_000_000
MAX_ARTICLES = 800          # alignment is quadratic in the article count; this bounds the work per request
_EN_LABELLED = re.compile(r"^\s*(?:article|section)\s+(\d+)([A-Za-z]{0,3})\b\s*[.:\-–]?\s*(.*)$", re.I)
_EN_NUMBERED = re.compile(r"^\s*(\d+)([A-Za-z]{0,3})\s*[.)]\s+(\S.*)$")


class CompareError(ValueError):
    pass


def detect_language(text: str) -> str:
    arabic = sum("؀" <= ch <= "ۿ" for ch in text)
    latin = sum(ch.isascii() and ch.isalpha() for ch in text)
    return "ar" if arabic > latin else "en"


def _parse_english(raw: str, expr: Expression) -> Expression:
    cur: Provision | None = None
    body: list[str] = []
    out: list[Provision] = []
    seen: set[tuple[int, int]] = set()

    def flush() -> None:
        nonlocal cur, body
        if cur is not None:
            cur.text = "\n".join(body).strip()
            from .normalize import normalize
            cur.text_norm = normalize(cur.text)
            out.append(cur)
        cur, body = None, []

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _EN_LABELLED.match(s) or _EN_NUMBERED.match(s)
        if m:
            number, suffix = int(m.group(1)), m.group(2).upper()
            bis = suffix_value(suffix) if suffix else 0
            if (number, bis) not in seen:
                flush()
                seen.add((number, bis))
                eid = f"s_{number}{suffix}" if suffix else f"s_{number}"
                cur = Provision(eid=eid, kind="article", number=number, bis=bis, heading=m.group(3)[:120])
                body.append(m.group(3))
                continue
        if cur is not None:
            body.append(s)
    flush()
    expr.provisions = out
    return expr


def build(raw: str, name: str, lang: str | None = None) -> Expression:
    if len(raw) > MAX_CHARS:
        raise CompareError(f"{name}: text is longer than {MAX_CHARS} characters")
    lang = lang or detect_language(raw)
    e = Expression(work_id="user/input", expression_id=name, source_url="user-supplied", retrieved_at=date.today().isoformat(),
                   language=lang, effective_status="unknown", synthetic=False)
    e = parse_structure(raw, e) if lang == "ar" else _parse_english(raw, e)
    if not e.articles():
        raise CompareError(f"{name}: no article headings were found "
                           f"(expected 'المادة 1' or 'Article 1' / 'Section 1' / '1. Title')")
    if len(e.articles()) > MAX_ARTICLES:
        raise CompareError(f"{name}: {len(e.articles())} articles found, the limit is {MAX_ARTICLES}")
    return e


def compare_texts(old: str, new: str, lang: str | None = None) -> dict:
    a, b = build(old, "old", lang), build(new, "new", lang)
    res = align(a, b)
    ta, tb = {p.eid: p.text for p in a.articles()}, {p.eid: p.text for p in b.articles()}
    changes = []
    for c in diff(a, b, res):
        d = asdict(c)
        d["a_text"], d["b_text"] = ta.get(c.a_eid or ""), tb.get(c.b_eid or "")
        changes.append(d)
    counts: dict[str, int] = {}
    for c in changes:
        counts[c["kind"]] = counts.get(c["kind"], 0) + 1
    return {"language": a.language, "articles_old": len(ta), "articles_new": len(tb),
            "aligned": len(res.pairs), "low_confidence": sum(p.confidence == "low" for p in res.pairs),
            "counts": counts, "changes": changes}
