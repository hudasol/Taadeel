"""SQLite storage with FTS5 search and Parquet export. Not legal advice.

Corpus rules (enforced in code AND by SQL constraints):

* ``synthetic``      generated test text; work_id must start with ``synthetic/``
* ``uk-validation``  real English UK legislation (OGL), engine validation only
* ``uae``            real UAE legislation; empty until a source permits collection

Provenance (source_url, retrieved_at) is mandatory on expressions, provisions and
amendment events. Search never returns text without its provenance.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .model import Expression, Provision, validate_expression
from .normalize import normalize
from .temporal import PointInTime, Version
from .temporal import as_of as _as_of

SCHEMA_VERSION = 1
DISCLAIMER = ("Research and navigation tool, not legal advice. The official Arabic text published by the "
              "competent UAE authority prevails.")
CORPORA = ("synthetic", "uk-validation", "uae")
REAL_CORPORA = ("uae", "uk-validation")          # the "real" view: never synthetic
SYNTHETIC_PREFIX = "synthetic/"
_JURISDICTION = {"synthetic": "synthetic", "uk-validation": "UK", "uae": "AE"}


class StoreError(ValueError):
    """Raised when a write would violate provenance or corpus rules."""


_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS works(
  work_id TEXT PRIMARY KEY,
  corpus TEXT NOT NULL CHECK(corpus IN ('synthetic','uk-validation','uae')),
  title TEXT NOT NULL DEFAULT '',
  jurisdiction TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'ar',
  source_url TEXT NOT NULL CHECK(length(source_url) > 0),
  licence TEXT NOT NULL DEFAULT '',
  attribution TEXT NOT NULL DEFAULT '',
  CHECK((corpus = 'synthetic') = (substr(work_id, 1, 10) = 'synthetic/')),
  UNIQUE(work_id, corpus)
);
CREATE TABLE IF NOT EXISTS expressions(
  expression_id TEXT NOT NULL,
  work_id TEXT NOT NULL,
  valid_from TEXT,
  effective_status TEXT NOT NULL CHECK(effective_status IN ('known','uncertain','unknown')),
  issue_date TEXT,
  source_url TEXT NOT NULL CHECK(length(source_url) > 0),
  retrieved_at TEXT NOT NULL CHECK(length(retrieved_at) > 0),
  content_sha256 TEXT NOT NULL,
  synthetic INTEGER NOT NULL CHECK(synthetic IN (0,1)),
  corpus TEXT NOT NULL CHECK(corpus IN ('synthetic','uk-validation','uae')),
  PRIMARY KEY(work_id, expression_id),
  CHECK((synthetic = 1) = (corpus = 'synthetic')),
  UNIQUE(work_id, expression_id, corpus),
  FOREIGN KEY(work_id, corpus) REFERENCES works(work_id, corpus)
);
CREATE TABLE IF NOT EXISTS provisions(
  eid TEXT NOT NULL,
  expression_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('part','chapter','article','clause')),
  number INTEGER,
  bis INTEGER NOT NULL DEFAULT 0,
  parent TEXT,
  heading TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL,
  text_norm TEXT NOT NULL,
  source_url TEXT NOT NULL CHECK(length(source_url) > 0),
  retrieved_at TEXT NOT NULL CHECK(length(retrieved_at) > 0),
  work_id TEXT NOT NULL,
  corpus TEXT NOT NULL,
  PRIMARY KEY(work_id, expression_id, eid),
  FOREIGN KEY(work_id, expression_id, corpus) REFERENCES expressions(work_id, expression_id, corpus)
);
CREATE INDEX IF NOT EXISTS ix_prov_corpus ON provisions(corpus);
CREATE VIRTUAL TABLE IF NOT EXISTS provisions_fts USING fts5(text_norm);
CREATE TABLE IF NOT EXISTS amendment_events(
  event_id TEXT PRIMARY KEY,
  target_work_id TEXT NOT NULL,
  amending_work_id TEXT,
  op TEXT NOT NULL,
  target_eid TEXT,
  effective_date TEXT,
  effective_status TEXT NOT NULL CHECK(effective_status IN ('known','uncertain','unknown')),
  source_url TEXT NOT NULL CHECK(length(source_url) > 0),
  retrieved_at TEXT NOT NULL CHECK(length(retrieved_at) > 0),
  evidence TEXT NOT NULL DEFAULT '',
  corpus TEXT NOT NULL,
  FOREIGN KEY(target_work_id, corpus) REFERENCES works(work_id, corpus)
);
CREATE TABLE IF NOT EXISTS changes(
  change_id TEXT PRIMARY KEY,
  work_id TEXT NOT NULL,
  from_expression TEXT NOT NULL,
  to_expression TEXT NOT NULL,
  kind TEXT NOT NULL,
  a_eid TEXT,
  b_eid TEXT,
  confidence TEXT,
  score REAL,
  renumbered INTEGER NOT NULL DEFAULT 0,
  amending_work_id TEXT,
  words_json TEXT NOT NULL DEFAULT '[]',
  corpus TEXT NOT NULL,
  FOREIGN KEY(work_id, from_expression, corpus) REFERENCES expressions(work_id, expression_id, corpus),
  FOREIGN KEY(work_id, to_expression, corpus) REFERENCES expressions(work_id, expression_id, corpus)
);
"""

