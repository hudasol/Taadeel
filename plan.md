# Taadeel plan

Milestones, each tagged `m1`…`m9` with tests. Reversible decisions are noted here.

| ID | Milestone | Exit criteria | Status |
|---|---|---|---|
| P0 | Research docs | RESEARCH, DATA_SOURCES, ARCHITECTURE written | done (local) |
| P1 | Repo, plan, README | pushed to GitHub with About + topics | **blocked: GitHub write token** |
| M1 | Ingestion | permission-gated, robots-aware, rate-limited, hashed snapshots, resumable | next |
| M2 | Parsing | Arabic normalization; structure extraction law→part→chapter→article→clause; schema validation | next |
| M3 | Alignment | renumbering-robust matching with confidence and an "unaligned" bucket | |
| M4 | Diffing | article + word-level diffs; classification; amending instrument linked | |
| M5 | Temporal | point-in-time reconstruction; uncertain effective dates flagged | |
| M6 | Validation | gold set, accuracy/P/R, adversarial tests, honest report | |
| M7 | API + dataset | read-only FastAPI; versioned release + data card | |
| M8 | Interface | RTL-first bilingual UI with timeline slider, redline, as-of view | |
| M9 | Deploy | live URL, CI badge, reproducible build | |

## Decisions (reversible)

* Python 3.13, stdlib-first core, SQLite for storage (single file, trivial deploy), Parquet export for the dataset, FastAPI, static front end (no build step), pytest, GitHub Actions.
* Real-data work gated by `sources.toml`; default is link-only.
* Synthetic fixtures are labeled and live under `data/synthetic/`.
