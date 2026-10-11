"""Synthetic, clearly labeled test laws with known ground truth.

Text is randomly composed from a word pool: it is NOT real legislation and
carries no legal meaning. Every Expression produced here has
``synthetic=True`` and a ``synthetic/`` work_id, enforced by validate_expression,
so it can never appear in real-data views. The generator applies a known
sequence of operations and returns the gold labels, so alignment and diff
classification can be scored exactly. These numbers measure engine
correctness on synthetic text only, not real-world accuracy.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from .model import Expression, Provision
from .normalize import normalize

SYNTHETIC_URL = "synthetic://taadeel/test-fixture"

_POOL = (
    "الجهة المختصة الترخيص الطلب المدة الغرامة الإخطار السجل الموظف المنشأة العقد "
    "التقرير الحساب الاجتماع القرار اللائحة النموذج الرسوم الفحص الشهادة المراجعة "
    "الإجراء الاعتراض الاستئناف التسجيل التجديد الإلغاء الموافقة الضمان المخالفة "
    "يلتزم يجوز يصدر يقدم يحدد يتم تنظر تلتزم يعتمد تحتفظ يخطر يودع يسدد "
    "خلال ثلاثين يوما من تاريخ وفقا لأحكام هذا وفي حال عدم وبعد وذلك على أن "
    "ما لم كل كما أو إلى عن بموجب لدى نهاية بداية السنة الشهر الأسبوع"
).split()


def _sentence(rng: random.Random, lo: int = 14, hi: int = 26) -> str:
    return " ".join(rng.choice(_POOL) for _ in range(rng.randint(lo, hi))) + "."


@dataclass
class GoldChange:
    kind: str                      # inserted | replaced | repealed | renumbered | clarified
    a_eid: str | None
    b_eid: str | None


@dataclass
class SyntheticPair:
    a: Expression
    b: Expression
    gold_pairs: dict[str, str]     # a_eid -> b_eid for every surviving article
    gold_changes: list[GoldChange] = field(default_factory=list)


def _expr(eid: str, items: list[tuple[int, int, str]], valid_from: date) -> Expression:
    e = Expression(
        work_id="synthetic/law/1", expression_id=eid, source_url=SYNTHETIC_URL,
        retrieved_at="2026-10-11", valid_from=valid_from, effective_status="known",
        issue_date=valid_from, synthetic=True,
    )
    for number, bis, text in items:
        e.provisions.append(Provision(
            eid=f"art_{number}" if bis == 0 else f"art_{number}_bis{bis}",
            kind="article", number=number, bis=bis, text=text,
        ))
    return e


def make_pair(seed: int, n: int = 40, n_replace: int = 5, n_repeal: int = 3, n_insert: int = 3,
              n_clarify: int = 2, bis_inserts: int = 1) -> SyntheticPair:
    """Build version A, apply operations, return version B and gold labels.

    Inserted plain articles shift later numbers (renumbering); ``bis_inserts``
    of the insertions are «مكرر» articles that do not shift numbering.
    """
    rng = random.Random(seed)
    base = [(i, 0, _sentence(rng)) for i in range(1, n + 1)]
    a = _expr("a", base, date(2020, 1, 1))

    idx = list(range(n))
    rng.shuffle(idx)
    replace_idx = set(idx[:n_replace])
    repeal_idx = set(idx[n_replace : n_replace + n_repeal])
    clarify_idx = set(idx[n_replace + n_repeal : n_replace + n_repeal + n_clarify])
    plain_inserts = sorted(rng.sample(range(n), n_insert - bis_inserts))
    bis_after = rng.sample([i for i in range(n) if i not in repeal_idx], bis_inserts)

    b_items: list[tuple[int, int, str]] = []
    gold_pairs: dict[str, str] = {}
    gold: list[GoldChange] = []
    shift = 0
    for i, (num, _, text) in enumerate(base):
        if i in plain_inserts:
            shift += 1
            new_no = num + shift - 1
            b_items.append((new_no, 0, _sentence(rng)))
            gold.append(GoldChange("inserted", None, f"art_{new_no}"))
        if i in repeal_idx:
            gold.append(GoldChange("repealed", f"art_{num}", None))
            continue
        new_text = text
        kind = None
        if i in replace_idx:
            words = text.rstrip(".").split()
            k = rng.randrange(len(words))
            words[k : k + 3] = [rng.choice(_POOL) for _ in range(rng.randint(2, 4))]
            new_text, kind = " ".join(words) + ".", "replaced"
        elif i in clarify_idx:
            # orthographic-only change: add diacritics to the first word
            first, _, rest = text.partition(" ")
            new_text, kind = first + "َ " + rest, "clarified"
        new_no = num + shift
        if shift and kind in (None, "clarified"):
            kind = "renumbered"   # same normalized text, new number
        b_items.append((new_no, 0, new_text))
        gold_pairs[f"art_{num}"] = f"art_{new_no}"
        if kind:
            gold.append(GoldChange(kind, f"art_{num}", f"art_{new_no}"))
        if i in bis_after:
            b_items.append((new_no, 1, _sentence(rng)))
            gold.append(GoldChange("inserted", None, f"art_{new_no}_bis1"))
    b = _expr("b", b_items, date(2024, 1, 1))
    return SyntheticPair(a, b, gold_pairs, gold)
