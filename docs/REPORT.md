# Taadeel: tracking amendments in UAE federal legislation

Status 2026-10-11, with status lines updated 2026-10-16. **Not legal advice.** Synthetic and UK English evidence only; real world accuracy on UAE legislation is unmeasured.

Superseded for numbers by `docs/VALIDATION_UK.md` and `docs/HELDOUT_RESULTS.md` (generated).

## One page summary

**Problem.** UAE federal laws are amended often. The official portal gives per law metadata (issue, effective and gazette dates, amendment count) but, as far as this research could determine, no article level diff or documented machine readable amendment feed. Answering "what did this law say on date X, and what changed since?" is manual.

**What exists (as of 2026-10-16).** A tested engine: Arabic normalisation, structure parser (part/chapter/article/clause, «مكرر» handling), confidence scored alignment with an unaligned bucket (v1, hash locked), article and word level diffs with five change classes, a point in time model that flags uncertain effective dates, a PDF extractor (tested on synthetic PDFs only), SQLite storage with FTS5 and Parquet export, a search API, a FastAPI API, an RTL bilingual web page, a Dockerfile and `render.yaml` (a live demo runs on the Render free tier from the branch `feat/validation-and-amendments`), an English amendment pattern module (measured on a small UK sample), an Arabic amendment lexicon (unvalidated, invented samples only), a UK legislation.gov.uk adapter with validation, permission gated ingestion and a validation harness.

**What does not exist yet.** Any real UAE law (no permission was obtained; the portal returned HTTP 403 on robots.txt, which was recorded and not worked around), any real Arabic validation, Akoma Ntoso lifecycle and modification metadata (a compatible export was added later, `docs/AKN_EXPORT.md`), and a gold set of real UAE laws.

**Numbers.** This report holds no hand typed result figures. Generated results are in `docs/HELDOUT_RESULTS.md`, `docs/VALIDATION_UK.md` and `results/dev_synthetic.json`. Synthetic results do not predict accuracy on real statutes.

## Related work

legislation.gov.uk (point in time, effects linking changes to amending Acts), EUR-Lex consolidated versions, Akoma Ntoso/LegalDocML (work/expression model, stable identifiers), commercial redlining tools. Public Arabic legal NLP work found is mostly retrieval/QA/classification; no open article level alignment benchmark for Arabic statutes was found (scan not exhaustive). Details: `RESEARCH.md`.

## Method

Akoma Ntoso inspired model (work, expression, provision, amendment event, alignment, change). Alignment is monotonic dynamic programming over a blend of normalised text similarity, relative position and number equality; weak pairs are not forced, and pairs with low similarity or a close rival candidate are marked `low` confidence. The exact weights and thresholds are in `src/taadeel/align.py` and were tuned on synthetic development seeds only. Diff classes: `clarified` only when normalised text is identical; any word or numeral change is `replaced`. Temporal logic never guesses: a version with an uncertain effective date yields `uncertain` plus candidates. Normalisation is index only; display text is untouched.

## Validation

See `VALIDATION.md` for status and caveats. Numbers live only in generated files:

* `docs/HELDOUT_RESULTS.md` (generated): held out synthetic results.
* `docs/VALIDATION_UK.md` (generated): UK English validation.
* `results/dev_synthetic.json`: synthetic development results.

The earlier hand typed table in this section (2026-10-11) was removed because it duplicated result files. The ambiguity margin was added after seeing results on development seeds, so development numbers are not a clean held out estimate.

## Limitations

1. No real UAE legislation loaded; licensing gate documented in `DATA_SOURCES.md`.
2. The PDF extractor has been tested on synthetic PDFs only; no real UAE PDF or HTML has been processed.
3. The English amendment pattern module was measured on a small UK sample; the Arabic amendment lexicon is unvalidated and rests on invented samples, so amendment events cannot yet be derived reliably from real Arabic amending instruments.
4. Monotonic alignment cannot represent long distance moves.
5. Alignment is O(n·m) and untested at real law sizes.
6. Synthetic text has no cross references or legal drafting structure.
7. Point in time logic was unit tested only at the time of this report; it was later evaluated on UK data (`docs/VALIDATION_UK.md`).
8. The live demo is a free tier deployment of a feature branch, with synthetic and UK validation data only.

## History

* 2026-10-11 status (superseded): HTML and PDF extraction, amendment parsing, search, deployment and the GitHub push were listed as missing. See the "What exists" paragraph above for the current state.
