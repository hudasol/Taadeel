# Data sources, terms and access decisions

Retrieved 2026-10-11, extended 2026-10-12. Terms are paraphrased unless in quotation marks. Re-verify before any ingestion run; terms change.

| Source | Access method | Terms (paraphrase) | robots.txt | Decision |
|---|---|---|---|---|
| UAE Legislation, uaelegislation.gov.ae (General Secretariat of the Cabinet) | HTML law pages (`/en|ar/legislations/{id}`), per-law download links; no documented API | No open licence; footer reserves all rights. ToS forbids flooding, load-increasing and unauthorised security testing; permits direct links, forbids framing. Says the Arabic text prevails over English. | `User-agent: *` / empty `Disallow` (allow all) | **Link-only until permission.** Metadata-only polite probing allowed at ≤1 request per 10 s with an identifying User-Agent. No bulk text copy. |
| Same site: `/modifications` pages and `sitemap.xml` | n/a | Return bot-detection blocks to automated clients | n/a | **Do not work around.** Documented as unavailable. Request access in the permission letter. |
| Same site, re-check 2026-10-12 | `curl` with the identifying User-Agent `TaadeelBot/0.1` | n/a | **HTTP 403 on `/robots.txt`** (2026-10-12). The 2026-10-11 reading of allow all was from a different client and is no longer relied on | **Blocked, recorded, not worked around.** No portal content was read on 2026-10-12. The ingestion adapter treats an unreadable robots.txt as disallowed. |
| Ministry of Justice (moj.gov.ae) legislation pages | HTML, script-loaded lists | © Ministry of Justice, rights reserved | Allows all except `/cp/`, `/login.aspx` | Link-only. Open-data request form is the permission channel. |
| MoJ e-laws (elaws.moj.gov.ae) | Not read (connection reset from research environment) | Unknown | Unknown | **UNVERIFIED.** Re-check manually. |
| Official Gazette (federal) | Print; subscription via MoJ | n/a | n/a | Authoritative reference only. Link, do not ingest. |
| WIPO Lex (UAE IP laws) | HTML metadata; PDFs on a separate host | WIPO's own content CC BY 4.0; excludes third-party text, so UAE statutes are likely not covered | PDF path disallowed for crawlers | Link-only. Do not crawl PDFs. |
| FTA tax legislation archive (tax.gov.ae) | HTML list + PDFs | No licence read | Allows `/en/`, `/ar/` | Link-only; candidate for permission request (tax laws have consolidated versions). |
| ILO NATLEX, FAOLEX | Bot-blocked per earlier note; not re-attempted 2026-10-12 | Unverified | n/a | Avoid. |
| Bayanat open data | Datasets | CC BY 4.0 for portal datasets | `Crawl-delay: 10` | No legislation dataset found. Usable only for datasets carrying that licence. |
| Hugging Face scrapes of the portal (`ipfs_uae_laws`, `uae-laws` and others) | Parquet/CSV | Licence tags (MIT/Apache/"other") cannot clear upstream rights; README of one states it used archive fallbacks to get around 403/429 | n/a | **Avoid as a source.** Would also copy circumvention. |

## Permission to request (owner action)