_TOKEN = re.compile(r"[\wؐ-ًؚ-ٰٟۖ-ۭـ]+")


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    return v.isoformat() if isinstance(v, (date, datetime)) else str(v)


def resolve_corpora(corpus: str) -> tuple[str, ...]:
    """Map a corpus name to the concrete corpora it covers. 'real' never includes synthetic."""
    if corpus == "real":
        return REAL_CORPORA
    if corpus in CORPORA:
        return (corpus,)
    raise StoreError(f"unknown corpus {corpus!r}; expected one of {CORPORA + ('real',)}")


def query_tokens(query: str) -> list[str]:
    """Normalize a user query (diacritics, alef/yaa variants, Arabic-Indic digits) into tokens."""
    return _TOKEN.findall(normalize(query))


def _fts_query(tokens: list[str], prefix: bool) -> str:
    return " AND ".join('"' + t.replace('"', '""') + '"' + ("*" if prefix else "") for t in tokens)


def _fts_query_article(tokens: list[str]) -> str:
    """Third attempt for Arabic: a term also matches with or without the definite article (ال) as a prefix."""
    parts = []
    for t in tokens:
        alts = {t}
        if t.startswith("ال") and len(t) > 4:
            alts.add(t[2:])
        elif "\u0600" <= t[:1] <= "\u06ff":
            alts.add("ال" + t)
        parts.append("(" + " OR ".join('"' + a.replace('"', '""') + '"*' for a in sorted(alts)) + ")")
    return " AND ".join(parts)


