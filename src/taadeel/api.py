"""Read-only API. Not legal advice.

Real-data collection is empty until a source with permitted use exists
(docs/DATA_SOURCES.md). Demo data is synthetic and every response says so.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .align import align
from .diff import diff
from .model import Expression
from .synthetic import make_pair
from .temporal import Version, as_of

DISCLAIMER = ("Research and navigation tool, not legal advice. The official Arabic text published by the "
              "competent UAE authority prevails.")

app = FastAPI(title="Taadeel API", version="0.1.0", description=DISCLAIMER)


def _demo() -> dict[str, list[Expression]]:
    p = make_pair(7, n=12, n_replace=2, n_repeal=1, n_insert=2, n_clarify=1, bis_inserts=1)
    p.b.valid_from = date(2024, 1, 1)
    return {"synthetic/law/1": [p.a, p.b]}


WORKS: dict[str, list[Expression]] = _demo()
REAL_WORKS: dict[str, list[Expression]] = {}      # intentionally empty (no permitted source yet)


def _store(real: bool) -> dict[str, list[Expression]]:
    return REAL_WORKS if real else WORKS


def _wrap(data: dict, synthetic: bool) -> dict:
    return {"disclaimer": DISCLAIMER, "synthetic": synthetic, **data}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "real_works": len(REAL_WORKS), "synthetic_works": len(WORKS), "disclaimer": DISCLAIMER}


@app.get("/api/works")
def works(real: bool = False) -> dict:
    items = [{"work_id": k, "versions": len(v), "synthetic": v[0].synthetic} for k, v in _store(real).items()]
    note = "No real legislation is loaded: no source currently permits collection (see docs/DATA_SOURCES.md)." if real and not items else ""
    return _wrap({"works": items, "note": note}, synthetic=not real)


def _get(work_id: str, real: bool) -> list[Expression]:
    v = _store(real).get(work_id)
    if not v:
        raise HTTPException(404, "unknown work")
    return v


@app.get("/api/works/{work_id:path}/versions")
def versions(work_id: str, real: bool = False) -> dict:
    v = _get(work_id, real)
    out = [{"expression_id": e.expression_id, "valid_from": e.valid_from, "effective_status": e.effective_status,
            "source_url": e.source_url, "retrieved_at": e.retrieved_at, "synthetic": e.synthetic} for e in v]
    return _wrap({"work_id": work_id, "versions": out}, synthetic=v[0].synthetic)


@app.get("/api/diff")
def api_diff(work: str, a: str, b: str, real: bool = False) -> dict:
    v = {e.expression_id: e for e in _get(work, real)}
    if a not in v or b not in v:
        raise HTTPException(404, "unknown version")
    res = align(v[a], v[b])
    texts = {p.eid: p.text for e in (v[a], v[b]) for p in e.articles()}
    changes = [{**asdict(c), "a_text": texts.get(c.a_eid or ""), "b_text": texts.get(c.b_eid or ""),
                "source_url": v[b].source_url, "retrieved_at": v[b].retrieved_at} for c in diff(v[a], v[b], res)]
    return _wrap({"work_id": work, "from": a, "to": b, "changes": changes,
                  "unaligned_a": res.unaligned_a, "unaligned_b": res.unaligned_b}, synthetic=v[a].synthetic)


@app.get("/api/as-of")
def api_as_of(work: str, on: date = Query(..., alias="date"), real: bool = False) -> dict:
    exprs = _get(work, real)
    r = as_of([Version(e.expression_id, e.valid_from, e.effective_status, e.issue_date) for e in exprs], on)
    chosen = next((e for e in exprs if e.expression_id == r.version_id), None)
    arts = [{"eid": p.eid, "number": p.number, "bis": p.bis, "text": p.text,
             "source_url": chosen.source_url, "retrieved_at": chosen.retrieved_at} for p in chosen.articles()] if chosen else []
    return _wrap({"work_id": work, "as_of": on, "version_id": r.version_id, "certainty": r.certainty,
                  "candidates": r.candidates, "note": r.note, "articles": arts}, synthetic=exprs[0].synthetic)


@app.exception_handler(HTTPException)
async def _http(_, exc: HTTPException):
    return JSONResponse({"error": exc.detail, "disclaimer": DISCLAIMER}, status_code=exc.status_code)


_WEB = Path(__file__).resolve().parents[2] / "web"
if _WEB.exists():
    app.mount("/static", StaticFiles(directory=_WEB), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_WEB / "index.html")
