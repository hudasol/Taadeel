"""Polite, permission-gated, resumable ingestion with versioned snapshots.

Rules enforced in code:
* Only hosts marked ``permitted`` in sources.toml are fetched; everything else
  raises ``NotPermitted`` before any network call.
* robots.txt is consulted per host (fail closed if unreadable).
* A minimum delay between requests per host is enforced.
* A blocked response (403/429/bot challenge) is recorded and NOT retried via
  other routes (no mirrors, caches or header tricks).
* Snapshots are content-addressed and append-only; re-running resumes by
  skipping URLs whose latest snapshot is already stored.
"""
from __future__ import annotations

import hashlib
import json
import time
import tomllib
import urllib.robotparser
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "TaadeelBot/0.1 (+https://github.com/hudasol/Taadeel; research; contact: hudamueen2407@gmail.com)"


class NotPermitted(Exception):
    pass


class Blocked(Exception):
    pass


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict[str, str]
    final_url: str = ""


Fetcher = Callable[[str, dict[str, str]], Response]


@dataclass
class Snapshot:
    url: str
    retrieved_at: str
    status: int
    sha256: str
    content_type: str
    path: str
    robots_allowed: bool
    user_agent: str
    final_url: str = ""


def load_sources(path: str | Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f).get("sources", {})


def default_fetcher(url: str, headers: dict[str, str]) -> Response:  # pragma: no cover - network
    import urllib.request

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return Response(r.status, r.read(), dict(r.headers), r.geturl())
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read() or b"", dict(e.headers or {}), url)


class Ingestor:
    def __init__(self, sources: dict, store: str | Path, fetcher: Fetcher = default_fetcher,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.sources = sources
        self.store = Path(store)
        self.store.mkdir(parents=True, exist_ok=True)
        self.fetcher, self.sleep, self.clock = fetcher, sleep, clock
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._crawl_delay: dict[str, float] = {}
        self.index_path = self.store / "index.jsonl"

    # -- gating ---------------------------------------------------------
    def _source(self, url: str) -> tuple[str, dict]:
        host = urlparse(url).hostname or ""
        src = self.sources.get(host)
        if src is None:
            raise NotPermitted(f"{host}: not in sources.toml")
        if src.get("mode") != "permitted":
            raise NotPermitted(f"{host}: mode is {src.get('mode')!r}, not 'permitted' (see docs/DATA_SOURCES.md)")
        if not src.get("permission_evidence"):
            raise NotPermitted(f"{host}: permitted without permission_evidence")
        for suf in src.get("deny_suffixes", []):
            if urlparse(url).path.endswith(suf):
                raise NotPermitted(f"{url}: suffix {suf} is excluded for this source")
        return host, src

    def _robots_ok(self, host: str, url: str) -> bool:
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.fetcher(f"https://{host}/robots.txt", {"User-Agent": USER_AGENT})
                if r.status == 200:
                    rp.parse(r.body.decode("utf-8", "replace").splitlines())
                elif r.status in (404, 410):
                    rp.parse([])            # no robots file: nothing disallowed
                else:
                    rp = None               # unreadable: fail closed
            except Exception:
                rp = None
            self._robots[host] = rp
            cd = rp.crawl_delay(USER_AGENT) if rp else None
            if cd:
                self._crawl_delay[host] = float(cd)
        rp = self._robots[host]
        return bool(rp and rp.can_fetch(USER_AGENT, url))

    def _wait(self, host: str, delay: float) -> None:
        last = self._last.get(host)
        if last is not None:
            gap = delay - (self.clock() - last)
            if gap > 0:
                self.sleep(gap)
        self._last[host] = self.clock()

    # -- snapshots ------------------------------------------------------
    def latest(self, url: str) -> Snapshot | None:
        if not self.index_path.exists():
            return None
        found = None
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            if d["url"] == url and d["status"] == 200:
                found = Snapshot(**d)
        return found

    def fetch(self, url: str, *, resume: bool = True) -> Snapshot:
        host, src = self._source(url)
        if resume and (prev := self.latest(url)):
            return prev
        if not self._robots_ok(host, url):
            raise NotPermitted(f"{url}: disallowed or unreadable robots.txt")
        self._wait(host, max(float(src.get("min_delay_seconds", 10)), self._crawl_delay.get(host, 0.0)))
        r = self.fetcher(url, {"User-Agent": USER_AGENT, "Accept-Language": "ar,en;q=0.5"})
        now = datetime.now(UTC).isoformat(timespec="seconds")
        digest = hashlib.sha256(r.body).hexdigest()
        path = ""
        if r.status == 200:
            p = self.store / "blobs" / f"{digest}.bin"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(r.body)
            path = str(p)
        snap = Snapshot(url, now, r.status, digest, r.headers.get("Content-Type", ""), path, True, USER_AGENT,
                        r.final_url or url)
        with open(self.index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(snap), ensure_ascii=False) + "\n")
        if r.status in (403, 429, 503):
            raise Blocked(f"{url}: HTTP {r.status}; recorded, not retrying by other routes")
        return snap
