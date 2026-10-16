"""SYNTHETIC Arabic stress cases (test strings, not legislation): v1 gaps are recorded, v2 must pass."""
from __future__ import annotations

import pytest

from taadeel import normalize as v1
from taadeel import normalize_v2 as v2
from taadeel.arabic_stress import LABEL_CASES, NORM_CASES

V1_KNOWN_GAPS = {"farsi_yeh", "keheh", "rlm_inside", "zwnj_inside_word", "bom_start", "alm_mark",
                 "rlm_label", "lrm_digits", "bom_label", "alm_label", "ornate_paren", "dash_bis"}


@pytest.mark.parametrize("cid,group,text,expected", NORM_CASES, ids=[c[0] for c in NORM_CASES])
def test_normalise_v2(cid, group, text, expected):
    assert v2.normalize(text) == expected
    assert v2.normalize(v2.normalize(text)) == v2.normalize(text)


@pytest.mark.parametrize("cid,group,text,expected", LABEL_CASES, ids=[c[0] for c in LABEL_CASES])
def test_labels_v2(cid, group, text, expected):
    assert v2.parse_article_label(text) == expected


@pytest.mark.parametrize("cid,group,text,expected", NORM_CASES + LABEL_CASES, ids=[c[0] for c in NORM_CASES + LABEL_CASES])
def test_v1_gaps_are_exactly_the_recorded_ones(cid, group, text, expected):
    fn = v1.parse_article_label if (cid, group, text, expected) in LABEL_CASES else v1.normalize
    assert (fn(text) == expected) == (cid not in V1_KNOWN_GAPS)


def test_v2_leaves_display_text_rules_unchanged_for_plain_text():
    s = "يلتزم المرخص له بتقديم التقرير خلال ثلاثين يوما"
    assert v2.normalize(s) == v1.normalize(s)
