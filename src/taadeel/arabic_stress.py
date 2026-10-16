"""SYNTHETIC Arabic stress set for normalisation and article label parsing (v1 against v2).

Every string here was written for testing. None is quoted from legislation and none carries legal
meaning; article numbers are arbitrary. It measures how the code treats orthographic variation
(diacritics, tatweel, alef and yaa variants, Arabic Indic and Persian digits, «مكرر», mixed Arabic and
English, invisible format characters). It says nothing about accuracy on real UAE text, which remains
unvalidated because no permitted real Arabic legal text is available.

v2 was written after these cases exposed the v1 gaps, so its score here is by construction.
``python -m taadeel.arabic_stress`` writes results/arabic_stress.json.
"""
from __future__ import annotations

import json
import sys

from . import normalize as v1
from . import normalize_v2 as v2
from .heldout import RESULTS

LABEL = "SYNTHETIC test strings, not legislation"

# (id, group, input, expected normalised form or None, expected article label or None)
NORM_CASES = [
    ("diacritics", "diacritics", "يَجُوزُ لِلْجِهَةِ", "يجوز للجهة"),
    ("shadda_tanween", "diacritics", "مكرَّراً", "مكررا"),
    ("superscript_alef", "diacritics", "هٰذا", "هذا"),
    ("tatweel", "tatweel", "الترخيــــص", "الترخيص"),
    ("alef_hamza", "alef", "أحكام إصدار آخر", "احكام اصدار اخر"),
    ("alef_wasla", "alef", "ٱلقرار", "القرار"),
    ("alef_maqsura", "yaa", "على", "علي"),
    ("farsi_yeh", "yaa", "علی", "علي"),
    ("keheh", "letters", "کل", "كل"),
    ("indic_digits", "digits", "لسنة ٢٠٢١", "لسنة 2021"),
    ("persian_digits", "digits", "لسنة ۲۰۲۱", "لسنة 2021"),
    ("presentation_forms", "nfkc", "ﺍﻟﻤﺎﺩﺓ", "المادة"),
    ("lam_alef_ligature", "nfkc", "ﻻ يجوز", "لا يجوز"),
    ("arabic_punct", "punctuation", "أولاً، ثانياً؛", "اولا, ثانيا;"),
    ("mixed_ar_en", "mixed", "أحكام Federal Decree-Law No. 5 لسنة ٢٠٢١", "احكام Federal Decree-Law No. 5 لسنة 2021"),
    ("rlm_inside", "format", "الجهة‏ المختصة", "الجهة المختصة"),
    ("zwnj_inside_word", "format", "المخ‌تصة", "المختصة"),
    ("bom_start", "format", "﻿القرار", "القرار"),
    ("alm_mark", "format", "القرار؜ الوزاري", "القرار الوزاري"),
    ("nbsp", "format", "الجهة المختصة", "الجهة المختصة"),
]

LABEL_CASES = [
    ("plain", "label", "المادة (5)", (5, 0)),
    ("no_al", "label", "مادة ٥", (5, 0)),
    ("indic_bis_n", "label", "المادة (١٢) مكرر (٢)", (12, 2)),
    ("ordinal_bis", "label", "المادة 5 مكرراً ثالثاً", (5, 3)),
    ("tatweel_label", "label", "المـــادة (٧)", (7, 0)),
    ("diacritic_label", "label", "المَادَّةُ (٥)", (5, 0)),
    ("persian_digit_label", "label", "مادة ۷", (7, 0)),
    ("spaces_in_paren", "label", "المادة ( 5 )", (5, 0)),
    ("fullwidth_paren", "label", "المادة （5）", (5, 0)),
    ("rlm_label", "format", "المادة‏ (5)", (5, 0)),
    ("lrm_digits", "format", "المادة (‎5‎)", (5, 0)),
    ("bom_label", "format", "﻿المادة (5)", (5, 0)),
    ("alm_label", "format", "المادة؜ (9)", (9, 0)),
    ("ornate_paren", "label", "المادة ﴾5﴿", (5, 0)),
    ("dash_bis", "label", "المادة 5 - مكرر", (5, 1)),
    ("english_label", "mixed", "Article 5 bis", None),
    ("chapter_not_article", "label", "الفصل الأول", None),
]


def run() -> dict:
    out = {"data": LABEL, "normalise": [], "labels": [], "summary": {}}
    for cid, grp, s, exp in NORM_CASES:
        out["normalise"].append({"id": cid, "group": grp, "v1_ok": v1.normalize(s) == exp, "v2_ok": v2.normalize(s) == exp,
                                 "v1_idempotent": v1.normalize(v1.normalize(s)) == v1.normalize(s)})
    for cid, grp, s, exp in LABEL_CASES:
        r1, r2 = v1.parse_article_label(s), v2.parse_article_label(s)
        out["labels"].append({"id": cid, "group": grp, "expected": exp, "v1": r1, "v2": r2,
                              "v1_ok": (tuple(r1) if r1 else None) == exp, "v2_ok": (tuple(r2) if r2 else None) == exp})
    for k in ("normalise", "labels"):
        rows = out[k]
        out["summary"][k] = {"cases": len(rows), "v1_ok": sum(r["v1_ok"] for r in rows), "v2_ok": sum(r["v2_ok"] for r in rows)}
    return out


if __name__ == "__main__":
    r = run()
    (RESULTS / "arabic_stress.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(r["summary"]))
