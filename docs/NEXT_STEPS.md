# Next steps

Updated 2026-10-16. Measured results are in the generated documents (`README.md` results block, `docs/VALIDATION_UK.md`, `docs/HELDOUT_V2_RESULTS.md`, `docs/VALIDATION_ARABIC.md`, `docs/AKN_EXPORT.md`); this page lists actions only.

## Owner actions (cannot be done by the code)

| # | Action | Why |
|---|---|---|
| 1 | Send the permission request in `docs/PERMISSION_REQUEST.md` and record any reply in `sources.toml` (`permission_evidence`) and `docs/PERMISSION_TRACKING.csv` | Every UAE result depends on it; nothing has been sent |
| 2 | Review and merge PR #1, then the phase 3 pull request into it, and only then decide whether the live site should deploy from `main` | The live site still serves the PR #1 branch; this session's changes reach it only after a merge |
| 3 | Confirm the commit for the tag `heldout-lock-1` (likely `1c02bdc`) and push it; tag a release after merging | The tag was never pushed from the earlier clone |
| 4 | Set the repository About text and topics; confirm the licence (MIT is proposed, no LICENSE file yet) | Reviewers look for these first |
| 5 | Decide on a project contact address for the crawler user agent instead of a personal address | Privacy |
| 6 | Decide whether the Wikisource page (oldid 137670) may be used as a short attributed fixture, after checking the current UAE copyright law from an official source | Its reuse status is not clear, so no wording was committed |

## Engineering, in order

| # | Task | Exit check |
|---|---|---|
| 1 | With permission: ingest 5 to 8 UAE laws with amendments; hand check a gold set with each item cited | Gold set file with sources and retrieval dates; v1 and v2 measured once against it |
| 2 | Arabic amendment by reference patterns on real UAE amending instruments | Dev and test split by hash, patterns frozen before the test half |
| 3 | Wire the snapshot timeline (`timeline_v2.py`) into the API and page, showing candidate texts for uncertain dates | API test plus a browser check in both languages |
| 4 | Cover the schedule form "Section N ... is amended as follows" in the English patterns, tuned on a new dev half only | Measured once on a new test half |
| 5 | Decide on `normalize_v2` as the default after a check on real Arabic text | Stress set plus a real text sample |
| 6 | Akoma Ntoso: lifecycle and modification metadata | Schema valid plus a check of the modification elements |
| 7 | Lockfile, coverage report, API rate limiting | CI green |
| 8 | Sovereign deployment option (UAE hosted region) once the data owner states residency needs | Container check in CI already runs with no network |
