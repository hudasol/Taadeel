"""Polite, resumable fetching of UK Public General Acts for engine validation.

Real English UK legislation, Open Government Licence v3.0 (see docs/DATA_SOURCES.md).
This validates the engine on English text; it says nothing about UAE law.

Everything goes through ``taadeel.ingest.Ingestor``: sources.toml gate, robots.txt, the
5 s crawl delay, identifying user agent, content-addressed hashed snapshots, resume.
Raw XML stays in ``snapshots/uk`` (gitignored); data/uk/manifest.jsonl records each fetch.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .ingest import Blocked, Ingestor, load_sources

ROOT = Path(os.environ.get("TAADEEL_ROOT") or Path(__file__).resolve().parents[2])
BASE = "https://www.legislation.gov.uk"
STORE = ROOT / "snapshots" / "uk"
MANIFEST = ROOT / "data" / "uk" / "manifest.jsonl"

# Candidate Public General Acts for the survey (type/year/number). Chosen before looking at data.
CANDIDATES = {
    "Computer Misuse Act 1990": "ukpga/1990/18",
    "Fraud Act 2006": "ukpga/2006/35",
    "Modern Slavery Act 2015": "ukpga/2015/30",
    "Bribery Act 2010": "ukpga/2010/23",
    "Theft Act 1968": "ukpga/1968/60",
    "Human Rights Act 1998": "ukpga/1998/42",
    "Official Secrets Act 1989": "ukpga/1989/6",
    "Protection from Harassment Act 1997": "ukpga/1997/40",
    "Public Order Act 1986": "ukpga/1986/64",
    "Misuse of Drugs Act 1971": "ukpga/1971/38",
}


def url_current(act: str) -> str:
    return f"{BASE}/{act}/data.xml"


def url_enacted(act: str) -> str:
    return f"{BASE}/{act}/enacted/data.xml"


def url_at(act: str, date: str) -> str:
    return f"{BASE}/{act}/{date}/data.xml"


def url_section_enacted(act: str, section: str) -> str:
    return f"{BASE}/{act}/section/{section}/enacted/data.xml"


def make_ingestor() -> Ingestor:
    return Ingestor(load_sources(ROOT / "sources.toml"), STORE)


def fetch(ing: Ingestor, url: str, log=print) -> Path | None:
    """Fetch one URL (resumable). Returns the blob path, or None if blocked / not found."""
    try:
        snap = ing.fetch(url)
    except Blocked as e:
        log(f"BLOCKED {e}")
        _manifest({"url": url, "status": "blocked"})
        return None
    if snap.status != 200:
        log(f"HTTP {snap.status} {url}")
        _manifest({"url": url, "status": snap.status})
        return None
    _manifest({"url": url, "final_url": snap.final_url, "status": 200, "sha256": snap.sha256,
               "retrieved_at": snap.retrieved_at, "bytes": Path(snap.path).stat().st_size})
    return Path(snap.path)


_seen: set[str] = set()


def _manifest(rec: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    key = json.dumps(rec, sort_keys=True)
    if not _seen:
        if MANIFEST.exists():
            _seen.update(json.dumps(json.loads(l), sort_keys=True) for l in MANIFEST.read_text().splitlines() if l)
    if key in _seen:
        return
    _seen.add(key)
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


SELECTION_RULE = ("At least 15 usable England & Wales text effects dated after the 1991-02-01 base, "
                  "3 to 15 distinct effect dates, and at least 10 live sections (fixed before any engine result).")
BASE_DATE = "1991-02-01"


def snapshot_dates(act: str, ing: Ingestor | None = None) -> list[str]:
    """Effect dates (England & Wales view, usable, after base) from the already-fetched current XML."""
    from datetime import date as _d

    from . import clml

    ing = ing or make_ingestor()
    snap = ing.latest(url_current(act))
    if snap is None:
        raise SystemExit(f"current XML for {act} not fetched yet")
    eff = clml.parse_effects(clml.load(snap.path))
    ds = sorted({e.date for e in eff if e.status == "ok" and e.sections and e.kind != "other"
                 and e.date and _d(1991, 2, 1) < e.date <= _d(2026, 10, 12)})
    return [d.isoformat() for d in ds]


def plan_snapshots(act: str, ing: Ingestor | None = None) -> list[str]:
    """Snapshot dates to fetch: base, every effect date, and the day before each (boundary checks)."""
    from datetime import date as _d
    from datetime import timedelta

    out = {BASE_DATE}
    for ds in snapshot_dates(act, ing):
        d = _d.fromisoformat(ds)
        out.add(ds)
        out.add((d - timedelta(days=1)).isoformat())
    return sorted(out)


def cmd_snapshots(acts: list[str]) -> None:
    ing = make_ingestor()
    for act in acts:
        dates = plan_snapshots(act, ing)
        print(f"{act}: {len(dates)} snapshots", flush=True)
        for d in dates:
            fetch(ing, url_at(act, d))
    print("done", flush=True)


def cmd_survey() -> None:
    ing = make_ingestor()
    for name, act in CANDIDATES.items():
        print(name, act, fetch(ing, url_current(act)), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "survey":
        cmd_survey()
    elif cmd == "snapshots":
        cmd_snapshots(sys.argv[2:])
    else:
        print("usage: survey | snapshots ACT [ACT...]")
