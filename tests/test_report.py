"""Generated documents must equal what the generator produces from results/ (no hand edited numbers)."""
from __future__ import annotations

from pathlib import Path

from taadeel import report
from taadeel.facts import facts

ROOT = Path(__file__).resolve().parents[1]


def test_readme_block_and_uk_doc_match_the_generator():
    doc, block = report.build()
    assert block in (ROOT / "README.md").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "VALIDATION_UK.md").read_text(encoding="utf-8") == doc


def test_rendered_templates_match_the_generator():
    F = facts()
    tdir = ROOT / "docs" / "templates"
    for t in tdir.rglob("*.md"):
        dest = ROOT / "docs" / t.relative_to(tdir)
        assert dest.read_text(encoding="utf-8") == t.read_text(encoding="utf-8").format_map(F), dest


def test_generated_docs_have_no_em_dash():
    for p in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]:
        assert "—" not in p.read_text(encoding="utf-8"), p
