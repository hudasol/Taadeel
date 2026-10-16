import hashlib
import json
from datetime import date

import pyarrow.parquet as pq
import pytest

from taadeel.model import Expression, Provision
from taadeel.store import Store, StoreError, build_demo_store, query_tokens


def mk(work="uk/ukpga/2000/1", eid="e1", texts=None, *, src="https://example.org/x", ret="2026-10-11",
       synthetic=False, lang="en", vf=date(2020, 1, 1)):
    e = Expression(work_id=work, expression_id=eid, source_url=src, retrieved_at=ret, language=lang,
                   valid_from=vf, effective_status="known", issue_date=vf, synthetic=synthetic)
    for i, t in enumerate(texts or ["The licence holder shall notify the authority."], 1):
        e.provisions.append(Provision(eid=f"art_{i}", kind="article", number=i, text=t))
    return e


UK = dict(licence="OGL v3.0", attribution="Contains public sector information (OGL v3.0)")


@pytest.fixture
def ar_store():
    s = Store()
    e = Expression("ae/law/1", "v1", "https://example.ae/law1", "2026-10-11", language="ar",
                   valid_from=date(2020, 1, 1), effective_status="known")
    e.provisions = [
        Provision("art_1", "article", 1, text="يَجِبُ على المُنشَأة تقديم الطلب خلال ٣٠ يوما إلى الجهة المختصة."),
        Provision("art_2", "article", 2, text="تُلزَم الجهة عند إصدار الترخيص بالمدة المحددة."),
        Provision("art_3", "article", 3, text="يسري هذا القانون على الأشخاص في الدولة."),
    ]
    s.add_expression(e, "uae", licence="test permission")
    return s


def test_provenance_required():
    s = Store()
    with pytest.raises(StoreError):
        s.add_expression(mk(src=""), "uk-validation", **UK)
    with pytest.raises(StoreError):
        s.add_expression(mk(ret=""), "uk-validation", **UK)
    assert s.corpus_counts()["uk-validation"]["provisions"] == 0


def test_sql_constraints_block_missing_provenance():
    s = Store()
    s.add_expression(mk(), "uk-validation", **UK)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        s._db.execute("INSERT INTO provisions(eid,expression_id,kind,text,text_norm,source_url,retrieved_at,work_id,corpus)"
                      " VALUES ('x','e1','article','t','t','','2026','uk/ukpga/2000/1','uk-validation')")
    with pytest.raises(sqlite3.IntegrityError):  # synthetic prefix under a non synthetic corpus
        s._db.execute("INSERT INTO works(work_id,corpus,source_url) VALUES ('synthetic/x','uae','u')")


def test_synthetic_rules():
    s = Store()
    with pytest.raises(StoreError):
        s.add_expression(mk(work="synthetic/w", synthetic=True), "uae", licence="x")
    with pytest.raises(StoreError):
        s.add_expression(mk(work="synthetic/w", synthetic=True), "uk-validation", **UK)
    with pytest.raises(StoreError):
        s.add_expression(mk(work="uk/real", synthetic=True), "synthetic")
    with pytest.raises(StoreError):
        s.add_expression(mk(work="uk/real"), "synthetic")
    s.add_expression(mk(work="synthetic/w", synthetic=True), "synthetic")


def test_licence_required_for_real_corpora():
    s = Store()
    with pytest.raises(StoreError):
        s.add_expression(mk(), "uk-validation")
    with pytest.raises(StoreError):
        s.add_expression(mk(work="ae/x", lang="ar"), "uae")


def test_work_cannot_change_corpus_and_duplicates_rejected():
    s = Store()
    s.add_expression(mk(), "uk-validation", **UK)
    with pytest.raises(StoreError):
        s.add_expression(mk(eid="e2"), "uae", licence="x")
    with pytest.raises(StoreError):
        s.add_expression(mk(), "uk-validation", **UK)


def test_corpus_separation():
    s = build_demo_store()
    s.add_expression(mk(texts=["Synthetic word الترخيص in a real UK text"]), "uk-validation", **UK)
    assert s.list_works("uae") == []
    assert [w["work_id"] for w in s.list_works("real")] == ["uk/ukpga/2000/1"]
    assert s.search("الجهة", "uae") == []
    assert all(not r["synthetic"] for r in s.search("الترخيص", "real", 100))
    syn = s.search("الترخيص", "synthetic", 100)
    assert syn and all(r["corpus"] == "synthetic" and r["work_id"].startswith("synthetic/") for r in syn)
    assert s.get_expression("synthetic/law/1", "a", corpus="real") is None
    assert s.get_expression("synthetic/law/1", "a", corpus="synthetic") is not None
    with pytest.raises(LookupError):
        s.as_of("synthetic/law/1", date(2021, 1, 1), "uae")
    with pytest.raises(StoreError):
        s.search("x", "bogus")


def test_roundtrip_expression(ar_store):
    e = ar_store.get_expression("ae/law/1", "v1", "uae")
    assert e.language == "ar" and e.valid_from == date(2020, 1, 1) and len(e.provisions) == 3
    assert e.provisions[0].text.startswith("يَجِبُ")


