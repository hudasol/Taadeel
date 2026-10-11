"""Synthetic Arabic PDF generator for testing the PDF extractor.

Every PDF produced here carries the visible banner and the metadata label
``SYNTHETIC TEST DOCUMENT - NOT LEGISLATION``. Body text is random words from
the synthetic word pool (see synthetic.py); it is not law and has no meaning.

Rendering: DejaVu Sans, arabic-reshaper (contextual presentation forms) and
python-bidi (visual order), because fpdf2's HarfBuzz shaping needs
``uharfbuzz`` which is not installed. This deliberately reproduces the common
real-world pitfall: the PDF stores presentation forms in visual order, so the
extractor must fold and un-reverse them (these display correctly in a viewer).
Layout ``logical`` stores raw logical codepoints (no shaping, no reordering;
it would display wrongly) as the opposite case: extraction needs no reversal.
"""
from __future__ import annotations

import io
import random
from dataclasses import dataclass, field

from fpdf import FPDF

from .synthetic import _POOL, _sentence

LABEL = "SYNTHETIC TEST DOCUMENT - NOT LEGISLATION"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_AR_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_DIAC = ["َ", "ُ", "ِ", "ّ", "ْ"]

LAYOUTS = [
    "single", "header_footer", "multipage", "arabic_indic",
    "diacritics", "bis", "structured", "logical", "clauses", "long", "mixed", "everything",
]


@dataclass
class GoldArticle:
    number: int
    bis: int
    text: str


@dataclass
class SyntheticPdf:
    data: bytes
    gold: list[GoldArticle]
    layout: str
    seed: int
    header: str = ""          # running header text (empty if none)
    footer_prefix: str = ""   # fixed footer words (page number varies)
    pages: int = 0
    expect_reversed: bool = True
    meta: dict = field(default_factory=dict)


def _shape(s: str, mode: str) -> str:
    if mode == "logical":
        return s
    import arabic_reshaper
    from bidi.algorithm import get_display
    # keep diacritics; reshaper would otherwise drop them
    cfg = arabic_reshaper.ArabicReshaper(configuration={"delete_harakat": False, "support_ligatures": True})
    return get_display(cfg.reshape(s))


