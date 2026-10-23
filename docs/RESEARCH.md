# Research

Status: Phase 0, 2026-10-11 (formatting revised 2026-10-16). Claims marked UNVERIFIED were not confirmed against a primary source.

## 1. Official sources

* **UAE Legislation portal** (uaelegislation.gov.ae), run by the General Secretariat of the Cabinet. Per law pages expose: issue date, effective date, official gazette date and number, legislation state, amendment count, EN/AR toggle, per law download links, and a related legislation page. The portal reported roughly 277 federal legislations, 77 executive regulations and 610 regulatory decisions on its home page (UNVERIFIED: source URL and retrieval date not recorded; a 2026-10-09 snapshot date was noted at the time). Machine readability: structured metadata in HTML and no documented API were observed; the portal returned HTTP 403 on robots.txt, which was recorded and not worked around (see `DATA_SOURCES.md`).
* **Official Gazette**: federal laws appear within about two weeks of signature; access is print/subscription through the Ministry of Justice. No online archive found (UNVERIFIED: source URL and retrieval date not recorded).
* **Ministry of Justice** pages, **FTA tax archive** (consolidated tax laws as PDFs), **WIPO Lex** (IP laws, third party hosted PDFs).
* No source found publishes an open licence for statute text. See `DATA_SOURCES.md`.
* The English text is a translation; the portal states the Arabic prevails.

## 2. Prior art

| System | What it does | Open? | Lesson for Taadeel |
|---|---|---|---|
| legislation.gov.uk | Point in time versions, "changes to legislation" with effects data linking each change to the amending Act | Open Government Licence | The "effects" model (change → amending instrument → effective date) is the right abstraction |
| EUR-Lex consolidated versions | Consolidated text per date, with amending acts listed | Reuse permitted | Consolidations are derived, not authoritative, and carry that disclaimer |
| Akoma Ntoso / LegalDocML (OASIS) | XML standard for legislative documents, FRBR work/expression/manifestation, temporal "lifecycle" events | Open standard | Borrow the work/expression split and eId style stable identifiers |
| Legislate style/lawmaking tools, commercial redlining (Lexis and others) | Visual redlines of amendments | Proprietary | Redline UX is expected; accurate alignment is the hard part |
| Arabic legal NLP | Mostly retrieval, QA and classification benchmarks; little on amendment alignment (UNVERIFIED, literature scan not exhaustive) | Mixed | Open gap: article level alignment and temporal reconstruction for Arabic statutes |

**What Taadeel adds:** an Arabic first, confidence scored alignment of articles across versions with an explicit unaligned bucket, change classification linked to the amending instrument, effective date uncertainty as a first class state, and, as a planned item (no gold set exists yet), a published gold set evaluation.

## 3. Hard problems and design responses

1. **Renumbering.** Articles shift when others are inserted or repealed. Align by text similarity plus structural position; never trust number equality alone.
2. **مكرر / مكرراً (repeated) articles** (e.g. Article 5 bis). Numbering key is `(number, suffix)` with ordinal suffixes (مكرر، مكرر (1)، مكرر ثانياً).
3. **Amendment by reference** ("Article X is replaced by the following text", "the following article is added after Article Y", "Article Z is repealed"). Parse the amending instrument into operations; keep unparsed operations as `unresolved` instead of guessing.
4. **Arabic normalization.** Index only layer: strip tashkeel and tatweel, unify alef variants (أ إ آ → ا), yaa/alef maqsura (ى → ي), optionally taa marbuta/haa, map Arabic-Indic and Persian digits to ASCII, normalize whitespace and punctuation, NFKC for presentation forms. Display always uses the original text.
5. **Effective vs publication vs issue dates.** Three distinct dates per instrument; effective date may be "from publication", "30 days after publication", or conditional. Unknown/conditional → flag `effective_date_status = uncertain` and never silently fall back.
6. **Law vs executive regulation vs decree.** Separate `instrument_type`; regulations reference their parent law; amendments apply to a specific instrument.
7. **Dual language divergence.** Arabic is the authoritative text; English alignment is separate and secondary.

## 4. Known amendment cases for the gold set (candidates)

From secondary sources read during research; each must be checked against the official text before use as ground truth.

* Federal Decree-Law 33/2021 (Labour Relations), amended by Federal Decree-Law 9/2024 (Articles 54 and 60), in force 28 Aug 2024 per a law firm summary (UNVERIFIED: source URL and retrieval date not recorded).
* Federal Decree-Law 32/2021 (Commercial Companies), amended by Federal Decree-Law 20/2025, in force 15 Oct 2025 per a law firm summary (UNVERIFIED: source URL and retrieval date not recorded).
* Federal Decree-Law 8/2017 (VAT), amended by Federal Decree-Law 16/2024, effective 30 Oct 2024 per KPMG and the FTA archive (UNVERIFIED: source URL and retrieval date not recorded).
* Replacements, not amendments: Civil Procedure Law 42/2022 replacing Law 11/1992; Personal Status Decree-Law 41/2024 replacing Law 28/2005 (UNVERIFIED: source URL and retrieval date not recorded).

Gold set construction is blocked on text permission; see `ARCHITECTURE.md` §Validation for the fallback.
