# Next steps

Updated 2026-10-23. Measured results are in the generated documents (`README.md` results block, `docs/VALIDATION_UK.md`, `docs/HELDOUT_V2_RESULTS.md`, `docs/VALIDATION_ARABIC.md`, `docs/AKN_EXPORT.md`); this page lists actions only.

## Owner actions (cannot be done by the code)

| # | Action | Why |
|---|---|---|
| 1 | Send the permission request in `docs/PERMISSION_REQUEST.md` and record any reply in `sources.toml` (`permission_evidence`) and `docs/PERMISSION_TRACKING.csv` | Every UAE result depends on it; nothing has been sent |
| 2 | Review and merge PR #1, then retarget PR #2 to `main` and merge it. Then repoint the live site: Render dashboard, service `taadeel` (srv-db63lsdckfvc73c116mg), Settings, Build and Deploy, Branch, Edit, choose `main`, Save Changes; then Manual Deploy, Deploy latest commit; then open https://taadeel.onrender.com/api/health and check that `corpus_counts` is present | The live site still serves the PR #1 branch; merging was not approved in this session |
| 3 | Push the tag `heldout-lock-1` from the clone that holds it (`git push origin heldout-lock-1`), or confirm its commit (likely `1c02bdc`) and create it here. A retry on 2026-10-23 failed because this clone has no such tag | The tag is still local only |
| 4 | Set the repository About text and topics; confirm the licence (MIT is proposed, no LICENSE file yet) | Reviewers look for these first |
| 5 | Decide on a project contact address for the crawler user agent instead of a personal address | Privacy |
| 6 | Decide whether the Wikisource page (oldid 137670) may be used as a short attributed fixture, after checking the current UAE copyright law from an official source | Its reuse status is not clear, so no wording was committed |

## Engineering, in order

| # | Task | Exit check |
|---|---|---|
| 1 | With permission: ingest 5 to 8 UAE laws with amendments; hand check a gold set with each item cited | Gold set file with sources and retrieval dates; v1 and v2 measured once against it |
| 2 | Arabic amendment by reference patterns on real UAE amending instruments | Dev and test split by hash, patterns frozen before the test half |
| 3 | Cover the schedule form "Section N ... is amended as follows" in the English patterns, tuned on a new dev half only | Measured once on a new test half |
| 4 | Decide on `normalize_v2` as the default after a check on real Arabic text | Stress set plus a real text sample |
| 5 | Akoma Ntoso: lifecycle and modification metadata | Schema valid plus a check of the modification elements |
| 6 | Lockfile, coverage report, API rate limiting | CI green |
| 7 | Sovereign deployment option (UAE hosted region) once the data owner states residency needs | Container check in CI already runs with no network |