class _Doc(FPDF):
    def __init__(self, mode: str, header: str, footer_prefix: str, indic: bool, running: bool):
        super().__init__(format=(148, 210))
        self.mode, self.hdr, self.fpre, self.indic, self.running = mode, header, footer_prefix, indic, running
        self.add_font("DJV", "", FONT)
        self.set_auto_page_break(False)
        self.set_margins(15, 22, 15)

    def line(self, text: str, size: float = 11, bold_gap: float = 0.0) -> None:
        self.set_font("DJV", size=size)
        self.cell(0, 6.5 + bold_gap, _shape(text, self.mode), align="R", new_x="LMARGIN", new_y="NEXT")

    def header(self) -> None:
        self.set_font("DJV", size=7)
        self.set_xy(15, 6)
        self.cell(0, 4, LABEL, align="C", new_x="LMARGIN", new_y="NEXT")
        if self.running:
            self.set_font("DJV", size=9)
            self.cell(0, 5, _shape(self.hdr, self.mode), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_y(22)

    def footer(self) -> None:
        if not self.running:
            return
        n = str(self.page_no())
        if self.indic:
            n = n.translate(_AR_INDIC)
        self.set_xy(15, -14)
        self.set_font("DJV", size=9)
        self.cell(0, 5, _shape(f"{self.fpre} {n}", self.mode), align="C")

    def wrap(self, text: str, size: float = 11) -> list[str]:
        self.set_font("DJV", size=size)
        width = self.w - self.l_margin - self.r_margin
        lines, cur = [], ""
        for w in text.split():
            trial = (cur + " " + w).strip()
            if self.get_string_width(_shape(trial, self.mode)) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def put(self, text: str, size: float = 11) -> None:
        for ln in self.wrap(text, size):
            if self.get_y() > self.h - 24:
                self.add_page()
            self.line(ln, size)


def _diacritize(rng: random.Random, text: str) -> str:
    out = []
    for w in text.split():
        if rng.random() < 0.35 and len(w) > 3:
            i = rng.randrange(1, len(w) - 1)
            w = w[:i] + rng.choice(_DIAC) + w[i:]
        out.append(w)
    return " ".join(out)


def _label(number: int, bis: bool, indic: bool) -> str:
    n = str(number).translate(_AR_INDIC) if indic else str(number)
    return f"المادة ({n})" + (" مكرر" if bis else "")


def make_pdf(layout: str, seed: int, n_articles: int = 8) -> SyntheticPdf:
    """Build one synthetic PDF and its ground truth. Layouts: see LAYOUTS."""
    if layout not in LAYOUTS:
        raise ValueError(layout)
    rng = random.Random(f"{layout}:{seed}")
    running = layout in ("header_footer", "multipage", "long", "everything")
    clauses = layout in ("clauses", "everything")
    mixed = layout == "mixed"
    if layout == "long":
        n_articles = max(n_articles, 40)
    indic = layout in ("arabic_indic", "everything")
    dia = layout in ("diacritics", "everything")
    bis = layout in ("bis", "everything")
    structured = layout in ("structured", "everything")
    long_bodies = layout in ("multipage", "everything")
    mode = "logical" if layout == "logical" else "visual"
    header = " ".join(rng.choice(_POOL) for _ in range(4))
    footer_prefix = "صفحة"
    doc = _Doc(mode, header, footer_prefix, indic, running)
    doc.set_title(LABEL)
    doc.set_subject(LABEL)
    doc.set_keywords("synthetic, test, " + LABEL)
    doc.set_author("taadeel synthetic generator")
    doc.add_page()
    gold: list[GoldArticle] = []
    number = rng.randint(1, 5)
    for i in range(n_articles):
        if structured and i % 4 == 0:
            doc.put(f"الباب {['الأول', 'الثاني', 'الثالث'][i // 4 % 3]}", 12)
            doc.put(f"الفصل {['الأول', 'الثاني'][i // 4 % 2]}", 12)
        is_bis = bis and i % 3 == 2
        if is_bis:
            number_i = number  # same number as previous article, bis variant
        else:
            number += 1 if i else 0
            number_i = number
        n_sent = rng.randint(6, 10) if long_bodies else rng.randint(1, 3)
        paras = [" ".join(_sentence(rng) for _ in range(n_sent))]
        if clauses:  # numbered clauses on their own lines: "1- ..." with mixed digit runs
            paras += [f"{k}- {_sentence(rng, 6, 12)}" for k in range(1, rng.randint(3, 4))]
        if mixed:  # embedded Latin/digit runs and parentheses inside Arabic sentences
            bits = ["ISO 9001", "(12)", "2024", "No. 45", "PDF"]
            paras = [" ".join(w if rng.random() > 0.15 else rng.choice(bits) for w in x.split()) for x in paras]
        if dia:
            paras = [_diacritize(rng, x) for x in paras]
        body = "\n".join(paras)
        if doc.get_y() > doc.h - 40:
            doc.add_page()
        doc.put(_label(number_i, is_bis, indic), 12)
        for para in paras:
            doc.put(para)
        gold.append(GoldArticle(number_i, 1 if is_bis else 0, body))
    buf = io.BytesIO(doc.output())
    return SyntheticPdf(buf.getvalue(), gold, layout, seed, header if running else "",
                        footer_prefix if running else "", doc.page_no(), expect_reversed=(mode == "visual"))


def make_image_only_pdf(seed: int = 0) -> bytes:
    """A PDF whose only content is a raster image (no text layer): needs OCR."""
    from PIL import Image, ImageDraw
    rng = random.Random(seed)
    img = Image.new("L", (400, 300), 255)
    d = ImageDraw.Draw(img)
    for _ in range(40):
        y = rng.randrange(10, 290)
        d.line([(rng.randrange(0, 60), y), (rng.randrange(200, 390), y)], fill=0, width=2)
    pdf = FPDF(format=(148, 210))
    pdf.set_title(LABEL)
    pdf.add_page()
    pdf.set_font("Helvetica", size=7)
    # banner is drawn into the image so the page still has no text layer
    d.text((8, 4), LABEL, fill=0)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    pdf.image(bio, x=10, y=20, w=120)
    return bytes(pdf.output())
