from datetime import date

import pytest

from taadeel.align import align
from taadeel.diff import diff
from taadeel.model import Expression, SchemaError, validate_expression
from taadeel.parse import parse_structure
from taadeel.synthetic import SYNTHETIC_URL, make_pair
from taadeel.temporal import Version, as_of

RAW = """\
الباب الأول
الفصل الأول
المادة (1)
يسري هذا القانون على الجميع.
1- البند الأول
2- البند الثاني
المادة (1) مكرر
نص إضافي.
المادة ٢
نص المادة الثانية.
"""


def _expr(**kw):
    base = dict(work_id="synthetic/x/1", expression_id="e", source_url=SYNTHETIC_URL,
                retrieved_at="2026-10-11", synthetic=True)
    base.update(kw)
    return Expression(**base)


def test_parse_structure_and_bis():
    e = parse_structure(RAW, _expr())
    validate_expression(e)
    arts = [(p.number, p.bis) for p in e.articles()]
    assert arts == [(1, 0), (1, 1), (2, 0)]
    assert [p.kind for p in e.provisions if p.kind != "article"][:2] == ["part", "chapter"]
    clauses = [p for p in e.provisions if p.kind == "clause"]
    assert len(clauses) == 2 and clauses[0].parent == "art_1"
    assert e.articles()[0].parent == "chapter_1"


def test_schema_requires_provenance_and_synthetic_labelling():
    with pytest.raises(SchemaError):
        validate_expression(_expr(source_url=""))
    with pytest.raises(SchemaError):
        validate_expression(_expr(retrieved_at=""))
    with pytest.raises(SchemaError):
        validate_expression(_expr(synthetic=False))          # synthetic/ id but flag false
    with pytest.raises(SchemaError):
        validate_expression(_expr(work_id="ae/fdl/2021/33"))  # flag true but real-looking id
    with pytest.raises(SchemaError):
        validate_expression(_expr(effective_status="known"))  # known needs valid_from


@pytest.mark.parametrize("seed", range(10))
def test_alignment_on_synthetic(seed):
    p = make_pair(seed)
    for e in (p.a, p.b):
        validate_expression(e)
    res = align(p.a, p.b)
    got = {x.a_eid: x.b_eid for x in res.pairs}
    correct = sum(1 for k, v in p.gold_pairs.items() if got.get(k) == v)
    assert correct / len(p.gold_pairs) >= 0.90
    # no forced matches for repealed articles
    repealed = {g.a_eid for g in p.gold_changes if g.kind == "repealed"}
    assert not (repealed & set(got))


@pytest.mark.parametrize("seed", range(10))
def test_diff_classification_on_synthetic(seed):
    p = make_pair(seed)
    changes = diff(p.a, p.b, align(p.a, p.b), amending_work_id="synthetic/amend/1")
    got = {(c.kind, c.a_eid, c.b_eid) for c in changes}
    gold = {(g.kind, g.a_eid, g.b_eid) for g in p.gold_changes}
    assert len(got & gold) / len(gold) >= 0.85
    assert all(c.amending_work_id == "synthetic/amend/1" for c in changes)


def test_orthography_only_is_clarified_not_replaced():
    a = _expr(expression_id="a")
    b = _expr(expression_id="b")
    parse_structure("المادة (1)\nيلتزم الموظف بالإخطار خلال ٣٠ يوما.", a)
    parse_structure("المادة (1)\nيَلْتَزِمُ الموظف بالإخطار خلال 30 يوما.", b)
    ch = diff(a, b, align(a, b))
    assert [c.kind for c in ch] == ["clarified"]


def test_number_change_is_replaced_not_clarified():
    a, b = _expr(expression_id="a"), _expr(expression_id="b")
    parse_structure("المادة (1)\nيلتزم الموظف بالإخطار خلال 30 يوما من تاريخ الطلب.", a)
    parse_structure("المادة (1)\nيلتزم الموظف بالإخطار خلال 60 يوما من تاريخ الطلب.", b)
    ch = diff(a, b, align(a, b))
    assert [c.kind for c in ch] == ["replaced"]
    assert any(w.op == "replace" and w.a == "30" and w.b == "60" for w in ch[0].words)


def test_pure_renumbering_detected():
    a, b = _expr(expression_id="a"), _expr(expression_id="b")
    t = "تلتزم المنشأة بتجديد الترخيص قبل نهاية المدة المحددة في هذا القانون."
    parse_structure(f"المادة (5)\n{t}", a)
    parse_structure(f"المادة (6)\n{t}", b)
    ch = diff(a, b, align(a, b))
    assert [c.kind for c in ch] == ["renumbered"]


def test_dissimilar_articles_stay_unaligned():
    a, b = _expr(expression_id="a"), _expr(expression_id="b")
    parse_structure("المادة (1)\nتلتزم المنشأة بتجديد الترخيص قبل نهاية المدة المحددة.", a)
    parse_structure("المادة (1)\nيحظر على أي شخص حيازة المواد الخطرة دون موافقة مسبقة من الجهة.", b)
    res = align(a, b)
    assert res.pairs == [] and res.unaligned_a == ["art_1"] and res.unaligned_b == ["art_1"]


V = [
    Version("base", date(2020, 1, 1), "known", date(2019, 12, 1)),
    Version("am1", date(2023, 6, 1), "known", date(2023, 5, 1)),
    Version("am2", None, "uncertain", date(2024, 3, 1)),
]


def test_temporal_certain():
    r = as_of(V, date(2021, 1, 1))
    assert (r.version_id, r.certainty) == ("base", "certain")
    r = as_of(V, date(2023, 7, 1))
    assert (r.version_id, r.certainty) == ("am1", "certain")


def test_temporal_not_in_force_before_base():
    assert as_of(V, date(2019, 1, 1)).certainty == "not_in_force"


def test_temporal_uncertain_after_undated_amendment_issue():
    r = as_of(V, date(2024, 6, 1))
    assert r.version_id == "am1" and r.certainty == "uncertain" and r.candidates == ["am2"]
    # before the undated amendment was even issued it cannot apply
    assert as_of(V, date(2024, 2, 1)).certainty == "certain"
