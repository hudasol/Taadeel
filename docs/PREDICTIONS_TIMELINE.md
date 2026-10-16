# Predictions for the snapshot timeline (pre registered)

Written and committed before `python -m taadeel.timeline_v2 run` was executed. English UK legislation (OGL v3.0) only; nothing here is evidence about UAE law.

* Method: `src/taadeel/timeline_v2.py` (sha256 `7583e8f36621ed4a41c4d0bf5e57895c0b368dadd6403c0111522b9c5c5e7768`). The locked `temporal.py` is not edited; the old method is re run in the same script for comparison.
* Queries: the day before each recorded effect date for which both snapshots exist (the published evaluation had 80). Truth: the snapshot fetched for that day, which the method never reads.
* Effects are read from the current XML retrieved on 2026-10-16; the published 63 of 80 used the XML of 2026-10-12, so small differences are possible.

| id | prediction |
|---|---|
| T0 | The old method (effects only) is correct on 63 of 80 queries, plus or minus 2 (sanity check of the re run). |
| T1 | The new method answers "certain" and wrong on at most 5 queries. |
| T2 | The new method answers "uncertain" on at most 30% of queries. |
| T3 | For at least 80% of "uncertain" answers, the true text is one of the candidate texts. |
| T4 | The new method answers "certain" and correct on at least 50 queries. |

The run writes `results/uk_timeline_v2.json` once and refuses to run again. Results are reported as generated, including misses.