Write to the **General Secretariat of the UAE Cabinet** (via the portal's Contact Us page), copying the **Ministry of Justice** open-data request form. Ask for written permission for:

1. Read-only, rate-limited (≤1 req/10 s, off-peak) automated access to law pages and per-law PDF downloads, Arabic and English.
2. Storing text snapshots to compute and display article-level diffs, with a source link and retrieval date on every provision.
3. Redistributing a derived open dataset (article-level diffs and metadata) and whether commercial reuse is allowed.
4. A stated licence and preferred attribution wording.
5. A documented feed or API, and access to `/modifications` pages for a named crawler.

Offer: fixed User-Agent with contact email, request cap, caching, and removal on request.

## What is built in the meantime

* Ingestion adapter with robots check, rate limiter, resumable snapshots, hashing. It refuses to fetch any host not marked `permitted` in `sources.toml`.
* Everything downstream is validated on synthetic data (see `data/synthetic/`, every record carries `"synthetic": true` and is excluded from real-data views).

## UK legislation.gov.uk (engine validation only, not UAE law)

Terms read from pages retrieved 2026-10-12 (the WebFetch tool returns summaries; the OGL page was also fetched raw). Full notes: the research record kept with the project, summarised here.

| Item | Finding | Source |
|---|---|---|
| Licence | Site content is available under the Open Government Licence v3.0 except where otherwise stated. OGL permits copying, publishing, distributing, adapting and commercial or non commercial use with attribution. | https://www.legislation.gov.uk/developer/licensing ; https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ |
| Attribution used | "Contains public sector information licensed under the Open Government Licence v3.0." Shown on every UK record and in the UI. No site specific attribution statement was found (not proven absent). | same |
| Scope taken | UK Public General Acts only (`ukpga`), England and Wales view, body sections only (schedules excluded). Devolved material is excluded because its notices were not verified. | `docs/VALIDATION_UK.md` |
| Fair use | Maximum 1,500 requests per 5 minutes per user, anonymous user agents refused, avoid one off bulk crawls, follow the crawl delay. | https://www.legislation.gov.uk/fair-use-policy |
| robots.txt | `Crawl-delay: 5`; disallows `*/data.pdf`, `*/data.docx`, `/defralex`. Taadeel fetches only `data.xml`. | https://www.legislation.gov.uk/robots.txt |
| Our rate | One request per 6 seconds (above the crawl delay), identifying User-Agent with repository URL, content hashed, resumable, every fetch logged in `data/uk/manifest.jsonl`. 176 successful fetches plus 3 recorded HTTP 404 (point in time before the Act existed). Amending section sample fetched under the same rules. | `sources.toml`, `src/taadeel/uk_fetch.py` |
| Data caveats stated by the site | Revised text is an editorial construction and not the authoritative original; effects data is somewhat out of date and not guaranteed complete; base date 1 February 1991. | https://www.legislation.gov.uk/developer/limitations ; /help |
| Blocks and errors | `/terms-and-conditions` and `/fair-use` returned errors; not worked around. | research record |
| UNVERIFIED | `/changes/affecting` endpoint content; Akoma Ntoso output (`data.akn`, the documentation page is a placeholder); a machine endpoint listing version dates; devolved legislation notices. None of these is used. | |

Committed derived data: `data/uk/corpus.jsonl.gz` holds section text of dated snapshots with source URL, retrieval time and content hash, under the OGL with the attribution above. Raw XML is not committed.

## Arabic source candidates (research record, 2026-10-12)

| Candidate | Result | Decision |
|---|---|---|
| Arabic Wikisource | Hosting contributions under CC BY-SA 4.0; the copyright status of an underlying official text depends on its country (UNVERIFIED for any specific page). The API answered HTTP 429 during research. | **Not used.** No real Arabic text is committed. Normalization stays tested on labelled synthetic Arabic. Short excerpts with oldid and attribution remain a possible future fixture after a per page status check. |
| Arabic Wikipedia | CC BY-SA 4.0 for the site; not legal text. | Not used. |
| WIPO Lex, UN, OHCHR, treaties.un.org, tanzil.net | Terms pages failed to load, were not permitted by the fetch tool, or state personal use only or no redistribution. | Not used. |
| lawsociety.ly | `/about/terms-of-use/` returned HTTP 403; footer says all rights reserved. | **Blocked, recorded, not worked around.** Not used. |
| uaelegislation.gov.ae | robots.txt returned HTTP 403 to `curl` on 2026-10-12. | Blocked, recorded. See the permission request. |

The Arabic amendment pattern lexicon (`src/taadeel/amend_ar.py`) uses phrasings seen in the retrieved sources (listed with URLs in its comments). It is tested on invented samples only and is **unvalidated on real UAE text**.
