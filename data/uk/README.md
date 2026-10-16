# data/uk

Derived data from legislation.gov.uk (English UK Public General Acts, England and Wales view, body sections), used only to validate the Taadeel engine. This is not UAE law.

Contains public sector information licensed under the Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Source: https://www.legislation.gov.uk. Revised text on that site is an editorial construction and may not be fully up to date.

* `corpus.jsonl.gz`: section text per dated snapshot, with the source URL, retrieval time and content hash of each snapshot.
* `changes.jsonl.gz`: engine output (locked engine) for consecutive snapshots.
* `manifest.jsonl`: every fetch made (URL, status, hash, time), including three HTTP 404 responses.
* `amending_sample.json`: amending Act sections used to test English amendment patterns (first sample, 2026-10-12).
* `amending_sample_2.json`, `amending_sample_2_schedules.json`: second sample (2026-10-16), the 11 remaining amending sections and 99 schedule paragraphs selected by the rules in `docs/DECISIONS.md` items 6 and 7.

Fetching followed `docs/DATA_SOURCES.md` (identifying user agent, one request per 6 seconds, robots.txt respected).
