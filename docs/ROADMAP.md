# Limitations and plan

This page lists what the project cannot do yet, why, and what is being done about it. Measured numbers live in the generated documents (`docs/BASELINES.md`, `docs/VALIDATION_UK.md`, `docs/EVALUATION_CARD.md`), not here.

## Audit

| # | Limitation | Cause | Status |
|---|---|---|---|
| 1 | No reference point for the alignment results. "All sections aligned" is meaningless if a trivial method does the same | Earlier phases measured the engine only against itself | Fixed: `taadeel.baselines`, results in `docs/BASELINES.md` |
| 2 | A reader could not use their own texts. Only stored works could be diffed | The API exposed stored data only | Fixed: `taadeel diff`, `POST /api/compare`, and a section on the page. Arabic and English headings |
| 3 | Arabic search missed a word typed without the definite article | Matching was by word prefix | Fixed in `store.py`, with a test |
| 4 | No console script, no package metadata, no lint gate | Early phases were research code | Fixed: `pyproject.toml`, `ruff` in CI, hashed files excluded on purpose |
| 5 | No real UAE legislation | The official portal returned 403 on robots.txt, recorded and not worked around. A permission request is drafted and unsent | Blocked on the owner: `docs/PERMISSION_REQUEST.md` |
| 6 | Arabic amendment patterns are unvalidated on real text | No permitted real Arabic amending instruments | Blocked on item 5 |
| 7 | Amendment by reference recall is low in English | Patterns cover the common forms only | Open: needs a new development half, see `docs/NEXT_STEPS.md` |
| 8 | Schedules, devolved material and prospective changes are excluded from the UK corpus | Scope chosen for a clean ground truth | Documented, not planned |
| 9 | UK ground truth is editorial, hand checks were done by the author | No legal reviewer | Open: needs a reviewer |
| 10 | The live site served an older branch | Render tracked the first pull request branch | Fixed: both PRs merged, branch fast forwarded to `main`, deployed. Remaining: repoint Render to `main` in the dashboard |
| 11 | No licence file | Not yet chosen | Fixed: Apache License 2.0, with a `NOTICE` that keeps the UK sample data under the Open Government Licence |

## What the baselines are for

A baseline here is a method simple enough that anyone could write it in an afternoon, fixed before it was run and scored with the same ground truth and scoring code as the engine. They are `by_number` (match by section number, no text), `greedy_text` (best text match, one to one) and `latest` (always serve the newest snapshot). If the engine did not beat them in the conditions it was built for, the engine would not be worth shipping. `docs/BASELINES.md` states where it does, where it ties, and where it loses.

## Next, in order

1. Send the permission request, then ingest a small set of UAE laws and score the engine and the baselines against a hand checked gold set (`docs/NEXT_STEPS.md`, engineering item 1).
2. Add a lockfile and a coverage report to CI.
3. Add rate limiting in front of `POST /api/compare` if it is exposed beyond a demo. The request already has size and article caps.
4. Decide `normalize_v2` after a check on real Arabic text.
