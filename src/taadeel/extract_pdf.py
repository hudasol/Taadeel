"""PDF text extraction for Arabic legislation (text-layer PDFs only).

Pipeline: pypdf per-page text (layout mode, bidi-aware) -> strip bidi/format
marks -> NFKC fold (presentation forms -> base letters) -> visual-order
detection and correction -> page-number and repeated header/footer removal ->
soft-hyphen/hyphenation joins. Output feeds ``parse.parse_structure``.

Validated ONLY on synthetic PDFs (see docs/EXTRACTION_PDF.md). Image-only
PDFs are detected and flagged "needs OCR"; there is no OCR here.
"""
from __future__ import annotations

import io
import re
import unicodedata
import warnings
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .model import Expression, validate_expression
from .parse import parse_structure

NEEDS_OCR = "needs OCR: no extractable text layer (image-only PDF); OCR is out of scope"

_FORMAT_MARKS = re.compile("[​-‏‪-‮⁦-⁩﻿­]")
_AR = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_MIRROR = str.maketrans("()[]{}<>«»", ")(][}{><»«")
_RUN = re.compile(r"[A-Za-z0-9٠-٩][A-Za-z0-9٠-٩ .,:/\-]*[A-Za-z0-9٠-٩]|[A-Za-z0-9٠-٩]")
_PAGE_NO = re.compile(
    r"^\s*(?:[-–—]\s*)?\d{1,4}(?:\s*[-–—])?\s*$"
    r"|^\s*(?:صفحة|الصفحة|page|p\.)\s*\d{1,4}(?:\s*(?:من|of|/)\s*\d{1,4})?\s*$",
    re.IGNORECASE,
)
_ARTICLE_LINE = re.compile(r"^(?:المادة|مادة)\b")

# Words that are very frequent in forward Arabic; their reversals are the
# reversed-text signal. Document-level vote, see detect_reversed().
_FWD_MARKERS = ("المادة", "الباب", "الفصل", "الجهة", "التي", "الذي", "هذا", "على", "عن", "من", "في", "إلى", "الى")


@dataclass
class ExtractResult:
    text: str
    pages: list[str]
    warnings: list[str] = field(default_factory=list)
    method: str = "pypdf-layout"
    reversed_detected: bool = False
    needs_ocr: bool = False
    stripped_lines: list[str] = field(default_factory=list)


def _clean(s: str) -> str:
    return _FORMAT_MARKS.sub("", s).replace("\r", "")


def detect_reversed(lines: list[str]) -> bool:
    """Heuristic: is Arabic text stored/extracted in visual (reversed) order?

    Count tokens that look like forward Arabic (marker words, or tokens that
    start with the definite article ال) against tokens that look reversed
    (reversed marker words, or tokens ending in لا, i.e. a reversed ال). The
    document is reversed iff reversed evidence strictly exceeds forward
    evidence. Mixed-order documents are not handled (documented limitation).
    """
    fwd = rev = 0
    rev_markers = {m[::-1] for m in _FWD_MARKERS}
    for ln in lines:
        for tok in re.findall(r"[ء-ي]+", ln):
            if tok in _FWD_MARKERS:
                fwd += 2
            elif tok in rev_markers:
                rev += 2
            if len(tok) > 3:
                fwd += tok.startswith("ال")
                rev += tok.endswith("لا")
    return rev > fwd


def _unreverse(line: str) -> str:
    """Reverse a visual-order line to logical order.

    Whole-line character reversal, then re-reverse embedded digit/Latin runs
    (they were stored left-to-right) and swap mirrored brackets. Lines with no
    Arabic are left untouched.
    """
    if not _AR.search(line):
        return line
    r = line[::-1].translate(_MIRROR)
    return _RUN.sub(lambda m: m.group(0)[::-1], r)


def _key(line: str) -> str:
    return re.sub(r"\d+", "#", line.translate(_DIGITS)).strip()


def _strip_repeated(pages: list[list[str]], frac: float = 0.6, edge: int = 3) -> tuple[list[list[str]], list[str]]:
    """Remove lines repeated (digits masked) in the top/bottom ``edge`` lines of >= frac of pages.

    Needs >= 2 pages. Article/part/chapter headings are never stripped.
    """
    removed: list[str] = []
    if len(pages) >= 2:
        count: Counter[str] = Counter()
        for lines in pages:
            edges = set(_key(x) for x in lines[:edge] + lines[-edge:] if x.strip())
            count.update(edges)
        bad = {k for k, c in count.items() if c >= frac * len(pages) and not _ARTICLE_LINE.match(k)
               and not k.startswith(("الباب", "الفصل"))}
        out = []
        for lines in pages:
            keep = []
            for i, x in enumerate(lines):
                near_edge = i < edge or i >= len(lines) - edge
                if near_edge and _key(x) in bad:
                    removed.append(x)
                else:
                    keep.append(x)
            out.append(keep)
        pages = out
    # page-number lines on the first/last two lines of each page
    out = []
    for lines in pages:
        keep = []
        for i, x in enumerate(lines):
            if (i < 2 or i >= len(lines) - 2) and _PAGE_NO.match(x.translate(_DIGITS)):
                removed.append(x)
            else:
                keep.append(x)
        out.append(keep)
    return out, removed


