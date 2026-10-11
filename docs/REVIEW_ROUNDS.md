# Review rounds

Each round is a structured self-critique from a named perspective. These were performed by the author-agent, not by the named organisations; they reflect what such a reviewer would plausibly flag, not any real review.

## Round 1 — ADEO engineer (policy-team usability, clarity, sovereignty)

**Critique**
* A policy analyst cannot find a law: there is no search (M8 requires it).
* The as-of view shows only the first six articles, with no way to see the rest.
* Hosting location is unspecified, and a sovereignty-minded reviewer would ask for it. `render.yaml` sets no region, so the provider default applies (not confirmed to be in-country).

**Checklist**: search · full article list · source link on every provision · hosting region stated.

**Fixed**: every provision in the API and UI carries source URL and retrieval date; synthetic/real separation is explicit in UI.
**Deliberately not fixed**: search and full article list (need real data to be meaningful; tracked in NEXT_STEPS). Hosting region left to owner because sovereignty requirements depend on the deployment target; stated as a manual step.

## Round 2 — EDGE engineer (robustness, deployability)

**Critique**
* No Dockerfile or health check.
* Alignment is O(n·m) with a pure-Python similarity per pair; large laws (several hundred articles) will be slow. A 60-seed parameter sweep already timed out at the 2-minute limit.
* Ingestion fails closed on unreadable robots.txt, which is correct, but there is no retry/backoff policy for transient errors (only blocks are recorded).

**Checklist**: container · health endpoint · performance risk documented · transient-error policy.

**Fixed**: `Dockerfile`, `render.yaml`, `/api/health`.
**Deliberately not fixed**: alignment performance (no real-size benchmark yet; premature to optimise; candidate-pruning via n-gram index noted in NEXT_STEPS). Transient-error backoff left out because ingestion is disabled for all real hosts.

## Round 3 — TII engineer (Arabic NLP rigor, validation depth, reproducibility)

**Critique**
* Normalization folded ئ→ي by default, which merges distinct words (e.g. شاطئ/شاطي) and can create false alignment.
* **Amendment-by-reference parsing is not implemented** ("is replaced by the following text", "added after Article X", "is repealed"). This was a named hard problem and is a core capability of the product.
* HTML/PDF structure extraction is not implemented; the parser works on plain text only.
* Validation uses synthetic random text; it cannot establish real-world accuracy. The first benchmark was too easy (all metrics 1.000), which hid weaknesses until templated scenarios were added.
* The ambiguity margin was chosen after seeing results; numbers are not a clean held-out estimate.

**Checklist**: conservative default normalization · amendment parsing · extraction · harder benchmark · disclosure of tuning.

**Fixed**: hamza-on-yaa fold is now opt-in with a test; harder templated scenarios added; tuning disclosed in `VALIDATION.md`.
**Deliberately not fixed**: amendment-by-reference parser and HTML/PDF extraction. Both need real amending-instrument text to develop honestly; writing patterns from memory would risk encoding invented drafting conventions. Listed first in NEXT_STEPS.

## Round 4 — ATRC engineer (claims versus evidence)

**Critique**
* The README opened with a present-tense claim that Taadeel "produces" diffs and timelines, while only synthetic data exists.
* "Point-in-time correctness" has unit tests but no evaluation set.
* Thresholds are not calibrated on real text.

**Checklist**: claims match evidence · every metric labelled with its data source · limitations visible at top of README.

**Fixed**: README now states goal vs current state; `VALIDATION.md` leads with the synthetic-only warning.
**Deliberately not fixed**: no real-data accuracy figure is given because none exists; that is the correct state, not a gap to paper over.

## Round 5 — Final senior pass (security, secrets, dependencies, coverage, README accuracy)

**Critique**
* No secrets in the repo (checked by inspection; `.env` is gitignored). A repository secret scan was not run because GitHub access is read-only.
* Dependencies are unpinned lower bounds; no lockfile.
* Test coverage is not measured.
* API is read-only with no auth or rate limiting; acceptable for synthetic demo, not for a public real-data service.
* The `real=true` view returns empty by design; confirmed by test.

**Checklist**: secrets · pinned deps · coverage number · API abuse controls · docs consistent with code.

**Fixed**: docs/README aligned with code state.
**Deliberately not fixed**: lockfile, coverage report, rate limiting. Small, listed in NEXT_STEPS; none changes the claims made.
