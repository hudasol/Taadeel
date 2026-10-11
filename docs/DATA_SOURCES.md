# Data sources, terms and access decisions

Retrieved 2026-10-11. Terms are paraphrased, not quoted. Re-verify before any ingestion run; terms change.

| Source | Access method | Terms (paraphrase) | robots.txt | Decision |
|---|---|---|---|---|
| UAE Legislation, uaelegislation.gov.ae (General Secretariat of the Cabinet) | HTML law pages (`/en|ar/legislations/{id}`), per-law download links; no documented API | No open licence; footer reserves all rights. ToS forbids flooding, load-increasing and unauthorised security testing; permits direct links, forbids framing. Says the Arabic text prevails over English. | `User-agent: *` / empty `Disallow` (allow all) | **Link-only until permission.** Metadata-only polite probing allowed at ≤1 request per 10 s with an identifying User-Agent. No bulk text copy. |
| Same site: `/modifications` pages and `sitemap.xml` | n/a | Return bot-detection blocks to automated clients | n/a | **Do not work around.** Documented as unavailable. Request access in the permission letter. |
| Ministry of Justice (moj.gov.ae) legislation pages | HTML, script-loaded lists | © Ministry of Justice, rights reserved | Allows all except `/cp/`, `/login.aspx` | Link-only. Open-data request form is the permission channel. |
| MoJ e-laws (elaws.moj.gov.ae) | Not read (connection reset from research environment) | Unknown | Unknown | **UNVERIFIED.** Re-check manually. |
| Official Gazette (federal) | Print; subscription via MoJ | n/a | n/a | Authoritative reference only. Link, do not ingest. |
| WIPO Lex (UAE IP laws) | HTML metadata; PDFs on a separate host | WIPO's own content CC BY 4.0; excludes third-party text, so UAE statutes are likely not covered | PDF path disallowed for crawlers | Link-only. Do not crawl PDFs. |
| FTA tax legislation archive (tax.gov.ae) | HTML list + PDFs | No licence read | Allows `/en/`, `/ar/` | Link-only; candidate for permission request (tax laws have consolidated versions). |
| ILO NATLEX, FAOLEX | Bot-blocked | Unverified | n/a | Avoid. |
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
