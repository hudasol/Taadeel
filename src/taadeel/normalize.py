"""Arabic normalization for matching and indexing.

Display text is never modified; only the ``text_norm`` copy goes through this.
"""
from __future__ import annotations

import re
import unicodedata

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ALEF_VARIANTS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
_YAA = str.maketrans({"ى": "ي"})          # alef maqsura -> yaa
_HAMZA_YAA = str.maketrans({"ئ": "ي"})   # opt-in: merges distinct words (e.g. شاطئ / شاطي)
_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"
)
_PUNCT = str.maketrans({"،": ",", "؛": ";", "؟": "?", "«": '"', "»": '"'})
_WS = re.compile(r"\s+")


def normalize(text: str, *, fold_taa_marbuta: bool = False, fold_hamza_on_waw: bool = False,
              fold_hamza_on_yaa: bool = False) -> str:
    """Return a normalized copy for matching.

    Steps: NFKC (folds Arabic presentation forms), drop diacritics and tatweel,
    unify alef and yaa variants, map Arabic-Indic/Persian digits to ASCII,
    unify punctuation, collapse whitespace. Optional folds (off by default
    because they merge distinct words): taa marbuta -> haa, hamza-on-waw -> waw,
    hamza-on-yaa -> yaa.
    """
    t = unicodedata.normalize("NFKC", text)
    t = _DIACRITICS.sub("", t).replace(_TATWEEL, "")
    t = t.translate(_ALEF_VARIANTS).translate(_YAA).translate(_DIGITS).translate(_PUNCT)
    if fold_taa_marbuta:
        t = t.replace("ة", "ه")
    if fold_hamza_on_yaa:
        t = t.translate(_HAMZA_YAA)
    if fold_hamza_on_waw:
        t = t.replace("ؤ", "و")
    return _WS.sub(" ", t).strip()


# Ordinal words used after "مكرر" (bis, ter...). Values are normalized forms.
_ORDINALS = {
    "ثانيا": 2, "ثالثا": 3, "رابعا": 4, "خامسا": 5,
    "سادسا": 6, "سابعا": 7, "ثامنا": 8, "تاسعا": 9, "عاشرا": 10,
}

_ARTICLE_NO = re.compile(
    r"^\s*(?:المادة|مادة)\s*\(?\s*(\d+)\s*\)?\s*(?:(مكرر(?:ا)?)\s*(?:\(\s*(\d+)\s*\)|(" + "|".join(_ORDINALS) + r"))?)?\s*$"
)


def parse_article_label(label: str) -> tuple[int, int] | None:
    """Parse an Arabic article heading into ``(number, bis_level)``.

    ``bis_level`` is 0 for a plain article, 1 for «مكرر», n for «مكرر (n)» or
    an ordinal word. Returns ``None`` if the label is not an article heading.
    """
    m = _ARTICLE_NO.match(normalize(label))
    if not m:
        return None
    num = int(m.group(1))
    if not m.group(2):
        return num, 0
    if m.group(3):
        return num, int(m.group(3))
    if m.group(4):
        return num, _ORDINALS[m.group(4)]
    return num, 1
