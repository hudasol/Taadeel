# Storage and search

Research and navigation tool, not legal advice. The official Arabic text published by the competent UAE authority prevails.

## Corpora

| corpus | content | rules |
|---|---|---|
| `synthetic` | generated test text | `work_id` must start with `synthetic/`; `synthetic=1`; licence CC0-1.0 (proposed) |
| `uk-validation` | real English UK legislation, engine validation only | licence and attribution mandatory (Open Government Licence v3.0); not UAE law |
| `uae` | real UAE legislation | empty until a source permits collection; a stated licence/permission is mandatory |

`synthetic` is allowed only with the `synthetic/` prefix and the prefix only with `synthetic`. These rules are checked in Python (`Store.add_expression`) and again by SQL `CHECK` and composite foreign keys, so a raw insert cannot bypass them.
The `real` view means `uae` plus `uk-validation`. It never contains synthetic rows. The HTTP default view is `uae`; synthetic data needs `corpus=synthetic`.

## Schema (SQLite, `taadeel.store`)

* `works(work_id, corpus, title, jurisdiction, language, source_url, licence, attribution)`
* `expressions(expression_id, work_id, valid_from, effective_status, issue_date, source_url, retrieved_at, content_sha256, synthetic, corpus)`; key `(work_id, expression_id)`
* `provisions(eid, expression_id, kind, number, bis, parent, heading, text, text_norm, source_url, retrieved_at, work_id, corpus)`; `work_id` and `corpus` are additions so expression ids need only be unique per work
* `amendment_events(event_id, target_work_id, amending_work_id, op, target_eid, effective_date, effective_status, source_url, retrieved_at, evidence, corpus)`
* `changes(change_id, work_id, from_expression, to_expression, kind, a_eid, b_eid, confidence, score, renumbered, amending_work_id, words_json, corpus)`
* `provisions_fts`: FTS5 index over `text_norm` (rowid = provisions rowid)

`source_url` and `retrieved_at` are NOT NULL and non empty on expressions, provisions and amendment events. Provisions inherit them from their expression.

## Search

`Store.search(query, corpus, limit, lang)`:

1. The query goes through `taadeel.normalize.normalize` (NFKC, diacritics and tatweel removed, alef variants to bare alef, alef maqsura to yaa, Arabic-Indic and Persian digits to ASCII) and is split into tokens.
2. All tokens must match (AND). If nothing matches, the tokens are retried as prefixes.
3. Ranking is FTS5 `bm25` (higher `score` is better). Tokens are quoted, so FTS operators in user input have no effect.
4. Each hit returns the ORIGINAL text, a snippet of the original text with `[start, end]` highlight offsets, `source_url`, `retrieved_at`, corpus and licence. Rows without provenance are never returned.

## Parquet export

`Store.export_parquet(dir, corpus=None)` writes `works`, `provisions`, `changes`, `amendment_events` as zstd Parquet and `manifest.json` (rows, bytes, sha256 per file, per corpus counts, `contains_synthetic`, generation time and tool versions). Pass `corpus="real"` to exclude synthetic rows.

## Limitations

* Matching is by whole token. Arabic attached clitics (و، ب، ل، ك، ف and the article ال) are not stripped, so «بإصدار» does not match a query «إصدار». Prefix fallback only helps trailing material. No stemming or root search.
* Taa marbuta, hamza on waw/yaa are not folded (they merge distinct words).
* English search has no stemming ("licences" does not match "licence").
* One SQLite connection guarded by a lock; fine for a read-mostly demo, not for concurrent heavy writes.
* Dates are stored as ISO text. Parquet keeps them as strings.
* The default demo store is in memory and rebuilt at start.
