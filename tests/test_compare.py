import pytest
from fastapi.testclient import TestClient

from taadeel import cli
from taadeel.api import app
from taadeel.compare import MAX_ARTICLES, CompareError, compare_texts, detect_language

OLD_EN = """Section 1 Scope
This Act applies to all licensed premises.
Section 2 Fees
A fee of 100 dirhams is payable.
Section 3 Records
Records must be kept for five years.
"""
NEW_EN = """Section 1 Scope
This Act applies to all licensed premises.
Section 1A Definitions
In this Act premises means a building.
Section 2 Fees
A fee of 150 dirhams is payable.
"""
OLD_AR = "المادة (1)\nيسري هذا القانون على الجميع.\nالمادة (2)\nتلتزم المنشأة بتقديم الإخطار خلال ثلاثين يوما.\n"
NEW_AR = OLD_AR.replace("ثلاثين", "ستين") + "المادة (3)\nنص جديد للمادة.\n"


def kinds(res):
    return {(c["kind"], c["a_eid"], c["b_eid"]) for c in res["changes"]}


def test_english_headings_give_insert_replace_repeal():
    r = compare_texts(OLD_EN, NEW_EN)
    assert r["language"] == "en"
    assert kinds(r) == {("replaced", "s_2", "s_2"), ("repealed", "s_3", None), ("inserted", None, "s_1A")}
    assert r["counts"] == {"replaced": 1, "repealed": 1, "inserted": 1}


def test_arabic_headings():
    r = compare_texts(OLD_AR, NEW_AR)
    assert r["language"] == "ar"
    assert kinds(r) == {("replaced", "art_2", "art_2"), ("inserted", None, "art_3")}


def test_identical_texts_have_no_changes():
    assert compare_texts(OLD_EN, OLD_EN)["changes"] == []


def test_text_without_headings_is_rejected():
    with pytest.raises(CompareError, match="no article headings"):
        compare_texts("just a paragraph", NEW_EN)


def test_article_cap():
    big = "\n".join(f"Section {i}\ntext number {i}" for i in range(1, MAX_ARTICLES + 2))
    with pytest.raises(CompareError, match="limit"):
        compare_texts(big, big)


def test_language_detection():
    assert detect_language(OLD_AR) == "ar" and detect_language(OLD_EN) == "en"


def test_api_compare_ok_and_errors():
    c = TestClient(app)
    j = c.post("/api/compare", json={"old": OLD_EN, "new": NEW_EN}).json()
    assert j["counts"]["replaced"] == 1 and j["user_supplied"] is True and j["disclaimer"]
    assert c.post("/api/compare", json={"old": "x", "new": NEW_EN}).status_code == 422
    assert c.post("/api/compare", json={"old": OLD_EN}).status_code == 422
    assert c.post("/api/compare", json={"old": OLD_EN, "new": NEW_EN, "lang": "fr"}).status_code == 422


def test_cli_diff(tmp_path, capsys):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text(OLD_EN, encoding="utf-8")
    b.write_text(NEW_EN, encoding="utf-8")
    assert cli.main(["diff", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "inserted" in out and "s_1A" in out and "not legal advice" in out
    assert cli.main(["diff", str(a), str(b), "--json"]) == 0
    assert '"replaced": 1' in capsys.readouterr().out


def test_cli_diff_without_headings_exits_2(tmp_path, capsys):
    a = tmp_path / "a.txt"
    a.write_text("nothing here", encoding="utf-8")
    assert cli.main(["diff", str(a), str(a)]) == 2
