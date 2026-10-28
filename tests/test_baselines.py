import json
from pathlib import Path

from taadeel import baselines as B
from taadeel import validate
from taadeel.synthetic import make_pair

RESULTS = Path(__file__).resolve().parents[1] / "results" / "baselines.json"


def test_engine_v1_through_the_baseline_harness_equals_the_project_harness():
    mine = B.evaluate_synthetic(B.ALIGNERS["engine_v1"], range(6), templated=True)
    theirs = validate.run(range(6), templated=True)
    assert abs(mine["alignment_accuracy"] - theirs["alignment_accuracy"]) < 1e-4
    for k in B.KINDS:
        p = theirs["per_class"][k]["precision"]
        assert (mine["classes"][k]["precision"] is None) == (p is None)
        if p is not None:
            assert abs(mine["classes"][k]["precision"] - p) < 1e-3


def test_by_number_is_exact_without_renumbering_and_fails_with_it():
    p = make_pair(3, n_insert=0, bis_inserts=0, n_repeal=0)
    assert B.by_number(p.a, p.b).unaligned_a == []
    q = make_pair(3, n_insert=4, bis_inserts=0)      # plain inserts shift later numbers
    got = {x.a_eid: x.b_eid for x in B.by_number(q.a, q.b).pairs}
    wrong = sum(got.get(a) != b for a, b in q.gold_pairs.items())
    assert wrong > 0
    eng = {x.a_eid: x.b_eid for x in B.ALIGNERS["engine_v1"](q.a, q.b).pairs}
    assert sum(eng.get(a) != b for a, b in q.gold_pairs.items()) < wrong


def test_greedy_text_is_one_to_one():
    p = make_pair(5)
    res = B.greedy_text(p.a, p.b)
    assert len({x.a_eid for x in res.pairs}) == len(res.pairs) == len({x.b_eid for x in res.pairs})


def test_result_file_is_consistent_with_the_locked_held_out_run():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    held = json.loads((RESULTS.parent / "heldout_synthetic.json").read_text(encoding="utf-8"))
    for name, row in held["results"].items():
        assert abs(r["synthetic"]["engine_v1"][name]["alignment_accuracy"] - round(row["alignment_accuracy"], 4)) < 1e-4
    uk = json.loads((RESULTS.parent / "uk_validation.json").read_text(encoding="utf-8"))["aggregate"]
    assert r["uk"]["engine_v1"]["one_day"]["correct"] == uk["alignment_one_day"]["correct"]
    assert r["uk"]["engine_v1"]["renumbering_variant"]["correct"] == uk["renumbering_variant"]["correct"]
    assert r["point_in_time"]["effect_dates.prior_day"]["correct"] == uk["point_in_time"]["prior_day_correct"]


def test_baselines_document_matches_the_generator():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert B.DOC.read_text(encoding="utf-8") == B.markdown(r)
