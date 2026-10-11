# Taadeel: tracking amendments in UAE federal legislation

Status 2026-10-11. **Not legal advice.** Synthetic evidence only; real-world accuracy is unmeasured.

## One-page summary

**Problem.** UAE federal laws are amended often. The official portal gives per-law metadata (issue, effective and gazette dates, amendment count) but, as far as this research could determine, no article-level diff or documented machine-readable amendment feed. Answering "what did this law say on date X, and what changed since?" is manual.

**What exists.** A tested engine: Arabic normalization, structure parser (part/chapter/article/clause, «مكرر» handling), confidence-scored alignment with an unaligned bucket, article- and word-level diffs with five change classes, a point-in-time model that flags uncertain effective dates, permission-gated ingestion, a read-only API, an RTL-first bilingual UI, a dataset exporter with data card, and a validation harness.

**What does not exist yet.** Real data (no source currently permits text collection), HTML/PDF extraction, amendment-by-reference parsing, search, deployment, a real gold set.

**Headline numbers (synthetic only).** Alignment accuracy ranges from 0.877 to 1.000 depending on scenario; near-duplicate and heavily rewritten articles are the weak spot (see table below). These do not predict accuracy on real statutes.

## Related work

legislation.gov.uk (point-in-time, effects linking changes to amending Acts), EUR-Lex consolidated versions, Akoma Ntoso/LegalDocML (work/expression model, stable identifiers), commercial redlining tools. Public Arabic legal-NLP work found is mostly retrieval/QA/classification; no open article-level alignment benchmark for Arabic statutes was found (scan not exhaustive). Details: `RESEARCH.md`.

## Method

Akoma Ntoso-inspired model (work, expression, provision, amendment event, alignment, change). Alignment is monotonic dynamic programming over a blend of normalized text similarity (0.85), relative position (0.10) and number equality (0.05); pairs below 0.35 are not forced; pairs below 0.60 or with a rival candidate within 0.05 are `low` confidence. Diff classes: `clarified` only when normalized text is identical; any word or numeral change is `replaced`. Temporal logic never guesses: a version with an uncertain effective date yields `uncertain` plus candidates. Normalization is index-only; display text is untouched.

## Validation

See `VALIDATION.md` for the full table and caveats. Summary (synthetic, seeds 0–29):

| scenario | align acc. | replaced P / R | repealed P / R | inserted P / R |
|---|---|---|---|---|
| easy | 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| templated near-duplicates | 0.981 | 0.751 / 0.987 | 0.968 / 0.667 | 1.000 / 0.689 |
| templated, 70% words edited | 0.918 | 0.511 / 0.593 | 0.604 / 0.644 | 0.417 / 0.444 |
| templated, many inserts/repeals | 0.877 | 0.446 / 0.896 | 0.989 / 0.375 | 1.000 / 0.379 |

The easy scenario is a sanity check, not evidence. The ambiguity margin was added after seeing results, so the table is not a clean held-out estimate.

## Limitations

1. No real legislation loaded; licensing gate documented in `DATA_SOURCES.md`.
2. Plain-text parser only; no HTML/PDF extraction.
3. No amendment-by-reference parsing, so amendment events cannot yet be derived from amending instruments.
4. Monotonic alignment cannot represent long-distance moves.
5. Alignment is O(n·m) and untested at real law sizes.
6. Synthetic text has no cross-references or legal drafting structure.
7. Point-in-time logic is unit-tested, not evaluated.
8. Not deployed; code is local until GitHub write access is restored.
