"""Tests for taadeel.amend_en.

All sentences are INVENTED short examples written in UK drafting style. They are not
copied from any real Act, and this file does not validate the parser against real text
(that is done separately against recorded effects).
"""
from taadeel.amend_en import parse

INVENTED = "Invented sentences, not real Act text."


def test_substitute():
    t = "For section 3 substitute: Example duty applies."
    [a] = parse(t)
    assert (a.op, a.target, a.bis, a.lang, a.pattern_id) == ("substitute", "3", 0, "en", "en.for.substitute")
    assert a.new_text == "Example duty applies."
    assert t[a.span[0]:a.span[1]].lower().startswith("for section 3 substitute")


def test_substitute_lettered_and_em_dash():
    [a] = parse("In the Example Act, for section 3ZA substitute\u2014 \u201cNew rule.\u201d")
    assert a.target == "3ZA" and a.new_text == "\u201cNew rule.\u201d"


def test_omit_single_and_list():
    [a] = parse("Omit section 5.")
    assert (a.op, a.target, a.new_text) == ("repeal", "5", None)
    recs = parse("Omit sections 5, 6 and 7A.")
    assert [r.target for r in recs] == ["5", "6", "7A"]


def test_insert_with_stated_number():
    [a] = parse("After section 3 insert: 3A Example power. The body is invented.")
    assert (a.op, a.target, a.anchor, a.pattern_id) == ("insert", "3A", "3", "en.after.insert")
    assert a.new_text.startswith("3A Example power") and a.confidence >= 0.85


def test_insert_without_number_is_low_confidence():
    [a] = parse("After section 3 insert a new definition.")
    assert (a.target, a.anchor) == ("3", "3") and a.confidence <= 0.5


def test_repealed():
    [a] = parse("Section 4 is repealed.")
    assert (a.op, a.target, a.pattern_id) == ("repeal", "4", "en.repealed.section")
    assert [r.target for r in parse("sections 4 and 5 are repealed")] == ["4", "5"]


def test_multiple_instructions_in_order():
    recs = parse("Omit section 2. For section 3 substitute: Text A. After section 4 insert: 4A Text B.")
    assert [(r.op, r.target) for r in recs] == [("repeal", "2"), ("substitute", "3"), ("insert", "4A")]
    assert recs[1].new_text == "Text A."


def test_negatives():
    for t in (
        "",
        "Section 4 applies to every example body.",
        "Section 4 is amended as follows.",
        "Omit subsection (5).",
        "For subsection (2) substitute: invented words.",
        "After subsection (2) insert: invented words.",
        "The subsection 4 is repealed by nothing here.",
        "This Act may be cited as the Example Act.",
    ):
        assert parse(t) == [], t
