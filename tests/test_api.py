from fastapi.testclient import TestClient

from taadeel.api import DISCLAIMER, app

c = TestClient(app)


def test_every_payload_has_disclaimer_and_synthetic_flag():
    for url in ("/api/works", "/api/works/synthetic/law/1/versions",
                "/api/diff?work=synthetic/law/1&a=a&b=b", "/api/as-of?work=synthetic/law/1&date=2025-01-01"):
        j = c.get(url).json()
        assert j["disclaimer"] == DISCLAIMER and j["synthetic"] is True, url


def test_real_view_is_empty_and_never_contains_synthetic():
    j = c.get("/api/works?real=true").json()
    assert j["works"] == [] and j["synthetic"] is False and "permit" in j["note"]
    assert c.get("/api/works/synthetic/law/1/versions?real=true").status_code == 404


def test_as_of_certainty_and_provenance():
    j = c.get("/api/as-of?work=synthetic/law/1&date=2021-01-01").json()
    assert j["version_id"] == "a" and j["certainty"] == "certain"
    assert all(a["source_url"] and a["retrieved_at"] for a in j["articles"])
    assert c.get("/api/as-of?work=synthetic/law/1&date=2019-01-01").json()["certainty"] == "not_in_force"


def test_diff_has_provenance_and_kinds():
    j = c.get("/api/diff?work=synthetic/law/1&a=a&b=b").json()
    kinds = {x["kind"] for x in j["changes"]}
    assert kinds <= {"inserted", "replaced", "repealed", "renumbered", "clarified"} and kinds
    assert all(x["source_url"] and x["retrieved_at"] for x in j["changes"])


def test_unknown_work_404():
    assert c.get("/api/diff?work=nope&a=a&b=b").status_code == 404
