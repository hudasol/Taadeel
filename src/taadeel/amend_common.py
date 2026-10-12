"""Shared record type for the amendment by reference parsers (amend_ar, amend_en)."""
from __future__ import annotations

from dataclasses import dataclass

OPS = ("substitute", "repeal", "insert")


@dataclass(frozen=True)
class Amendment:
    """One parsed amendment instruction.

    op: substitute | repeal | insert.
    target: article or section number as a string (digits plus any letter suffix,
        for example "38" or "3ZA"). For an English insertion this is the new number
        when the inserted text states one, otherwise the anchor section.
    bis: Arabic "makarrar" index (0 none, 1 plain makarrar, n for makarrar n or an
        ordinal word); always 0 for English.
    new_text: replacement or inserted text when the sentence introduces it, else None.
    span: (start, end) offsets of the matched instruction. For Arabic these index the
        normalize()d string, not the raw input; for English they index the raw input.
    pattern_id: stable id of the pattern that matched.
    confidence: heuristic 0..1 from how well the pattern is attested; not a probability.
    paragraph: paragraph number when the instruction targets a paragraph only.
    anchor: English "After section N insert" anchor section.
    lang: "ar" or "en".
    """

    op: str
    target: str
    bis: int
    new_text: str | None
    span: tuple[int, int]
    pattern_id: str
    confidence: float
    paragraph: str | None = None
    anchor: str | None = None
    lang: str = "ar"

    def __post_init__(self) -> None:
        if self.op not in OPS:
            raise ValueError(f"bad op {self.op!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence out of range")
