# Review rounds

These are self review rounds written by the project author. They are not reviews by any organisation. Each round is a structured self critique from a stated perspective and reflects what such a reviewer might plausibly flag, not any real review. Items listed as missing at the time of writing (2026-10-11) are marked "addressed later" where they have since been built.

## Round 1: Policy usability perspective (usability, clarity, hosting location)

**Critique**
* A policy analyst cannot find a law: there is no search (M8 requires it).
* The as of view shows only the first six articles, with no way to see the rest.
* Hosting location is unspecified, and a reviewer concerned with data location would ask for it. `render.yaml` sets no region, so the provider default applies (not confirmed to be in country).

**Checklist**: search · full article list · source link on every provision · hosting region stated.

**Fixed**: every provision in the API and UI carries source URL and retrieval date; synthetic and real separation is explicit in the UI.
**Deliberately not fixed at the time**: search and full article list (need real data to be meaningful; tracked in NEXT_STEPS). Hosting region left to the owner because requirements depend on the deployment target; stated as a manual step.
**Addressed later**: SQLite storage with FTS5, a search API now exists (see `STORAGE.md`). The hosting region question remains open.

## Round 2: Robustness and deployment perspective (robustness, deployability)

**Critique**
* No Dockerfile or health check.
* Alignment is O(n·m) with a pure Python similarity per pair; large laws (several hundred articles) will be slow. A 60 seed parameter sweep already timed out at the 2 minute limit.
* Ingestion fails closed on unreadable robots.txt, which is correct, but there is no retry or backoff policy for transient errors (only blocks are recorded).

**Checklist**: container · health endpoint · performance risk documented · transient error policy.

**Fixed**: `Dockerfile`, `render.yaml`, `/api/health`.
**Addressed later**: the Dockerfile and `render.yaml` were listed as missing in the first draft of this round and now exist; a live demo runs on the Render free tier from the branch `feat/validation-and-amendments`.
**Deliberately not fixed**: alignment performance (no real size benchmark yet; premature to optimise; candidate pruning via an n gram index noted in NEXT_STEPS). Transient error backoff left out because ingestion is disabled for all real UAE hosts.

## Round 3: Arabic NLP rigour perspective (Arabic NLP rigour, validation depth, reproducibility)

**Critique**
* Normalisation folded ئ to ي by default, which merges distinct words (for example شاطئ and شاطي) and can create false alignment.
* **Amendment by reference parsing was not implemented** ("is replaced by the following text", "added after Article X", "is repealed"). This was a named hard problem and is a core capability of the product.
* HTML and PDF structure extraction was not implemented; the parser worked on plain text only.
* Validation uses synthetic random text; it cannot establish real world accuracy. The first benchmark was too easy (all metrics perfect), which hid weaknesses until templated scenarios were added.
* The ambiguity margin was chosen after seeing results; numbers are not a clean held out estimate.

**Checklist**: conservative default normalisation · amendment parsing · extraction · harder benchmark · disclosure of tuning.

**Fixed**: hamza on yaa fold is now opt in with a test; harder templated scenarios added; tuning disclosed in `VALIDATION.md`.
**Deliberately not fixed at the time**: amendment by reference parser and HTML/PDF extraction. Both need real amending instrument text to develop honestly; writing patterns from memory would risk encoding invented drafting conventions.
**Addressed later**: a PDF extractor (tested on synthetic PDFs only), an English amendment pattern module (measured on a small UK sample) and an Arabic amendment lexicon (unvalidated, invented samples only) now exist. Real Arabic validation is still not done.

## Round 4: Claims versus evidence perspective

**Critique**
* The README opened with a present tense claim that Taadeel "produces" diffs and timelines, while only synthetic data exists.
* "Point in time correctness" has unit tests but no evaluation set.
* Thresholds are not calibrated on real text.

**Checklist**: claims match evidence · every metric labelled with its data source · limitations visible at top of README.

**Fixed**: README now states goal versus current state; `VALIDATION.md` leads with the synthetic only warning.
**Deliberately not fixed**: no real data accuracy figure is given because none exists; that is the correct state, not a gap to paper over.

## Round 5: Final senior pass (security, secrets, dependencies, coverage, README accuracy)

**Critique**
* No secrets in the repo (checked by inspection; `.env` is gitignored). A repository secret scan was not run because GitHub access was read only at the time.
* Dependencies are unpinned lower bounds; no lockfile.
* Test coverage is not measured.
* API is read only with no auth or rate limiting; acceptable for a synthetic demo, not for a public real data service.
* The `real=true` view returns empty by design; confirmed by test.

**Checklist**: secrets · pinned deps · coverage number · API abuse controls · docs consistent with code.

**Fixed**: docs and README aligned with code state.
**Deliberately not fixed**: lockfile, coverage report, rate limiting. Small, listed in NEXT_STEPS; none changes the claims made.
