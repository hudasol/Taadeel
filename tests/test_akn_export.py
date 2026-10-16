"""Akoma Ntoso compatible export. Schema validation runs only when TAADEEL_AKN_SCHEMA_DIR points to the
OASIS schema files (not committed; see src/taadeel/akn_export.py)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from lxml import etree

from taadeel.akn_export import AKN, TDL, load_schema, samples, to_akn, validate


def test_export_is_well_formed_and_keeps_provenance():
    for label, e in samples()[:3]:
        doc = etree.fromstring(to_akn(e).encode("utf-8"))
        prov = doc.find(f".//{{{TDL}}}provenance")
        assert prov is not None and prov.get(f"{{{TDL}}}sourceUrl") == e.source_url, label
        assert prov.get(f"{{{TDL}}}synthetic") == str(e.synthetic).lower()
        assert len(doc.findall(f".//{{{AKN}}}article")) == len(e.articles())


def test_synthetic_export_uses_no_real_country_code():
    e = samples()[0][1]
    assert 'FRBRcountry value="zz"' in to_akn(e)


@pytest.mark.skipif(not os.environ.get("TAADEEL_AKN_SCHEMA_DIR"), reason="OASIS schema not present")
def test_samples_validate_and_broken_document_is_rejected():
    schema = load_schema(Path(os.environ["TAADEEL_AKN_SCHEMA_DIR"]))
    xml = to_akn(samples()[0][1])
    assert validate(xml, schema) == []
    assert validate(xml.replace("<body>", "<body><sectionx/>", 1), schema)
