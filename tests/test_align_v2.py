"""Tests for alignment v2 and its evaluator. SYNTHETIC data only; held out seeds are never used here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from taadeel import align_v2 as v2
from taadeel import validate
from taadeel.align import align as align_v1
from taadeel.eval_v2 import run as eval_run
from taadeel.heldout import ENGINE_FILES, SRC
from taadeel.model import Expression, Provision
from taadeel.synthetic import make_pair

ROOT = Path(__file__).resolve().parents[1]


def _expr(eid: str, items: list[tuple[int, str]]) -> Expression:
    e = Expression(work_id="synthetic/law/t", expression_id=eid, source_url="synthetic://t", retrieved_at="2026-10-16",
                   synthetic=True)
    e.provisions = [Provision(eid=f"art_{n}", kind="article", number=n, text=t) for n, t in items]
    return e


def test_evaluator_reproduces_validate_for_v1():
    kw = {"templated": True, "edit_frac": 0.4}
    a = validate.run(range(3), **kw)
    b = eval_run(range(3), lambda p: align_v1(p.a, p.b), **kw)
    assert a == b


def test_identical_versions_align_fully_with_high_confidence():
    p = make_pair(5)
    res = v2.align(p.a, p.a)
    assert not res.unaligned_a and not res.unaligned_b
    assert all(x.a_eid == x.b_eid and x.confidence == "high" for x in res.pairs)


def test_unrelated_article_is_not_forced():
    a = _expr("a", [(1, "alpha beta gamma delta"), (2, "the licence fee is due within thirty days"), (3, "omega psi chi phi")])
    b = _expr("b", [(1, "alpha beta gamma delta"), (2, "zz yy xx ww vv uu tt ss"), (3, "omega psi chi phi")])
    res = v2.align(a, b)
    assert "art_2" in res.unaligned_a and "art_2" in res.unaligned_b


def test_near_identical_text_matches_without_number_evidence():
    # number changed in a way no anchor explains; text alone (similarity >= 0.9) must still match
    a = _expr("a", [(1, "the authority shall publish the register of licences every year")])
    b = _expr("b", [(7, "the authority shall publish the register of licences every year.")])
    res = v2.align(a, b)
    assert [(x.a_eid, x.b_eid) for x in res.pairs] == [("art_1", "art_7")]


def test_empty_versions():
    e = _expr("a", [])
    f = _expr("b", [(1, "x y z")])
    assert v2.align(e, f).unaligned_b == ["art_1"]
    assert v2.align(f, e).unaligned_a == ["art_1"]


def test_v2_not_worse_than_v1_on_a_small_dev_slice():
    kw = {"templated": True, "n_insert": 8, "n_repeal": 8, "n_replace": 8}
    r1 = eval_run(range(3), lambda p: align_v1(p.a, p.b), **kw)
    r2 = eval_run(range(3), lambda p: v2.align(p.a, p.b), **kw)
    assert r2["alignment_accuracy"] >= r1["alignment_accuracy"]
    assert r2["per_class"]["repealed"]["recall"] >= r1["per_class"]["repealed"]["recall"]


def test_v1_engine_files_match_the_lock():
    lock = json.loads((ROOT / "results" / "heldout_synthetic.json").read_text(encoding="utf-8"))["engine_sha256"]
    now = {f: hashlib.sha256((SRC / f).read_bytes()).hexdigest() for f in ENGINE_FILES}
    assert now == lock
