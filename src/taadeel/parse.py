"""Structure extraction from plain Arabic legislative text.

Recognises part (الباب), chapter (الفصل), article (المادة) and numbered
clauses. HTML/PDF extraction to plain text happens upstream; this module is
deterministic and works on the text.
"""
from __future__ import annotations

import re

from .model import Expression, Provision
from .normalize import normalize, parse_article_label

_PART = re.compile(r"^(الباب)\b")
_CHAPTER = re.compile(r"^(الفصل)\b")
_CLAUSE = re.compile(r"^\s*(\d+)\s*[-\.\)]\s*(.*)$")


def _eid(number: int, bis: int) -> str:
    return f"art_{number}" if bis == 0 else f"art_{number}_bis{bis}"


def parse_structure(raw: str, expr: Expression) -> Expression:
    """Fill ``expr.provisions`` from ``raw`` and return ``expr``."""
    provisions: list[Provision] = []
    part_id: str | None = None
    chapter_id: str | None = None
    current: Provision | None = None
    body: list[str] = []
    counters = {"part": 0, "chapter": 0}

    def flush() -> None:
        nonlocal current, body
        if current is None:
            return
        current.text = "\n".join(body).strip()
        current.text_norm = normalize(current.text)
        clause_no = 0
        for line in body:
            m = _CLAUSE.match(normalize(line))
            if m:
                clause_no += 1
                provisions.append(
                    Provision(
                        eid=f"{current.eid}_cl{clause_no}",
                        kind="clause",
                        number=int(m.group(1)),
                        parent=current.eid,
                        text=line.strip(),
                    )
                )
        current, body = None, []

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        n = normalize(s)
        label = parse_article_label(s)
        if label is not None:
            flush()
            number, bis = label
            parent = chapter_id or part_id
            current = Provision(eid=_eid(number, bis), kind="article", number=number, bis=bis, parent=parent, heading=s)
            provisions.append(current)
            continue
        if _PART.match(n):
            flush()
            counters["part"] += 1
            part_id, chapter_id = f"part_{counters['part']}", None
            provisions.append(Provision(eid=part_id, kind="part", heading=s, text=s))
            continue
        if _CHAPTER.match(n):
            flush()
            counters["chapter"] += 1
            chapter_id = f"chapter_{counters['chapter']}"
            provisions.append(Provision(eid=chapter_id, kind="chapter", parent=part_id, heading=s, text=s))
            continue
        if current is not None:
            body.append(s)
    flush()
    expr.provisions = provisions
    return expr
