from taadeel.normalize import normalize, parse_article_label


def test_diacritics_and_tatweel_removed():
    assert normalize("الكِتَــاب") == "الكتاب"


def test_alef_and_yaa_variants_unified():
    assert normalize("أحمد إبراهيم آمن") == "احمد ابراهيم امن"
    assert normalize("على") == normalize("علي")


def test_arabic_indic_and_persian_digits():
    assert normalize("المادة ٣٣ و ۱۲") == "المادة 33 و 12"


def test_taa_marbuta_fold_is_opt_in():
    assert normalize("المادة") == "المادة"
    assert normalize("المادة", fold_taa_marbuta=True) == "الماده"


def test_presentation_forms_nfkc():
    assert normalize("ﺍﻟﻣﺎﺩﺓ") == "المادة"


def test_whitespace_collapsed():
    assert normalize("  المادة   (5)\n") == "المادة (5)"


def test_article_labels():
    assert parse_article_label("المادة (5)") == (5, 0)
    assert parse_article_label("مادة ٥") == (5, 0)
    assert parse_article_label("المادة (5) مكرر") == (5, 1)
    assert parse_article_label("المادة (5) مكرر (2)") == (5, 2)
    assert parse_article_label("المادة 5 مكررًا ثانيًا") == (5, 2)
    assert parse_article_label("الفصل الأول") is None
