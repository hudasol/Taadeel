import json

from taadeel.export import export


def test_export_is_deterministic_labeled_and_has_card(tmp_path):
    f1 = export(tmp_path / "a", n=3)
    f2 = export(tmp_path / "b", n=3)
    assert f1.read_bytes() == f2.read_bytes()
    rows = [json.loads(line) for line in f1.read_text(encoding="utf-8").splitlines()]
    assert rows and all(r["synthetic"] is True and r["source_url"] and r["retrieved_at"] for r in rows)
    card = (tmp_path / "a" / "DATA_CARD.md").read_text(encoding="utf-8")
    assert "Synthetic data only" in card and "not legal advice" in card.lower()
