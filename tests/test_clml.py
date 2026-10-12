"""CLML parsing tests. Effect texts are footnote wordings as published on legislation.gov.uk
(Open Government Licence v3.0; Contains public sector information licensed under the Open Government Licence v3.0)."""
from datetime import date

from lxml import etree

from taadeel import clml

XML = """<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation" RestrictExtent="E+W+S+N.I.">
<Primary><Body>
<Pblock><P1group><Title>Unauthorised access</Title>
<P1 id="section-1" IdURI="http://www.legislation.gov.uk/id/ukpga/1990/18/section/1"><Pnumber>1</Pnumber>
<P1para><P2><Pnumber>1</Pnumber><P2para><Text>A person is guilty if he secures access
<Addition CommentaryRef="c1">, or to enable any such access to be secured</Addition>
<Addition CommentaryRef="c2" RestrictExtent="S"> in Scotland only wording</Addition>.</Text></P2para></P2></P1para></P1></P1group>
<P1group><Title>Old</Title><P1 id="section-15"><Pnumber>15</Pnumber><P1para><Text><CommentaryRef Ref="c3"/>. . . . . . . . . .</Text></P1para></P1></P1group>
<P1group><Title>New</Title><P1 id="section-3ZA"><Pnumber>3ZA</Pnumber><P1para><Text>An act causing serious damage.</Text></P1para></P1></P1group>
</Pblock></Body></Primary>
<Commentaries>
<Commentary id="c1" Type="F"><Para><Text>Words in s. 1(1)(a) inserted (1.10.2007) by Police and Justice Act 2006 (c. 48), ss. 35(2)(a), 53 (with s. 38(1)); S.S.I. 2007/434</Text></Para></Commentary>
<Commentary id="c2" Type="F"><Para><Text>Words in s. 1(1)(b) inserted (S.) (1.10.2007) by Police and Justice Act 2006 (c. 48), ss. 35(2)(b)</Text></Para></Commentary>
<Commentary id="c3" Type="F"><Para><Text>S. 15 repealed (15.1.2007) by Fraud Act 2006 (c. 35), ss. 14(1)(3), 15(1), Sch. 1 para. 1(a)(i)</Text></Para></Commentary>
</Commentaries></Legislation>"""


def root():
    return etree.fromstring(XML.encode())


def test_sections_ew_view_placeholder_and_suffix():
    secs = {s.eid: s for s in clml.parse_sections(root())}
    assert set(secs) == {"section-1", "section-15", "section-3ZA"}
    assert secs["section-15"].placeholder and secs["section-15"].text == ""
    assert secs["section-3ZA"].number == 3 and secs["section-3ZA"].suffix == "ZA"
    t = secs["section-1"].text
    assert "or to enable any such access" in t and "Scotland only" not in t   # S.-only span dropped
    assert t.startswith("Unauthorised access")


def test_effects_anchor_kind_date_and_affecting():
    eff = {e.cid: e for e in clml.parse_effects(root())}
    assert eff["c1"].sections == ["section-1"] and eff["c1"].kind == "text_modified"
    assert eff["c1"].status == "ok" and eff["c1"].date == date(2007, 10, 1)
    assert (eff["c1"].affecting_title, eff["c1"].affecting_year, eff["c1"].affecting_chapter) == ("Police and Justice Act 2006", 2006, 48)
    assert eff["c1"].affecting_sections[:2] == ["35", "53"]
    assert eff["c2"].status == "extent_excluded"
    assert eff["c3"].kind == "section_repealed" and eff["c3"].sections == ["section-15"] and eff["c3"].date == date(2007, 1, 15)


def test_date_variants():
    f = clml.parse_effect_text
    ok = f("Words in s. 9(2)(a) substituted (1.10.2007 with application as mentioned in Sch. 4 para. 111(6) of the amending S.I.) by virtue of The Companies Act 2006 (Commencement No. 3)")
    assert ok[1] == "ok" and ok[2] == date(2007, 10, 1)
    assert f("Words in s. 6(2)(a) substituted (7.2.2023 at 12.00 p.m.) by The Judicial Review and Courts Act 2022 (Magistrates’ Court)")[2] == date(2023, 2, 7)
    # "d1 for S. and d2 otherwise": the meaning of "S." is not in the retrieved terms, so it is not guessed
    assert f("S. 1(3) substituted (1.10.2007 for S. and 1.10.2008 otherwise) by Police and Justice Act 2006 (c. 48), ss. 35(3)")[1] == "ambiguous_date"
    assert f("S. 4 substituted (E.W.) (1.10.2008) by X Act 2006 (c. 1), s. 1")[2] == date(2008, 10, 1)
    assert f("Words repealed (E.W.) by Criminal Attempts Act 1981 (c. 47, SIF 39:1), Sch. Pt. I")[1] == "undated"
    assert f("S. 3 inserted (prosp.) by Some Act 2020 (c. 3), s. 1")[1] == "prospective"
    assert f("S. 3 inserted (N.I.) (1.1.2010) by Some Act 2009 (c. 3), s. 1")[1] == "extent_excluded"
    assert f("S. 3 inserted (1.10.2007 for certain purposes and 1.4.2008 for all other purposes) by Some Act 2006 (c. 3), s. 1")[1] == "ambiguous_date"


def test_kinds():
    k = lambda t: clml.parse_effect_text(t + " (1.1.2000) by A Act 1999 (c. 1), s. 1")[0]
    assert k("S. 3ZA inserted") == "section_inserted"
    assert k("Ss. 28A-28C inserted") == "section_inserted"
    assert k("S. 12(2)-(4) inserted") == "text_modified"
    assert k("S. 15 repealed") == "section_repealed" and k("S. 5 omitted") == "section_repealed"
    assert k("S. 7 substituted") == "section_substituted"
    assert k("Words in s. 1(1)(a) inserted") == "text_modified"
    assert k("S. 3 heading: words substituted") == "text_modified"
    assert k("Act applied") == "other"


def test_subsection_effect_is_not_a_whole_section_effect():
    k = clml.parse_effect_text("S. 14(2) repealed (1.4.2001) by S.I. 2001/1216, art. 2(b)")[0]
    assert k == "text_modified"
    k2 = clml.parse_effect_text("S. 14 repealed (1.4.2001) by S.I. 2001/1216, art. 2(b)")[0]
    assert k2 == "section_repealed"
    k3 = clml.parse_effect_text("S. 3 (E.W.) substituted (1.10.2008) by Some Act 2006 (c. 48), s. 36")[0]
    assert k3 == "section_substituted"


def test_extent_restricted_duplicate_section_is_dropped():
    xml = (
        '<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation"><Body>'
        '<P1group RestrictExtent="E+W"><Title>T</Title><P1 id="section-14"><Pnumber>14</Pnumber>'
        '<P1para><Text>England text here.</Text></P1para></P1></P1group>'
        '<P1group RestrictExtent="N.I."><Title>T</Title><P1 id="section-14"><Pnumber>14</Pnumber>'
        '<P1para><Text>Northern Ireland text here.</Text></P1para></P1></P1group>'
        '</Body></Legislation>')
    from lxml import etree
    secs = clml.parse_sections(etree.fromstring(xml.encode()))
    assert [s.eid for s in secs] == ["section-14"] and "England" in secs[0].text
