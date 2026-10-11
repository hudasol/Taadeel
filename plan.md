# Taadeel plan

Milestones, each tagged `m1`…`m9` with tests. Reversible decisions are noted here.

| ID | Milestone | Exit criteria | Status |
|---|---|---|---|
| P0 | Research docs | RESEARCH, DATA_SOURCES, ARCHITECTURE written | done (local) |
| P1 | Repo, plan, README | pushed to GitHub with About + topics | **local only: GitHub write token returns 403** |
| M1 | Ingestion | permission-gated, robots-aware, rate-limited, hashed snapshots, resumable | done (tests; no real host permitted) |
| M2 | Parsing | Arabic normalization; structure extraction law→part→chapter→article→clause; schema validation | partial: plain text only, no HTML/PDF |
| M3 | Alignment | renumbering-robust matching with confidence and an "unaligned" bucket | done (synthetic-validated) |
| M4 | Diffing | article + word-level diffs; classification; amending instrument linked | done; no amendment parser |
| M5 | Temporal | point-in-time reconstruction; uncertain effective dates flagged | done (unit-tested) |
| M6 | Validation | gold set, accuracy/P/R, adversarial tests, honest report | partial: synthetic only, no real gold set |
| M7 | API + dataset | read-only FastAPI; versioned release + data card | done (synthetic data; JSONL) |
| M8 | Interface | RTL-first bilingual UI with timeline slider, redline, as-of view | partial: no search |
| M9 | Deploy | live URL, CI badge, reproducible build | not done: Dockerfile + CI written; needs GitHub push |

## Decisions (reversible)

* Python 3.13, stdlib-first core, SQLite for storage (single file, trivial deploy), Parquet export for the dataset, FastAPI, static front end (no build step), pytest, GitHub Actions.
* Real-data work gated by `sources.toml`; default is link-only.
* Synthetic fixtures are labeled and live under `data/synthetic/`.