def test_arabic_query_normalization(ar_store):
    base = {r["eid"] for r in ar_store.search("المنشأة", "uae")}
    assert base == {"art_1"}
    for q in ("المُنْشَأَة", "المنشاة", "الْمَنْشَأَةَ"):
        assert {r["eid"] for r in ar_store.search(q, "uae")} == {"art_1"}, q
    # alef variants and digits: ٣٠ / 30 / ۳۰ all find the same provision
    assert {r["eid"] for r in ar_store.search("٣٠ يوما", "uae")} == {"art_1"}
    assert {r["eid"] for r in ar_store.search("30 يوما", "uae")} == {"art_1"}
    assert {r["eid"] for r in ar_store.search("۳۰", "uae")} == {"art_1"}
    # alef-hamza vs bare alef; alef maqsura vs yaa in query
    assert {r["eid"] for r in ar_store.search("إصدار الترخيص", "uae")} == {"art_2"}
    assert {r["eid"] for r in ar_store.search("اصدار", "uae")} == {"art_2"}
    assert {r["eid"] for r in ar_store.search("علي", "uae")} >= {"art_1"}    # على -> علي
    assert {r["eid"] for r in ar_store.search("على", "uae")} >= {"art_1"}
    assert query_tokens("٣٠ أَ") == ["30", "ا"]


def test_search_provenance_and_original_text(ar_store):
    (r,) = ar_store.search("الترخيص", "uae")
    assert r["source_url"] == "https://example.ae/law1" and r["retrieved_at"] == "2026-10-11"
    assert "تُلزَم" in r["text"] and "تُلزَم" in r["snippet"]       # original diacritics preserved
    assert r["highlights"]
    a, b = r["highlights"][0]
    assert "ترخيص" in r["snippet"][a:b].replace("ـ", "")
    assert r["corpus"] == "uae" and r["synthetic"] is False


def test_empty_and_lang_and_limit(ar_store):
    assert ar_store.search("", "uae") == [] and ar_store.search("؟؟", "uae") == []
    assert ar_store.search("الجهة", "uae", lang="en") == []
    assert len(ar_store.search("الجهة", "uae", lang="ar")) == 2
    assert len(ar_store.search("الجهة", "uae", limit=1)) == 1
    assert ar_store.search('"; DROP TABLE works; --', "uae") == []     # FTS syntax is neutralized


def test_prefix_fallback(ar_store):
    assert {r["eid"] for r in ar_store.search("الترخ", "uae")} == {"art_2"}


def test_ranking_sanity():
    s = Store()
    s.add_expression(mk(texts=[
        "licence licence licence renewal of the licence",
        "A passing mention of licence among many other unrelated words about fees and registers and offices today",
        "Nothing relevant here", "Offices open daily", "Registers are kept", "Fees are payable",
    ]), "uk-validation", **UK)
    res = s.search("licence", "uk-validation")
    assert [r["eid"] for r in res] == ["art_1", "art_2"]
    assert res[0]["score"] > res[1]["score"]
    assert s.search("licence renewal", "uk-validation")[0]["eid"] == "art_1"
    assert s.search("renewal fees", "uk-validation") == []    # AND semantics


def test_as_of_via_store():
    s = build_demo_store()
    assert s.as_of("synthetic/law/1", date(2021, 1, 1), "synthetic").version_id == "a"
    assert s.as_of("synthetic/law/1", date(2025, 1, 1), "synthetic").version_id == "b"
    assert s.as_of("synthetic/law/1", date(2019, 1, 1), "synthetic").certainty == "not_in_force"


def test_demo_store_contents():
    s = build_demo_store()
    c = s.corpus_counts()
    assert c["synthetic"]["works"] == 1 and c["synthetic"]["expressions"] == 2 and c["synthetic"]["changes"] > 0
    assert c["synthetic"]["amendment_events"] == c["synthetic"]["changes"]
    assert sum(c["uae"].values()) == 0 and sum(c["uk-validation"].values()) == 0


def test_amendment_events_require_provenance():
    s = build_demo_store()
    with pytest.raises(StoreError):
        s.add_amendment_events([{"target_work_id": "synthetic/law/1", "op": "replace", "source_url": "",
                                 "retrieved_at": "2026-10-11"}])
    with pytest.raises(StoreError):
        s.add_amendment_events([{"target_work_id": "nope", "op": "replace", "source_url": "u", "retrieved_at": "r"}])


def test_parquet_roundtrip_and_manifest(tmp_path):
    s = build_demo_store()
    s.add_expression(mk(texts=["First", "Second"]), "uk-validation", **UK)
    m = s.export_parquet(tmp_path)
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert man["files"] == m["files"]
    for name in ("works", "provisions", "changes", "amendment_events"):
        f = tmp_path / f"{name}.parquet"
        assert man["files"][f"{name}.parquet"]["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
        assert man["files"][f"{name}.parquet"]["rows"] == pq.read_table(f).num_rows
    prov = pq.read_table(tmp_path / "provisions.parquet").to_pylist()
    c = s.corpus_counts()
    assert len(prov) == c["synthetic"]["provisions"] + c["uk-validation"]["provisions"]
    assert all(r["source_url"] and r["retrieved_at"] for r in prov)
    assert {r["corpus"] for r in prov} == {"synthetic", "uk-validation"}
    assert man["corpus_counts"]["synthetic"]["provisions"] == c["synthetic"]["provisions"]
    assert man["corpus_counts"]["uae"]["provisions"] == 0 and man["contains_synthetic"] is True
    ch = pq.read_table(tmp_path / "changes.parquet").to_pylist()
    assert ch and json.loads(ch[0]["words_json"]) is not None


def test_export_real_only_excludes_synthetic(tmp_path):
    s = build_demo_store()
    s.add_expression(mk(), "uk-validation", **UK)
    m = s.export_parquet(tmp_path, corpus="real")
    assert m["contains_synthetic"] is False and "synthetic" not in m["corpus_counts"]
    for name in ("works", "provisions", "changes", "amendment_events"):
        assert all(r["corpus"] != "synthetic" for r in pq.read_table(tmp_path / f"{name}.parquet").to_pylist())
