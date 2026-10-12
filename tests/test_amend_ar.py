"""Tests for taadeel.amend_ar.

Every sample below is INVENTED synthetic Arabic written to follow the phrasing patterns
listed in research/arabic_sources.md. None of it is real UAE (or any other) legislative
text, and passing these tests says nothing about accuracy on real text.
"""
from taadeel.amend_ar import has_general_repeal, parse
from taadeel.normalize import normalize

SYNTHETIC = "Invented sample sentences, not real UAE text. Do not treat as legal text."

REPLACE = "يُستبدل بنص المادة ٣٨ من القانون المثال رقم ١ لسنة 2020 النص الآتي: يجوز للجهة المختصة اصدار قرار."
REPLACE_PARA = "يستبدل بنص المادة (25) فقرة (2) من القانون المثال النص التالي: نص فقرة مخترع."
REWORD = "يعدل نص المادة (7) من القانون المثال ليصبح على النحو الآتي: نص معدل مخترع."
INSERT = "تضاف مادة جديدة برقم ٩ مكررا الى القانون المثال نصها الآتي: نص مادة مخترع."
REPEAL = "تلغى المواد ٣٤٨ و 349 و350 من القانون المثال."


def test_synthetic_label():
    assert "not real" in SYNTHETIC and "Invented" in SYNTHETIC


def test_replace_arabic_indic_digits_and_text():
    [a] = parse(REPLACE)
    assert (a.op, a.target, a.bis, a.pattern_id) == ("substitute", "38", 0, "ar.replace.article")
    assert a.new_text.startswith("يجوز للجهة") and a.confidence >= 0.9
    s, e = a.span
    assert normalize(REPLACE)[s:e].startswith("يستبدل بنص المادة 38")


def test_replace_variants_without_ba_and_feminine():
    for txt in ("تستبدل نص المادة 5 من القانون المثال النص التالي: س",
                "يستبدل بنص المادة 5 من القانون المثال النص الاتي: س"):
        [a] = parse(txt)
        assert (a.op, a.target, a.new_text) == ("substitute", "5", "س")


def test_replace_paragraph():
    [a] = parse(REPLACE_PARA)
    assert (a.target, a.paragraph, a.pattern_id) == ("25", "2", "ar.replace.paragraph")


def test_reword():
    [a] = parse(REWORD)
    assert (a.op, a.target, a.pattern_id) == ("substitute", "7", "ar.amend.reword")
    assert a.new_text.startswith("نص معدل")


def test_insert_makarrar_with_text():
    [a] = parse(INSERT)
    assert (a.op, a.target, a.bis, a.pattern_id) == ("insert", "9", 1, "ar.insert.article")
    assert a.new_text.startswith("نص مادة")


def test_insert_bis_forms():
    cases = {
        "تضاف مادة جديدة رقم 39 مكرر للقانون المثال": 1,
        "تضاف مادة جديدة رقم 39 مكرر 2 للقانون المثال": 2,
        "تضاف مادة جديدة رقم 39 مكرر (3) للقانون المثال": 3,
        "تضاف مادة جديدة رقم 39 مكررا ثانيا للقانون المثال": 2,
        "تضاف مادة جديدة رقم 39 مكررة للقانون المثال": 1,
        "تضاف مادة جديدة رقم 39 للقانون المثال": 0,
    }
    for txt, bis in cases.items():
        [a] = parse(txt)
        assert (a.target, a.bis, a.new_text) == ("39", bis, None), txt


def test_repeal_list_mixed_digits():
    recs = parse(REPEAL)
    assert [(r.op, r.target) for r in recs] == [("repeal", "348"), ("repeal", "349"), ("repeal", "350")]
    assert all(r.new_text is None and r.pattern_id == "ar.repeal.list" for r in recs)


def test_repeal_single_with_bis_and_ahkam():
    [a] = parse("تلغي احكام المادة 12 مكرر من القانون المثال")
    assert (a.target, a.bis) == ("12", 1)
    [b] = parse("ويلغى المادة 4")
    assert b.target == "4"


def test_tunisian_unit_has_lower_confidence():
    [a] = parse("تلغى احكام الفصل 2")
    [b] = parse("تلغى احكام المادة 2")
    assert a.confidence < b.confidence


def test_multiple_instructions_split_text():
    recs = parse(REPLACE + " " + INSERT)
    assert [r.op for r in recs] == ["substitute", "insert"]
    assert "تضاف" not in recs[0].new_text


def test_diacritics_and_tatweel_ignored():
    [a] = parse("يُسْتَبْدَلُ بِنَصِّ المَادَّةِ 3 مِنَ القَانُونِ المثال النَّصُّ الآتِي: س")
    assert a.target == "3"


# negative cases
def test_negatives():
    for txt in (
        "",
        "تنشر هذه الوثيقة في الجريدة الرسمية ويعمل بها من اليوم التالي لتاريخ نشرها",
        "المادة 5 من القانون المثال تنص على احكام عامة",          # mentions an article, no verb
        "تضاف مادة جديدة الى القانون المثال",                       # no number
        "يستبدل بنص المادة من القانون المثال النص الآتي",           # no number
        "تلغى احكام هذا القانون",                                    # no named target
        "يستعاض عن المادة 5 بالنص الآتي",                           # phrasing not in the sources
        "يجوز استبدال المادة 5 بقرار",                               # noun, not the instruction
        "لا يضاف شيء الى المادة 5",
    ):
        assert parse(txt) == [], txt


def test_general_repeal_is_flagged_not_parsed():
    t = "يلغى كل حكم يخالف احكام هذا القانون"
    assert parse(t) == [] and has_general_repeal(t)
    assert not has_general_repeal("تلغى المادة 5")
