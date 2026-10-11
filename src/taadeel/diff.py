"""Article- and word-level diffs with change classification.

Classes: inserted, replaced, repealed, renumbered, clarified.
``clarified`` is deliberately narrow: the normalized text is identical, so
only orthography/diacritics/digit-script/punctuation differ. Any change to
words or numerals is ``replaced``. A matched pair that also changed number is
``renumbered`` when the text is otherwise identical, else ``replaced`` with
``renumbered=True``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .align import AlignmentResult
from .model import Expression


@dataclass
class WordOp:
    op: str          # equal | replace | delete | insert
    a: str
    b: str


@dataclass
class Change:
    kind: str                       # inserted | replaced | repealed | renumbered | clarified
    a_eid: str | None
    b_eid: str | None
    renumbered: bool = False
    confidence: str = "high"
    score: float | None = None
    amending_work_id: str | None = None
    words: list[WordOp] = field(default_factory=list)


def word_diff(a: str, b: str) -> list[WordOp]:
    ta, tb = a.split(), b.split()
    ops: list[WordOp] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        ops.append(WordOp(tag, " ".join(ta[i1:i2]), " ".join(tb[j1:j2])))
    return ops


def diff(a: Expression, b: Expression, res: AlignmentResult, amending_work_id: str | None = None) -> list[Change]:
    ap = {p.eid: p for p in a.articles()}
    bp = {p.eid: p for p in b.articles()}
    changes: list[Change] = []
    for pr in res.pairs:
        pa, pb = ap[pr.a_eid], bp[pr.b_eid]
        same_no = pa.key == pb.key
        if pa.text == pb.text and same_no:
            continue  # unchanged
        norm_same = pa.text_norm == pb.text_norm
        if norm_same and same_no:
            kind, ren = "clarified", False
        elif norm_same:
            kind, ren = "renumbered", True
        else:
            kind, ren = "replaced", not same_no
        changes.append(Change(kind, pa.eid, pb.eid, ren, pr.confidence, pr.score, amending_work_id,
                              word_diff(pa.text, pb.text) if kind != "renumbered" else []))
    for eid in res.unaligned_a:
        changes.append(Change("repealed", eid, None, amending_work_id=amending_work_id))
    for eid in res.unaligned_b:
        changes.append(Change("inserted", None, eid, amending_work_id=amending_work_id))
    return changes
