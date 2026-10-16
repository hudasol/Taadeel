# Taadeel plan

Milestones, each tagged `m1` to `m9` with tests. Reversible decisions are noted here. Status lines below were updated on 2026-10-16 to match the code under `src/taadeel/`; the earlier status (2026-10-11) is kept in the history notes at the end.

| ID | Milestone | Exit criteria | Status |
|---|---|---|---|
| P0 | Research docs | RESEARCH, DATA_SOURCES, ARCHITECTURE written | done |
| P1 | Repo, plan, README | pushed to GitHub with About + topics | pushed to GitHub (branch `feat/validation-and-amendments`) |
| M1 | Ingestion | permission gated, robots aware, rate limited, hashed snapshots, resumable | done (tests); no real UAE host permitted (the portal returned HTTP 403 on robots.txt; recorded, not worked around); the UK legislation.gov.uk adapter is built for engine validation only |
| M2 | Parsing | Arabic normalisation; structure extraction law, part, chapter, article, clause; schema validation | done for plain text; PDF extractor built and tested on synthetic PDFs only; no real PDF or HTML from a UAE source |
| M3 | Alignment | renumbering robust matching with confidence and an "unaligned" bucket | done (v1, hash locked; synthetic validated) |
| M4 | Diffing | article and word level diffs; classification; amending instrument linked | done; English amendment pattern module built (measured on a small UK sample); Arabic amendment lexicon built but unvalidated (invented samples only) |
| M5 | Temporal | point in time reconstruction; uncertain effective dates flagged | done (unit tested) |
| M6 | Validation | gold set, accuracy/P/R, adversarial tests, honest report | partial: synthetic and UK English validation only; no real Arabic validation and no gold set of real UAE laws |
| M7 | API + dataset | read only FastAPI; versioned release + data card | done: SQLite storage with FTS5, Parquet export, search API, FastAPI API; no real UAE data loaded; no Akoma Ntoso export |
| M8 | Interface | RTL first bilingual UI with timeline slider, redline, as of view | done as an RTL bilingual web page; search is provided by the search API |
| M9 | Deploy | live URL, CI badge, reproducible build | partial: Dockerfile and render.yaml written; a live demo runs on the Render free tier from the branch `feat/validation-and-amendments` |

## Decisions (reversible)

* Python 3.13, stdlib first core, FastAPI, static front end (no build step), pytest, GitHub Actions. Storage is SQLite with FTS5 and a Parquet export (see `docs/STORAGE.md`).
* Real data work gated by `sources.toml`; default is link only.
* Synthetic fixtures are generated in code (`src/taadeel/synthetic.py`), labelled, and schema enforced out of real data views. `data/synthetic/` is an empty placeholder.

## Not done

* Any real UAE law (no permission; portal returns HTTP 403 on robots.txt, recorded and not worked around).
* Any real Arabic validation, and a gold set of real UAE laws.
* Akoma Ntoso export.

## History

* 2026-10-11 status (superseded): HTML and PDF extraction, amendment parser, search, SQLite and Parquet storage, deployment and the GitHub push were listed as not built or not done. They have since been built or completed as described in the table above.
