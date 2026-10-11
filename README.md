# Taadeel (تعديل) — UAE Legislation Change Tracker

> **Research and navigation tool. Not legal advice.**
> Taadeel does not state the law. For interpretation and application, the official Arabic text published by the competent UAE authority prevails. Every provision shown links to its official source with a retrieval date. Verify against the official source before relying on anything here.

**Goal:** track amendments across UAE federal legislation and produce structured, article-level diffs with effective-date timelines, answering *what did this law say on date X, and what changed since?* Arabic is the primary language; English is secondary where official translations exist.

**Current state (honest):** the parsing, alignment, diffing and point-in-time engine exists and is tested on clearly labeled **synthetic** data only. **No real UAE legislation is loaded**, because no source currently permits text collection. Real-world accuracy is unmeasured. See [`docs/VALIDATION.md`](docs/VALIDATION.md).

## Status

Engine and validation harness built; real data, HTML/PDF extraction, amendment-by-reference parsing, search, and deployment are open. Milestones: [`plan.md`](plan.md). Research and design: [`docs/RESEARCH.md`](docs/RESEARCH.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Data-source stance

The official portal (uaelegislation.gov.ae) publishes no open licence and no documented API, and its amendment-history pages block automated clients. Taadeel does **not** bulk-copy portal text and does **not** circumvent bot protection. Real-data ingestion is gated on written permission; until then the engine is validated on clearly labeled **synthetic** data and the product is link-first. Details and the permission to request: [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Principles

1. No fabricated law text, citations, dates or amendments.
2. Every displayed provision links to its official source and retrieval date.
3. Synthetic test data is labeled synthetic and kept out of real-data views.
4. No generic chatbot layer: the value is parsing, alignment, diffing, temporal modeling and validation.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

Code: MIT (proposed; owner to confirm). Legislation text remains the property of its publishers.
