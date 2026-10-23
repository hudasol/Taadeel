"""Snapshot timeline served through the API: certain, uncertain with candidates, not in force."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from taadeel import timeline_service as ts
from taadeel.api import DISCLAIMER, app
from taadeel.model import Expression, Provision
from taadeel.timeline_v2 import Step

ROOT = Path(__file__).resolve().parents[1]
c = TestClient(app)


def _v(d: date, texts: dict[str, str]) -> Expression:
    e = Expression(work_id="synthetic/law/tl", expression_id=f"synthetic/law/tl@{d}", source_url="synthetic://tl",
                   retrieved_at=f"{d}T00:00:00", valid_from=d, effective_status="known", synthetic=True)
    e.provisions = [Provision(eid=k, kind="article", number=i + 1, text=t) for i, (k, t) in enumerate(texts.items())]
    return e


@pytest.fixture
def synthetic_timeline(monkeypatch):
    v0 = _v(date(2020, 1, 1), {"s1": "alpha", "s2": "beta"})
    v1 = _v(date(2021, 1, 1), {"s1": "alpha changed", "s2": "beta changed"})
    # s1 is named by a recorded effect of 2021-01-01; s2 changed with no recorded effect
    step = Step(date(2021, 1, 1), explained=[("replaced", "s1", "s1")], unexplained=[("replaced", "s2", "s2")], conflicts=[])
    monkeypatch.setattr(ts, "_load", lambda: {"synthetic/law/tl": ([v0, v1], [step])})


def test_uncertain_between_versions_lists_both_candidates(synthetic_timeline):
    r = ts.query("synthetic/law/tl", date(2020, 6, 1))
    assert r["certainty"] == "uncertain" and len(r["candidates"]) == 2
    first, second = ({a["eid"]: a for a in c["articles"]} for c in r["candidates"])
    assert first["s2"]["text"] == "beta" and second["s2"]["text"] == "beta changed"
    assert second["s1"]["text"] == "alpha"                      # explained change is not pulled forward
    assert second["s2"]["retrieved_at"].startswith("2021-01-01")  # provenance of the later snapshot
    assert second["s1"]["retrieved_at"].startswith("2020-01-01")
    assert r["evidence"]["unexplained_changes"][0]["after"] == "s2"


def test_certain_on_and_after_version_date(synthetic_timeline):
    r = ts.query("synthetic/law/tl", date(2021, 3, 1))
    assert r["certainty"] == "certain" and len(r["candidates"]) == 1
    assert r["evidence"]["version_basis"] == "recorded effect dated 2021-01-01"


def test_not_in_force_before_first_snapshot(synthetic_timeline):
    r = ts.query("synthetic/law/tl", date(2019, 1, 1))
    assert r["certainty"] == "not_in_force" and r["candidates"] == []


STEPS_PRESENT = ts.STEPS.exists()


def _uncertain_uk_query() -> tuple[str, str]:
    res = json.loads((ROOT / "results" / "uk_timeline_v2.json").read_text(encoding="utf-8"))
    for a in res["acts"]:
        for row in a["rows"]:
            if row["new"] == "uncertain" and row["truth_candidate_index"] is not None and "not explained" in row["note"]:
                return f"uk/{a['act']}", row["query"]
    raise AssertionError("no uncertain row in the result file")


@pytest.mark.skipif(not STEPS_PRESENT, reason="data/uk/timeline_steps.json.gz not built")
def test_api_uncertain_uk_date_matches_the_measured_result():
    work, day = _uncertain_uk_query()
    j = c.get(f"/api/timeline?work={work}&date={day}").json()
    assert j["disclaimer"] == DISCLAIMER and j["synthetic"] is False and j["corpus"] == "uk-validation"
    assert "Open Government Licence" in j["attribution"]
    assert j["certainty"] == "uncertain" and len(j["candidates"]) == 2
    assert all(a["source_url"].startswith("https://www.legislation.gov.uk/") and a["retrieved_at"]
               for cand in j["candidates"] for a in cand["articles"])


@pytest.mark.skipif(not STEPS_PRESENT, reason="data/uk/timeline_steps.json.gz not built")
def test_api_lists_works_and_rejects_unknown_work():
    j = c.get("/api/timeline/works").json()
    assert j["works"] and all(w.startswith("uk/") for w in j["works"])
    assert c.get("/api/timeline?work=synthetic/law/1&date=2021-01-01").status_code == 404


@pytest.mark.skipif(not STEPS_PRESENT, reason="data/uk/timeline_steps.json.gz not built")
def test_service_reproduces_every_measured_state():
    res = json.loads((ROOT / "results" / "uk_timeline_v2.json").read_text(encoding="utf-8"))
    rows = [(f"uk/{a['act']}", r) for a in res["acts"] for r in a["rows"]]
    assert rows and all(ts.query(w, date.fromisoformat(r["query"]))["certainty"] == r["new"] for w, r in rows)
    ex = ts.example()
    assert ts.query(ex["work"], date.fromisoformat(ex["date"]))["certainty"] == "uncertain"
