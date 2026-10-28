# Changelog

All notable changes are listed here. Measured results are not repeated in this file; they are generated from `results/` into [`docs/VALIDATION_UK.md`](docs/VALIDATION_UK.md) and [`docs/HELDOUT_RESULTS.md`](docs/HELDOUT_RESULTS.md).

## Unreleased (pull requests 1 and 2, not yet merged)

### Added
- Held out synthetic measurement with hash locked engine files and predictions committed before the run.
- Permission gated, robots aware, rate limited and resumable adapter for legislation.gov.uk (Open Government Licence v3.0), with a recorded fetch manifest.
- CLML parser, UK validation set, point in time evaluation and a renumbering variant.
- Amendment by reference patterns for English (measured) and Arabic (tested on invented samples only).
- PDF extraction, SQLite storage with full text search, Parquet export and search endpoints.
- Snapshot based timeline for point in time answers, with an explicit uncertain state.
- Akoma Ntoso compatible export validated against the OASIS schema.
- Alignment v2 (pre registered; version 1 remains the default).
- `taadeel` command line (`diff`, `serve`, `baselines`, `report`), `POST /api/compare`, and a page section for comparing two texts the reader supplies, in Arabic or English.
- Baselines (match by number, greedy text matching, newest snapshot) scored on the same data as the engine: [`docs/BASELINES.md`](docs/BASELINES.md).
- Limitations and plan: [`docs/ROADMAP.md`](docs/ROADMAP.md). Package metadata, a linter and coverage in CI.
- Proposal briefs for TII/ATRC, EDGE and ADEO, an evaluation card and a permission request draft in English and Arabic.

### Changed
- Web page redesigned with a pink theme, dark mode, and loading, empty and error states.
- Container runs as a non root user and is built and health checked in CI.

### Fixed
- Arabic search missed a term typed without the definite article.
- Diff view showed new text in the Before column for articles that kept their identifier.
- Subsection effects were read as whole section effects in the UK effects reader.
- Northern Ireland only duplicate sections are dropped from the England and Wales view.

## 0.1.0 (synthetic only)
- Parsing, alignment, diffing, temporal model, ingestion framework and a synthetic validation harness.
