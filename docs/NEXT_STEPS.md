# Next steps

Updated 2026-10-29. Measured results are in the generated documents (`README.md` results block, `docs/VALIDATION_UK.md`, `docs/HELDOUT_V2_RESULTS.md`, `docs/VALIDATION_ARABIC.md`, `docs/AKN_EXPORT.md`); this page lists actions only.

## Owner actions (cannot be done by the code)

| # | Action | Why |
|---|---|---|
| 1 | Send the permission request in `docs/PERMISSION_REQUEST.md` and record any reply in `sources.toml` (`permission_evidence`) and `docs/PERMISSION_TRACKING.csv` | Every UAE result depends on it; nothing has been sent |
| 2 | In the Render dashboard, service `taadeel` (srv-db63lsdckfvc73c116mg), Settings, Build and Deploy, Branch: choose `main`, Save Changes | PRs 1 and 2 are merged. The service still tracks the old branch `feat/validation-and-amendments`, which was fast forwarded to `main` so the live site matches. Repointing removes that dependency. GitHub does not trigger Render deploys here, so use Manual Deploy after a push |
| 3 | Push the tags from a clone that can: `git push origin heldout-lock-1` (the lock commit `1c02bdc`, already in `main`), then `git tag -a v0.3.0 a88602a -m "Taadeel 0.3.0" && git push origin v0.3.0` | The tool environment used for the last session cannot push tags |
| 4 | Set the repository About text and topics (settings writes are blocked in the tool environment) | Reviewers look for these first |
| 5 | Done: licence is Apache 2.0 (`LICENSE`, `NOTICE`); the crawler user agent and the permission request use the project owner's email | |
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
