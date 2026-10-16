"""Export an Expression in an Akoma Ntoso 3.0 compatible form and validate it against the OASIS schema.

Status: "AKN compatible", not "AKN compliant". The export covers the identification block (FRBR
Work, Expression, Manifestation), the body hierarchy (chapters, articles, clauses) and Taadeel's
provenance (source URL, retrieval date, synthetic flag) under ``<proprietary>``. It does not
produce lifecycle events, passive or active modifications, temporal groups or references to
amending acts, and the URIs are Taadeel's own, not an official naming convention. Validation
against the XSD checks structure only, not the meaning of the content.

Schema: OASIS LegalDocML, Akoma Ntoso Version 1.0 Part 2, ``akomantoso30.xsd`` and its import
``xml.xsd`` (CC BY 4.0, OASIS Open 2018). They are not committed; ``python -m taadeel.akn_export
validate SCHEMA_DIR`` checks their sha256 against the values recorded below and in
docs/DATA_SOURCES.md, then writes results/akn_validation.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .model import Expression, Provision

AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
TDL = "https://github.com/hudasol/Taadeel/ns/provenance"
SCHEMA_SHA256 = {
    "akomantoso30.xsd": "6f61fe84cbb6f8cb0e8418cd67b74a63da9990e6573b5a3491f623184f45c4fd",
    "xml.xsd": "61960fb3131e38022caad5360e2f33a3382578ab3c80cd58bd74320ede61b20c",
}


def _date(e: Expression) -> str:
    return (e.valid_from or e.issue_date).isoformat() if (e.valid_from or e.issue_date) else e.retrieved_at[:10]


def _country(e: Expression) -> str:
    if e.synthetic:
        return "zz"          # user assigned code: not a country
    return "gb" if e.work_id.startswith("uk/") else "ae"


def _uri(e: Expression) -> tuple[str, str, str]:
    work = "/akn/" + _country(e) + "/act/" + e.work_id.replace("/", "-")
    expr = f"{work}/{e.language}@{_date(e)}"
    return work, expr, expr + "/main.xml"


def _p(text: str) -> str:
    lines = [ln for ln in text.split("\n") if ln.strip()] or [""]
    return "".join(f"<p>{escape(ln)}</p>" for ln in lines)


def _eid(p: Provision) -> str:
    return p.eid.replace("~", "_")


def _article(p: Provision, children: list[Provision]) -> str:
    num = "" if p.number is None else f"<num>{p.number}{'' if not p.bis else f' bis {p.bis}'}</num>"
    head = f"<heading>{escape(p.heading)}</heading>" if p.heading and p.heading != p.text else ""
    clauses = [c for c in children if c.kind == "clause"]
    if clauses:   # clause lines are also part of the article text; export them as the hierarchy
        body = "".join(f'<paragraph eId="{_eid(p)}__para_{i + 1}"><num>{c.number}</num><content>{_p(c.text)}</content></paragraph>'
                       for i, c in enumerate(clauses))
    else:
        body = f"<content>{_p(p.text)}</content>"
    return f'<article eId="{_eid(p)}">{num}{head}{body}</article>'


def to_akn(e: Expression) -> str:
    work, expr, mani = _uri(e)
    d = _date(e)
    kids: dict[str | None, list[Provision]] = {}
    for p in e.provisions:
        kids.setdefault(p.parent, []).append(p)

    def render(parent: str | None) -> str:
        out = []
        for p in kids.get(parent, []):
            if p.kind in ("part", "chapter"):
                tag = "part" if p.kind == "part" else "chapter"
                inner = render(p.eid) or "<article eId=\"" + _eid(p) + "__empty\"><content><p/></content></article>"
                out.append(f'<{tag} eId="{_eid(p)}"><heading>{escape(p.heading or p.text)}</heading>{inner}</{tag}>')
            elif p.kind == "article":
                out.append(_article(p, kids.get(p.eid, [])))
        return "".join(out)

    body = render(None) or '<article eId="empty"><content><p/></content></article>'
    name = "synthetic" if e.synthetic else "act"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<akomaNtoso xmlns="{AKN}" xmlns:tdl="{TDL}">'
        f'<act name="{name}"><meta>'
        f'<identification source="#taadeel">'
        f'<FRBRWork><FRBRthis value={quoteattr(work + "/!main")}/><FRBRuri value={quoteattr(work)}/>'
        f'<FRBRdate date="{d}" name="version"/><FRBRauthor href="#publisher"/><FRBRcountry value="{_country(e)}"/></FRBRWork>'
        f'<FRBRExpression><FRBRthis value={quoteattr(expr + "/!main")}/><FRBRuri value={quoteattr(expr)}/>'
        f'<FRBRdate date="{d}" name="version"/><FRBRauthor href="#publisher"/><FRBRlanguage language="{e.language}"/></FRBRExpression>'
        f'<FRBRManifestation><FRBRthis value={quoteattr(mani)}/><FRBRuri value={quoteattr(mani)}/>'
        f'<FRBRdate date="{e.retrieved_at[:10]}" name="retrieval"/><FRBRauthor href="#taadeel"/></FRBRManifestation>'
        f'</identification>'
        f'<references source="#taadeel"><TLCOrganization eId="taadeel" href="/ontology/organization/taadeel" showAs="Taadeel"/>'
        f'<TLCOrganization eId="publisher" href="/ontology/organization/publisher" showAs="Original publisher (see source URL)"/></references>'
        f'<proprietary source="#taadeel"><tdl:provenance tdl:sourceUrl={quoteattr(e.source_url)} tdl:retrievedAt={quoteattr(e.retrieved_at)} '
        f'tdl:synthetic="{str(e.synthetic).lower()}" tdl:effectiveStatus="{e.effective_status}" tdl:notLegalAdvice="true"/></proprietary>'
        f'</meta><body>{body}</body></act></akomaNtoso>'
    )


def load_schema(schema_dir: Path):
    from lxml import etree

    for f, h in SCHEMA_SHA256.items():
        got = hashlib.sha256((schema_dir / f).read_bytes()).hexdigest()
        if got != h:
            raise SystemExit(f"{f}: sha256 {got} does not match the recorded {h}")
    return etree.XMLSchema(etree.parse(str(schema_dir / "akomantoso30.xsd")))


def validate(xml: str, schema) -> list[str]:
    from lxml import etree

    doc = etree.fromstring(xml.encode("utf-8"))
    return [] if schema.validate(doc) else [f"line {e.line}: {e.message}" for e in schema.error_log][:20]


def samples() -> list[tuple[str, Expression]]:
    import gzip

    from .synthetic import make_pair
    from .uk_corpus import OUT, _expression

    p = make_pair(7, n=12, n_replace=2, n_repeal=1, n_insert=2, n_clarify=1, bis_inserts=1)
    out = [("synthetic demo, version a", p.a), ("synthetic demo, version b (bis article)", p.b)]
    from .parse import parse_structure
    from .synthetic import SYNTHETIC_URL
    raw = "الباب الأول\nالفصل الأول\nالمادة (1)\n1- نص اصطناعي أول.\n2- نص اصطناعي ثان.\nالمادة (1) مكرر\nنص اصطناعي.\nالفصل الثاني\nالمادة (2)\nنص اصطناعي."
    e = Expression(work_id="synthetic/law/akn", expression_id="akn-structured", source_url=SYNTHETIC_URL,
                   retrieved_at="2026-10-16", synthetic=True)
    out.append(("synthetic structured text (parts, chapters, clauses)", parse_structure(raw, e)))
    if OUT.exists():
        seen = set()
        with gzip.open(OUT, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["act"] not in seen:
                    seen.add(r["act"])
                    out.append((f"UK {r['act']} @ {r['date']} (English, OGL v3.0)", _expression(r)))
    return out


def run(schema_dir: Path) -> dict:
    schema = load_schema(schema_dir)
    rows = []
    for label, e in samples():
        errs = validate(to_akn(e), schema)
        rows.append({"sample": label, "valid": not errs, "errors": errs})
    # negative controls: deliberately broken documents must be rejected, or the check proves nothing
    good = to_akn(samples()[0][1])
    broken = {
        "identification without FRBRWork": good.replace(good[good.index("<FRBRWork>"):good.index("</FRBRWork>") + 11], ""),
        "article text outside content": good.replace("<content><p>", "<p>", 1).replace("</p></content>", "</p>", 1),
        "unknown element in body": good.replace("<body>", "<body><sectionx/>", 1),
    }
    controls = [{"control": k, "rejected": bool(validate(v, schema))} for k, v in broken.items()]
    out = {"schema": "OASIS Akoma Ntoso 1.0 akomantoso30.xsd (CC BY 4.0)", "schema_sha256": SCHEMA_SHA256,
           "negative_controls": controls, "negative_controls_rejected": sum(c["rejected"] for c in controls),
           "claim": "AKN compatible export (structure validated); not AKN compliant",
           "valid": sum(r["valid"] for r in rows), "total": len(rows), "samples": rows}
    from .heldout import RESULTS
    (RESULTS / "akn_validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "validate":
        r = run(Path(sys.argv[2]))
        print(json.dumps({k: r[k] for k in ("valid", "total")}), [(s["sample"], s["errors"][:2]) for s in r["samples"] if not s["valid"]])
    else:
        raise SystemExit("usage: python -m taadeel.akn_export validate SCHEMA_DIR")
