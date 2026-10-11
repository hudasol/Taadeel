"""Score the PDF extractor on SYNTHETIC PDFs only (random text, not law).

Run ``pytest -q -s tests/test_extract_pdf.py`` to see measured values, or
``python tests/test_extract_pdf.py`` for the markdown table used in
docs/EXTRACTION_PDF.md. Results say nothing about real-world PDFs.
"""
from __future__ import annotations

import functools
import io
import sys
import warnings
from dataclasses import dataclass

import pytest
from pypdf import PdfReader

from taadeel import extract_pdf as ep
from taadeel.extract_pdf import extract_expression_ex, extract_text
from taadeel.normalize import normalize
from taadeel.synthetic_pdf import LABEL, LAYOUTS, make_image_only_pdf
from taadeel.synthetic_pdf import make_pdf as _make_pdf

make_pdf = functools.cache(_make_pdf)  # generation is slow; PDFs are deterministic

META = dict(work_id="synthetic/pdf/1", expression_id="synthetic-pdf-v1",
            source_url="synthetic://taadeel/pdf-test", retrieved_at="2026-10-12", synthetic=True)
SEEDS = (0, 1)
MAIN = [l for l in LAYOUTS if l != "mixed"]


@dataclass
class Score:
    layout: str
    n_pdfs: int = 0
    articles: int = 0
    number_ok: int = 0
    text_ok: int = 0
    leaks: int = 0
    reversed_ok: int = 0

    @property
    def number_rate(self) -> float:
        return self.number_ok / self.articles

    @property
    def text_rate(self) -> float:
        return self.text_ok / self.articles


