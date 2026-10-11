"""Core data model (Akoma Ntoso-inspired, simplified). See docs/ARCHITECTURE.md."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .normalize import normalize


@dataclass
class Provision:
    eid: str                      # stable id, e.g. "art_5_bis1"
    kind: str                     # part | chapter | article | clause
    number: int | None = None
    bis: int = 0                  # 0 plain, 1 مكرر, n مكرر (n)
    parent: str | None = None
    text: str = ""                # original text, never altered
    text_norm: str = ""
    heading: str = ""

    def __post_init__(self) -> None:
        if not self.text_norm:
            self.text_norm = normalize(self.text)

    @property
    def key(self) -> tuple[int | None, int]:
        return (self.number, self.bis)


@dataclass
class Expression:
    work_id: str
    expression_id: str
    source_url: str
    retrieved_at: str             # ISO date/time of retrieval
    language: str = "ar"
    valid_from: date | None = None
    effective_status: str = "unknown"   # known | uncertain | unknown
    issue_date: date | None = None
    synthetic: bool = False
    provisions: list[Provision] = field(default_factory=list)

    def articles(self) -> list[Provision]:
        return [p for p in self.provisions if p.kind == "article"]


class SchemaError(ValueError):
    pass


def validate_expression(e: Expression) -> None:
    """Raise SchemaError on structural problems. Provenance is mandatory."""
    if not e.source_url:
        raise SchemaError(f"{e.expression_id}: missing source_url")
    if not e.retrieved_at:
        raise SchemaError(f"{e.expression_id}: missing retrieved_at")
    if e.effective_status not in {"known", "uncertain", "unknown"}:
        raise SchemaError(f"{e.expression_id}: bad effective_status {e.effective_status!r}")
    if e.effective_status == "known" and e.valid_from is None:
        raise SchemaError(f"{e.expression_id}: known status requires valid_from")
    seen: set[str] = set()
    keys: set[tuple[int | None, int]] = set()
    ids = {p.eid for p in e.provisions}
    for p in e.provisions:
        if p.eid in seen:
            raise SchemaError(f"{e.expression_id}: duplicate eid {p.eid}")
        seen.add(p.eid)
        if p.kind not in {"part", "chapter", "article", "clause"}:
            raise SchemaError(f"{p.eid}: bad kind {p.kind}")
        if p.parent is not None and p.parent not in ids:
            raise SchemaError(f"{p.eid}: unknown parent {p.parent}")
        if p.kind == "article":
            if p.number is None:
                raise SchemaError(f"{p.eid}: article without number")
            if p.key in keys:
                raise SchemaError(f"{e.expression_id}: duplicate article {p.key}")
            keys.add(p.key)
    if e.synthetic and not e.work_id.startswith("synthetic/"):
        raise SchemaError(f"{e.expression_id}: synthetic expressions must use a synthetic/ work_id")
    if not e.synthetic and e.work_id.startswith("synthetic/"):
        raise SchemaError(f"{e.expression_id}: synthetic/ work_id requires synthetic=True")