def _join_hyphenation(lines: list[str]) -> list[str]:
    """Join Latin words split by a trailing hyphen (Arabic is not hyphenated)."""
    out: list[str] = []
    for ln in lines:
        if out and re.search(r"[a-z]-$", out[-1]) and re.match(r"[a-z]", ln):
            out[-1] = out[-1][:-1] + ln
        else:
            out.append(ln)
    return out


def _page_texts(data: bytes) -> tuple[list[str], list[str]]:
    from pypdf import PdfReader
    warns: list[str] = []
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            warns.append("encrypted PDF: could not decrypt")
            return [], warns
    pages = []
    for i, pg in enumerate(reader.pages):
        try:
            t = pg.extract_text(extraction_mode="layout")
        except Exception as exc:  # noqa: BLE001
            warns.append(f"page {i + 1}: layout extraction failed ({exc!r}); fell back to plain mode")
            try:
                t = pg.extract_text()
            except Exception as exc2:  # noqa: BLE001
                warns.append(f"page {i + 1}: extraction failed ({exc2!r})")
                t = ""
        pages.append(t or "")
    return pages, warns


def extract_text(source: str | Path | bytes) -> ExtractResult:
    data = source if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
    raw_pages, warns = _page_texts(bytes(data))
    cleaned = [[re.sub(r"[ \t]+", " ", ln).strip() for ln in _clean(p).split("\n")] for p in raw_pages]
    cleaned = [[ln for ln in p if ln] for p in cleaned]
    fold = unicodedata.normalize
    all_lines = [fold("NFKC", ln) for p in cleaned for ln in p]
    res = ExtractResult(text="", pages=[], warnings=warns)
    if not all_lines or not any(_AR.search(x) or re.search(r"[A-Za-z0-9]", x) for x in all_lines):
        res.needs_ocr = True
        res.warnings.append(NEEDS_OCR)
        res.pages = ["" for _ in raw_pages]
        return res
    if not any(_AR.search(x) for x in all_lines):
        res.warnings.append("no Arabic text found in text layer; may be scanned with a stray text layer")
    if detect_reversed(all_lines):
        res.reversed_detected = True
        # reverse BEFORE NFKC: a lam-alef ligature is one glyph whose NFKC
        # expansion is already in logical order; reversing after folding
        # would flip it to alef+lam.
        cleaned = [[_unreverse(x) for x in p] for p in cleaned]
        res.warnings.append("visual-order (reversed) Arabic detected and corrected by heuristic")
    cleaned = [[re.sub(r"[ \t]+", " ", fold("NFKC", x)).strip() for x in p] for p in cleaned]
    stripped, removed = _strip_repeated(cleaned)
    res.stripped_lines = removed
    stripped = [_join_hyphenation(p) for p in stripped]
    res.pages = ["\n".join(p) for p in stripped]
    res.text = "\n".join(res.pages)
    if not any(re.search(r"(?:المادة|مادة)\s*\(?\s*[0-9٠-٩]+", x) for x in res.text.split("\n")):
        res.warnings.append("no article headings recognised; check order/shaping")
    return res


def extract_expression_ex(source: str | Path | bytes, expr_meta: dict) -> tuple[Expression, ExtractResult]:
    """Extract and parse. ``expr_meta`` must carry work_id, expression_id,
    source_url and retrieved_at; optional: synthetic, valid_from, issue_date,
    effective_status, language."""
    for k in ("work_id", "expression_id", "source_url", "retrieved_at"):
        if not expr_meta.get(k):
            raise ValueError(f"expr_meta missing {k}")
    res = extract_text(source)
    expr = Expression(
        work_id=expr_meta["work_id"], expression_id=expr_meta["expression_id"],
        source_url=expr_meta["source_url"], retrieved_at=expr_meta["retrieved_at"],
        language=expr_meta.get("language", "ar"),
        valid_from=expr_meta.get("valid_from"), issue_date=expr_meta.get("issue_date"),
        effective_status=expr_meta.get("effective_status", "unknown"),
        synthetic=bool(expr_meta.get("synthetic", False)),
    )
    if res.needs_ocr:
        warnings.warn(NEEDS_OCR, stacklevel=2)
    else:
        parse_structure(res.text, expr)
    validate_expression(expr)
    return expr, res


def extract_expression(source: str | Path | bytes, expr_meta: dict) -> Expression:
    return extract_expression_ex(source, expr_meta)[0]


__all__ = ["ExtractResult", "extract_text", "extract_expression", "extract_expression_ex", "detect_reversed", "NEEDS_OCR", "date"]
