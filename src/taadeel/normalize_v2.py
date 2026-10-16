"""Normalisation v2: a pre clean step in front of the hash locked v1 (``normalize.py`` is not edited).

The synthetic Arabic stress set (``arabic_stress.py``) showed that v1 keeps invisible format
characters, so an article heading copied from HTML or a PDF with a right to left mark fails to parse.
v2 removes or maps, before calling v1:

* bidi and zero width format characters: U+200B to U+200F, U+202A to U+202E, U+2066 to U+2069,
  U+061C (Arabic letter mark), U+FEFF (byte order mark), U+00AD (soft hyphen);
* Persian letter forms often typed in Arabic text: U+06CC (Farsi yeh) to U+064A, U+06A9 (keheh) to U+0643;
* ornate parentheses U+FD3E and U+FD3F to ASCII parentheses (direction follows the logical order);
* in article labels, a dash between the number and «مكرر» ("المادة 5 - مكرر").

Arabic text is primary; only the matching copy (``text_norm``) is affected, display text never is.
Status: written after the stress set exposed these gaps, so its score on that set is by construction,
not a held out measurement. Tested on SYNTHETIC strings only. Not validated on real UAE text.
Not yet wired into the parser or the store (v1 stays the default until real Arabic text can be checked).
"""
from __future__ import annotations

import re

from .normalize import normalize as _v1_normalize
from .normalize import parse_article_label as _v1_label

_FORMAT = re.compile("[​-‏‪-‮⁦-⁩؜﻿­]")
_MAP = str.maketrans({"ی": "ي", "ک": "ك", "﴾": "(", "﴿": ")"})
_DASH_BIS = re.compile(r"(\d)\s*[-‐-―ـ]+\s*(مكرر)")


def preclean(text: str) -> str:
    return _FORMAT.sub("", text).translate(_MAP)


def normalize(text: str, **kw) -> str:
    return _v1_normalize(preclean(text), **kw)


def parse_article_label(label: str) -> tuple[int, int] | None:
    t = preclean(label)
    r = _v1_label(t)
    if r is None:
        r = _v1_label(_DASH_BIS.sub(r"\1 \2", _v1_normalize(t)))
    return r
