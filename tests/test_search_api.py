from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from taadeel import search_api
from taadeel.model import Expression, Provision
from taadeel.store import DISCLAIMER, Store, build_demo_store


@pytest.fixture
def client():
    search_api.set_store(build_demo_store())
    app = FastAPI()
    app.include_router(search_api.router)
    yield TestClient(app)
    search_api.set_store(None)


def test_disclaimer_and_synthetic_flag_everywhere(client):
    for url in ("/api/corpora", "/api/search?q=x", "/api/search?q=الجهة&corpus=synthetic",
                "/api/search?q=x&corpus=bogus", "/api/search?q=x&corpus=real"):
        j = client.get(url).json()
        assert j["disclaimer"] == DISCLAIMER and isinstance(j["synthetic"], bool), url


def test_default_is_uae_and_empty_with_note(client):
    j = client.get("/api/search?q=الجهة").json()
    assert j["corpus"] == "uae" and j["results"] == [] and j["synthetic"] is False
    assert "permit" in j["note"]


def test_synthetic_requires_explicit_corpus(client):
    syn = client.get("/api/search?q=الجهة&corpus=synthetic").json()
    assert syn["synthetic"] is True and syn["count"] > 0
    for r in syn["results"]:
        assert r["synthetic"] is True and r["source_url"] and r["retrieved_at"] and r["corpus"] == "synthetic"
    assert client.get("/api/search?q=الجهة&corpus=real").json()["results"] == []
    assert client.get("/api/search?q=الجهة").json()["results"] == []


def test_unknown_corpus_and_limit_validation(client):
    r = client.get("/api/search?q=x&corpus=bogus")
    assert r.status_code == 400 and "synthetic" in r.json()["allowed"]
    assert client.get("/api/search?q=x&limit=0").status_code == 422
    assert len(client.get("/api/search?q=الجهة&corpus=synthetic&limit=1").json()["results"]) == 1


def test_corpora_listing(client):
    j = client.get("/api/corpora").json()
    by = {c["corpus"]: c for c in j["corpora"]}
    assert j["default"] == "uae" and set(by) == {"uae", "uk-validation", "synthetic"}
    assert by["synthetic"]["synthetic"] is True and by["synthetic"]["counts"]["provisions"] > 0
    assert by["uae"]["counts"]["provisions"] == 0 and by["uae"]["synthetic"] is False
    assert "Open Government Licence" in by["uk-validation"]["licence"]
    assert "English" in by["uk-validation"]["label_en"]


def test_arabic_normalization_through_api():
    s = Store()
    e = Expression("ae/l/1", "v1", "https://x.ae/l1", "2026-10-11", valid_from=date(2020, 1, 1), effective_status="known")
    e.provisions = [Provision("art_1", "article", 1, text="تُقدَّم الطلبات خلال ٣٠ يوما إلى الجهة")]
    s.add_expression(e, "uae", licence="test")
    search_api.set_store(s)
    try:
        app = FastAPI()
        app.include_router(search_api.router)
        c = TestClient(app)
        for q in ("٣٠ يوماً", "30 يوما", "الطَّلَبات"):
            j = c.get("/api/search", params={"q": q}).json()
            assert j["count"] == 1 and j["results"][0]["eid"] == "art_1", q
            assert j["results"][0]["source_url"] == "https://x.ae/l1"
    finally:
        search_api.set_store(None)


def test_dependency_override():
    s = Store()
    app = FastAPI()
    app.include_router(search_api.router)
    app.dependency_overrides[search_api.store_dependency] = lambda: s
    j = TestClient(app).get("/api/corpora").json()
    assert all(c["counts"]["provisions"] == 0 for c in j["corpora"])


def test_api_mounts_search_and_uk_corpus_endpoints():
    from fastapi.testclient import TestClient

    from taadeel import search_api
    from taadeel.api import app
    from taadeel.store import Store, build_demo_store

    search_api.set_store(build_demo_store())
    try:
        c = TestClient(app)
        r = c.get("/api/search", params={"q": "section", "corpus": "synthetic"})
        assert r.status_code == 200 and r.json()["synthetic"] is True
        assert c.get("/api/store/works", params={"corpus": "uae"}).json()["works"] == []
        assert c.get("/api/store/versions", params={"work": "nope", "corpus": "uae"}).status_code == 404
    finally:
        search_api.set_store(None)