def _highlights(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    out = []
    for m in _TOKEN.finditer(text):
        w = normalize(m.group())
        if any(w == t or w.startswith(t) or w.startswith("ال" + t) or (t.startswith("ال") and w.startswith(t[2:])) for t in tokens):
            out.append((m.start(), m.end()))
    return out


def make_snippet(text: str, tokens: list[str], width: int = 240) -> tuple[str, list[list[int]]]:
    """Excerpt of the ORIGINAL text around the first match, with [start, end] highlight offsets."""
    hl = _highlights(text, tokens)
    if len(text) <= width:
        return text, [list(h) for h in hl]
    first = hl[0][0] if hl else 0
    s = max(0, first - width // 3)
    e = min(len(text), s + width)
    if s > 0:
        k = text.find(" ", s)
        s = k + 1 if 0 <= k < first else s
    if e < len(text):
        k = text.rfind(" ", s, e)
        e = k if k > s else e
    pre = "…" if s > 0 else ""
    post = "…" if e < len(text) else ""
    snip = pre + text[s:e] + post
    shifted = [[a - s + len(pre), b - s + len(pre)] for a, b in hl if a >= s and b <= e]
    return snip, shifted


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    # ------------------------------------------------------------------ writes
    def add_expression(self, expr: Expression, corpus: str, *, title: str = "", jurisdiction: str | None = None,
                       licence: str = "", attribution: str = "", work_source_url: str | None = None) -> None:
        """Insert an expression with its provisions. Raises StoreError on any rule violation."""
        if corpus not in CORPORA:
            raise StoreError(f"unknown corpus {corpus!r}")
        try:
            validate_expression(expr)
        except ValueError as exc:
            raise StoreError(str(exc)) from exc
        if (corpus == "synthetic") != bool(expr.synthetic):
            raise StoreError(f"{expr.expression_id}: synthetic flag and corpus {corpus!r} disagree")
        if (corpus == "synthetic") != expr.work_id.startswith(SYNTHETIC_PREFIX):
            raise StoreError(f"{expr.expression_id}: work_id prefix {SYNTHETIC_PREFIX!r} is required for, "
                             f"and only allowed in, corpus 'synthetic'")
        if corpus == "uk-validation" and not (licence and attribution):
            # licence/attribution are mandatory for real material; filled at first insert of the work
            existing = self._db.execute("SELECT licence, attribution FROM works WHERE work_id=?",
                                        (expr.work_id,)).fetchone()
            if not existing or not (existing["licence"] and existing["attribution"]):
                raise StoreError("uk-validation works require licence and attribution")
        if corpus == "uae" and not licence:
            existing = self._db.execute("SELECT licence FROM works WHERE work_id=?", (expr.work_id,)).fetchone()
            if not existing or not existing["licence"]:
                raise StoreError("uae works require a stated licence/permission")
        sha = hashlib.sha256("\n".join(f"{p.eid}\t{p.text}" for p in expr.provisions).encode("utf-8")).hexdigest()
        with self._lock, self._db:
            row = self._db.execute("SELECT corpus FROM works WHERE work_id=?", (expr.work_id,)).fetchone()
            if row and row["corpus"] != corpus:
                raise StoreError(f"{expr.work_id} already belongs to corpus {row['corpus']!r}")
            if not row:
                self._db.execute(
                    "INSERT INTO works(work_id, corpus, title, jurisdiction, language, source_url, licence, attribution)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (expr.work_id, corpus, title, jurisdiction or _JURISDICTION[corpus], expr.language,
                     work_source_url or expr.source_url, licence, attribution))
            try:
                self._db.execute(
                    "INSERT INTO expressions(expression_id, work_id, valid_from, effective_status, issue_date,"
                    " source_url, retrieved_at, content_sha256, synthetic, corpus) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (expr.expression_id, expr.work_id, _iso(expr.valid_from), expr.effective_status,
                     _iso(expr.issue_date), expr.source_url, expr.retrieved_at, sha, int(expr.synthetic), corpus))
            except sqlite3.IntegrityError as exc:
                raise StoreError(f"cannot insert expression {expr.work_id}/{expr.expression_id}: {exc}") from exc
            for p in expr.provisions:
                src = getattr(p, "source_url", None) or expr.source_url
                ret = getattr(p, "retrieved_at", None) or expr.retrieved_at
                if not src or not ret:
                    raise StoreError(f"{p.eid}: provision requires source_url and retrieved_at")
                norm = p.text_norm or normalize(p.text)
                cur = self._db.execute(
                    "INSERT INTO provisions(eid, expression_id, kind, number, bis, parent, heading, text, text_norm,"
                    " source_url, retrieved_at, work_id, corpus) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (p.eid, expr.expression_id, p.kind, p.number, p.bis, p.parent, p.heading, p.text, norm,
                     src, ret, expr.work_id, corpus))
                self._db.execute("INSERT INTO provisions_fts(rowid, text_norm) VALUES (?,?)", (cur.lastrowid, norm))

    def _work_corpus(self, work_id: str) -> str:
        r = self._db.execute("SELECT corpus FROM works WHERE work_id=?", (work_id,)).fetchone()
        if not r:
            raise StoreError(f"unknown work {work_id!r}")
        return r["corpus"]

    def add_changes(self, work_id: str, from_expression: str, to_expression: str, changes: Iterable[Any]) -> int:
        """Store diff Change objects (or dicts). Returns the number of rows written."""
        n = 0
        with self._lock, self._db:
            corpus = self._work_corpus(work_id)
            for c in changes:
                d = asdict(c) if is_dataclass(c) else dict(c)
                words = d.get("words")
                if words is None:
                    words = json.loads(d["words_json"]) if d.get("words_json") else []
                n += 1
                cid = d.get("change_id") or f"{work_id}|{from_expression}|{to_expression}|{n}"
                try:
                    self._db.execute(
                        "INSERT INTO changes(change_id, work_id, from_expression, to_expression, kind, a_eid, b_eid,"
                        " confidence, score, renumbered, amending_work_id, words_json, corpus)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, work_id, from_expression, to_expression, d["kind"], d.get("a_eid"), d.get("b_eid"),
                         d.get("confidence"), d.get("score"), int(bool(d.get("renumbered"))),
                         d.get("amending_work_id"), json.dumps(words, ensure_ascii=False), corpus))
                except sqlite3.IntegrityError as exc:
                    raise StoreError(f"cannot insert change {cid}: {exc}") from exc
        return n

    def add_amendment_events(self, events: Iterable[dict]) -> int:
        """Events need target_work_id, op, source_url, retrieved_at (provenance is mandatory)."""
        n = 0
        with self._lock, self._db:
            for e in events:
                for k in ("source_url", "retrieved_at", "target_work_id", "op"):
                    if not e.get(k):
                        raise StoreError(f"amendment event missing {k}")
                corpus = self._work_corpus(e["target_work_id"])
                eid = e.get("event_id") or hashlib.sha1(json.dumps(
                    [e["target_work_id"], e.get("amending_work_id"), e["op"], e.get("target_eid"),
                     _iso(e.get("effective_date"))], default=str).encode()).hexdigest()[:16]
                try:
                    self._db.execute(
                        "INSERT INTO amendment_events(event_id, target_work_id, amending_work_id, op, target_eid,"
                        " effective_date, effective_status, source_url, retrieved_at, evidence, corpus)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (eid, e["target_work_id"], e.get("amending_work_id"), e["op"], e.get("target_eid"),
                         _iso(e.get("effective_date")), e.get("effective_status", "unknown"), e["source_url"],
                         e["retrieved_at"], e.get("evidence", ""), corpus))
                except sqlite3.IntegrityError as exc:
                    raise StoreError(f"cannot insert amendment event {eid}: {exc}") from exc
                n += 1
        return n

    # ------------------------------------------------------------------- reads
    def get_expression(self, work_id: str, expression_id: str, corpus: str | None = None) -> Expression | None:
        """Rebuild an Expression. If ``corpus`` is given the work must be visible in that view."""
        with self._lock:
            r = self._db.execute(
                "SELECT e.*, w.language FROM expressions e JOIN works w ON w.work_id=e.work_id"
                " WHERE e.work_id=? AND e.expression_id=?", (work_id, expression_id)).fetchone()
            if not r or (corpus and r["corpus"] not in resolve_corpora(corpus)):
                return None
            ex = Expression(
                work_id=work_id, expression_id=expression_id, source_url=r["source_url"],
                retrieved_at=r["retrieved_at"], language=r["language"],
                valid_from=date.fromisoformat(r["valid_from"]) if r["valid_from"] else None,
                effective_status=r["effective_status"],
                issue_date=date.fromisoformat(r["issue_date"]) if r["issue_date"] else None,
                synthetic=bool(r["synthetic"]))
            for p in self._db.execute(
                    "SELECT * FROM provisions WHERE work_id=? AND expression_id=? ORDER BY rowid",
                    (work_id, expression_id)):
                ex.provisions.append(Provision(eid=p["eid"], kind=p["kind"], number=p["number"], bis=p["bis"],
                                               parent=p["parent"], text=p["text"], text_norm=p["text_norm"],
                                               heading=p["heading"]))
            return ex

    def list_works(self, corpus: str = "uae") -> list[dict]:
        cs = resolve_corpora(corpus)
        q = ",".join("?" * len(cs))
        with self._lock:
            rows = self._db.execute(
                f"SELECT w.*, (SELECT COUNT(*) FROM expressions e WHERE e.work_id=w.work_id) AS versions"
                f" FROM works w WHERE w.corpus IN ({q}) ORDER BY w.work_id", cs).fetchall()
        return [{**dict(r), "synthetic": r["corpus"] == "synthetic"} for r in rows]

    def list_expressions(self, work_id: str, corpus: str) -> list[dict]:
        cs = resolve_corpora(corpus)
        q = ",".join("?" * len(cs))
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM expressions WHERE work_id=? AND corpus IN ({q}) ORDER BY valid_from, expression_id",
                (work_id, *cs)).fetchall()
        return [dict(r) for r in rows]

    def list_changes(self, work_id: str, from_expression: str, to_expression: str, corpus: str) -> list[dict]:
        cs = resolve_corpora(corpus)
        q = ",".join("?" * len(cs))
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM changes WHERE work_id=? AND from_expression=? AND to_expression=? AND corpus IN ({q})"
                f" ORDER BY change_id", (work_id, from_expression, to_expression, *cs)).fetchall()
        return [{**dict(r), "words": json.loads(r["words_json"] or "[]")} for r in rows]

    def as_of(self, work_id: str, on: date, corpus: str = "uae") -> PointInTime:
        """Point-in-time lookup via taadeel.temporal. Raises LookupError if the work is not in that corpus view."""
        exprs = self.list_expressions(work_id, corpus)
        if not exprs:
            raise LookupError(f"work {work_id!r} not found in corpus view {corpus!r}")
        vs = [Version(e["expression_id"], date.fromisoformat(e["valid_from"]) if e["valid_from"] else None,
                      e["effective_status"], date.fromisoformat(e["issue_date"]) if e["issue_date"] else None)
              for e in exprs]
        return _as_of(vs, on)

    def corpus_counts(self) -> dict[str, dict[str, int]]:
        out = {c: {"works": 0, "expressions": 0, "provisions": 0, "amendment_events": 0, "changes": 0}
               for c in CORPORA}
        with self._lock:
            for table, key in (("works", "works"), ("expressions", "expressions"), ("provisions", "provisions"),
                               ("amendment_events", "amendment_events"), ("changes", "changes")):
                for r in self._db.execute(f"SELECT corpus, COUNT(*) n FROM {table} GROUP BY corpus"):
                    out[r["corpus"]][key] = r["n"]
        return out

    def search(self, query: str, corpus: str = "uae", limit: int = 20, lang: str | None = None) -> list[dict]:
        """FTS5 search over normalized text. Results carry the ORIGINAL text, source_url and retrieved_at.

        All query terms must match (AND). If nothing matches exactly, terms are retried as prefixes, then with or
        without the Arabic definite article.
        """
        tokens = query_tokens(query)
        if not tokens:
            return []
        cs = resolve_corpora(corpus)
        limit = max(1, min(int(limit), 100))
        q = ",".join("?" * len(cs))
        sql = (f"SELECT p.*, w.title, w.language, w.licence, w.attribution, e.valid_from, bm25(provisions_fts) AS rank"
               f" FROM provisions_fts f JOIN provisions p ON p.rowid=f.rowid"
               f" JOIN works w ON w.work_id=p.work_id JOIN expressions e ON e.work_id=p.work_id AND e.expression_id=p.expression_id"
               f" WHERE provisions_fts MATCH ? AND p.corpus IN ({q})"
               f" AND length(p.source_url) > 0 AND length(p.retrieved_at) > 0"
               + (" AND w.language = ?" if lang else "") + " ORDER BY rank, p.work_id, p.expression_id, p.rowid LIMIT ?")
        rows: list[sqlite3.Row] = []
        for fts in (_fts_query(tokens, False), _fts_query(tokens, True), _fts_query_article(tokens)):
            args: list[Any] = [fts, *cs]
            if lang:
                args.append(lang)
            args.append(limit)
            with self._lock:
                try:
                    rows = self._db.execute(sql, args).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if rows:
                break
        results = []
        for r in rows:
            snippet, hl = make_snippet(r["text"], tokens)
            results.append({
                "corpus": r["corpus"], "synthetic": r["corpus"] == "synthetic", "work_id": r["work_id"],
                "title": r["title"], "expression_id": r["expression_id"], "valid_from": r["valid_from"],
                "eid": r["eid"], "kind": r["kind"], "number": r["number"], "bis": r["bis"],
                "heading": r["heading"], "language": r["language"], "text": r["text"], "snippet": snippet,
                "highlights": hl, "source_url": r["source_url"], "retrieved_at": r["retrieved_at"],
                "licence": r["licence"], "attribution": r["attribution"], "score": round(-r["rank"], 4),
            })
        return results

    # ------------------------------------------------------------------ export
    def export_parquet(self, out_dir: str | Path, corpus: str | None = None) -> dict:
        """Write works/provisions/changes/amendment_events .parquet plus manifest.json. Returns the manifest."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        cs = resolve_corpora(corpus) if corpus else CORPORA
        q = ",".join("?" * len(cs))
        S, I, F, B = pa.string(), pa.int64(), pa.float64(), pa.bool_()
        specs = {
            "works": ([("work_id", S), ("corpus", S), ("title", S), ("jurisdiction", S), ("language", S),
                       ("source_url", S), ("licence", S), ("attribution", S)], "work_id"),
            "provisions": ([("eid", S), ("expression_id", S), ("kind", S), ("number", I), ("bis", I), ("parent", S),
                            ("heading", S), ("text", S), ("text_norm", S), ("source_url", S), ("retrieved_at", S),
                            ("work_id", S), ("corpus", S)], "work_id, expression_id, rowid"),
            "changes": ([("change_id", S), ("work_id", S), ("from_expression", S), ("to_expression", S),
                         ("kind", S), ("a_eid", S), ("b_eid", S), ("confidence", S), ("score", F),
                         ("renumbered", B), ("amending_work_id", S), ("words_json", S), ("corpus", S)], "change_id"),
            "amendment_events": ([("event_id", S), ("target_work_id", S), ("amending_work_id", S), ("op", S),
                                  ("target_eid", S), ("effective_date", S), ("effective_status", S),
                                  ("source_url", S), ("retrieved_at", S), ("evidence", S), ("corpus", S)], "event_id"),
        }
        files: dict[str, dict] = {}
        with self._lock:
            for name, (cols, order) in specs.items():
                names = [c for c, _ in cols]
                rows = self._db.execute(
                    f"SELECT {', '.join(names)} FROM {name} WHERE corpus IN ({q}) ORDER BY {order}", cs).fetchall()
                data = {}
                for c, t in cols:
                    vals = [r[c] for r in rows]
                    if t == B:
                        vals = [bool(v) for v in vals]
                    data[c] = pa.array(vals, type=t)
                table = pa.table(data, schema=pa.schema(cols))
                path = out / f"{name}.parquet"
                pq.write_table(table, path, compression="zstd")
                files[path.name] = {"rows": table.num_rows, "bytes": path.stat().st_size,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            counts = self.corpus_counts()
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "generator": f"taadeel.store (pyarrow {pa.__version__})",
            "corpora_exported": list(cs),
            "files": files,
            "corpus_counts": {c: counts[c] for c in cs},
            "contains_synthetic": "synthetic" in cs and counts["synthetic"]["provisions"] > 0,
            "disclaimer": DISCLAIMER,
        }
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                                           encoding="utf-8")
        return manifest


def build_demo_store() -> Store:
    """Synthetic demo pair (same as api.py) in corpus 'synthetic', with its diff and amendment events."""
    from .align import align
    from .diff import diff
    from .synthetic import make_pair

    p = make_pair(7, n=12, n_replace=2, n_repeal=1, n_insert=2, n_clarify=1, bis_inserts=1)
    p.b.valid_from = date(2024, 1, 1)
    s = Store(":memory:")
    for ex in (p.a, p.b):
        s.add_expression(ex, "synthetic", title="Synthetic test law 1 (not legislation)", licence="CC0-1.0",
                         attribution="Generated by taadeel.synthetic; random text with no legal meaning.")
    amending = "synthetic/amend/1"
    changes = diff(p.a, p.b, align(p.a, p.b), amending_work_id=amending)
    s.add_changes(p.a.work_id, p.a.expression_id, p.b.expression_id, changes)
    s.add_amendment_events([{
        "target_work_id": p.a.work_id, "amending_work_id": amending, "op": c.kind,
        "target_eid": c.a_eid or c.b_eid, "effective_date": p.b.valid_from, "effective_status": "known",
        "source_url": p.b.source_url, "retrieved_at": p.b.retrieved_at,
        "evidence": "synthetic fixture; derived from generated diff"} for c in changes])
    return s