def score_layout(layout: str, seeds=SEEDS) -> Score:
    sc = Score(layout)
    for seed in seeds:
        pdf = make_pdf(layout, seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            expr, res = extract_expression_ex(pdf.data, META)
        arts = {a.key: a.text_norm for a in expr.articles()}
        sc.n_pdfs += 1
        sc.reversed_ok += res.reversed_detected == pdf.expect_reversed
        for g in pdf.gold:
            sc.articles += 1
            sc.number_ok += (g.number, g.bis) in arts
            sc.text_ok += arts.get((g.number, g.bis)) == normalize(g.text)
        junk = [LABEL.lower(), "صفحة"] + ([normalize(pdf.header)] if pdf.header else [])
        for t in arts.values():
            sc.leaks += any(j in t.lower() for j in junk)
    return sc


def test_at_least_15_pdfs_scored():
    assert len(MAIN) * len(SEEDS) >= 15


@pytest.mark.parametrize("layout", MAIN)
def test_layout_scores(layout):
    sc = score_layout(layout)
    print(f"\n[synthetic-only] {layout}: pdfs={sc.n_pdfs} articles={sc.articles} "
          f"number_recovery={sc.number_rate:.3f} text_exact={sc.text_rate:.3f} "
          f"leaks={sc.leaks} reversal_flag_ok={sc.reversed_ok}/{sc.n_pdfs}")
    assert sc.number_rate >= 0.99
    assert sc.text_rate >= 0.98
    assert sc.leaks == 0
    assert sc.reversed_ok == sc.n_pdfs


def test_overall_thresholds():
    scores = [score_layout(l) for l in MAIN]
    a = sum(s.articles for s in scores)
    nr = sum(s.number_ok for s in scores) / a
    tr = sum(s.text_ok for s in scores) / a
    print(f"\n[synthetic-only] OVERALL pdfs={sum(s.n_pdfs for s in scores)} articles={a} "
          f"number_recovery={nr:.4f} text_exact={tr:.4f} leaks={sum(s.leaks for s in scores)}")
    assert nr >= 0.99 and tr >= 0.98


@pytest.mark.xfail(reason="Latin/digit runs embedded in Arabic (e.g. 'ISO 9001', 'No. 45') change position or order "
                          "after pypdf layout extraction + whole-line reversal; measured text exact match well below 1.0",
                   strict=False)
def test_mixed_latin_digit_runs():
    sc = score_layout("mixed")
    print(f"\n[synthetic-only] mixed: articles={sc.articles} number_recovery={sc.number_rate:.3f} text_exact={sc.text_rate:.3f}")
    assert sc.text_rate >= 0.98


def test_image_only_pdf_warns_needs_ocr():
    data = make_image_only_pdf()
    res = extract_text(data)
    assert res.needs_ocr and res.text == ""
    assert any("needs OCR" in w for w in res.warnings)
    with pytest.warns(UserWarning, match="needs OCR"):
        expr, _ = extract_expression_ex(data, META)
    assert expr.provisions == []


def test_reversed_text_detected_and_corrected():
    pdf = make_pdf("single", 3)
    res = extract_text(pdf.data)
    assert res.reversed_detected
    assert "المادة" in res.text and "ةداملا" not in res.text
    assert any("reversed" in w for w in res.warnings)


def test_reversal_correction_is_what_makes_it_work(monkeypatch):
    pdf = make_pdf("single", 3)
    monkeypatch.setattr(ep, "detect_reversed", lambda lines: False)
    expr, _ = extract_expression_ex(pdf.data, META)
    assert len(expr.articles()) == 0   # without the heuristic nothing parses


def test_logical_order_pdf_not_flagged_reversed():
    pdf = make_pdf("logical", 3)
    res = extract_text(pdf.data)
    assert not res.reversed_detected


def test_header_footer_actually_stripped():
    pdf = make_pdf("multipage", 0)
    res = extract_text(pdf.data)
    assert len(res.pages) == pdf.pages >= 3
    assert res.stripped_lines
    assert normalize(pdf.header) not in normalize(res.text)
    assert "صفحة" not in res.text


def test_label_present_visible_and_in_metadata():
    pdf = make_pdf("single", 0)
    reader = PdfReader(io.BytesIO(pdf.data))
    assert LABEL in reader.pages[0].extract_text()
    assert LABEL in (reader.metadata.title or "") and LABEL in (reader.metadata.subject or "")
    assert LABEL in reader.metadata.keywords


def test_bytes_and_path_inputs_agree(tmp_path):
    pdf = make_pdf("bis", 1)
    f = tmp_path / "a.pdf"
    f.write_bytes(pdf.data)
    assert extract_text(f).text == extract_text(pdf.data).text


def test_bis_and_arabic_indic_recovered():
    pdf = make_pdf("everything", 0)
    expr, _ = extract_expression_ex(pdf.data, META)
    assert any(a.bis == 1 for a in expr.articles())
    assert expr.synthetic and expr.work_id.startswith("synthetic/")


def test_missing_provenance_rejected():
    with pytest.raises(ValueError):
        extract_expression_ex(make_pdf("single", 0).data, {"work_id": "synthetic/x"})


def measure_table() -> str:
    rows = ["| layout | PDFs | articles | number recovery | text exact | leaks | reversal flag correct |",
            "|---|---|---|---|---|---|---|"]
    tot = Score("TOTAL (excl. mixed)")
    for l in LAYOUTS:
        s = score_layout(l)
        rows.append(f"| {l} | {s.n_pdfs} | {s.articles} | {s.number_rate:.3f} | {s.text_rate:.3f} | {s.leaks} | {s.reversed_ok}/{s.n_pdfs} |")
        if l != "mixed":
            for f in ("n_pdfs", "articles", "number_ok", "text_ok", "leaks", "reversed_ok"):
                setattr(tot, f, getattr(tot, f) + getattr(s, f))
    rows.append(f"| **{tot.layout}** | {tot.n_pdfs} | {tot.articles} | {tot.number_rate:.3f} | {tot.text_rate:.3f} | {tot.leaks} | {tot.reversed_ok}/{tot.n_pdfs} |")
    return "\n".join(rows)


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    sys.stdout.reconfigure(encoding="utf-8")
    print(measure_table())
