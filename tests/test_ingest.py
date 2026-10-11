import pytest

from taadeel.ingest import Blocked, Ingestor, NotPermitted, Response, load_sources

SRC = {
    "ok.example": {"mode": "permitted", "min_delay_seconds": 10, "permission_evidence": "letter 2026-10-12"},
    "link.example": {"mode": "link_only", "min_delay_seconds": 10},
    "noev.example": {"mode": "permitted", "min_delay_seconds": 10, "permission_evidence": ""},
}


class FakeNet:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url, headers):
        self.calls.append(url)
        return self.pages.get(url, Response(404, b"", {}))


def mk(tmp_path, pages):
    net = FakeNet(pages)
    t = [0.0]
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        t[0] += s

    ing = Ingestor(SRC, tmp_path, net, sleep=sleep, clock=lambda: t[0])
    return ing, net, sleeps


def test_real_registry_defaults_to_link_only(tmp_path):
    reg = load_sources("sources.toml")
    assert all(s["mode"] != "permitted" for s in reg.values())
    ing = Ingestor(reg, tmp_path, FakeNet({}))
    with pytest.raises(NotPermitted):
        ing.fetch("https://uaelegislation.gov.ae/en/legislations/1541")


def test_no_network_call_for_non_permitted(tmp_path):
    ing, net, _ = mk(tmp_path, {})
    for u in ("https://link.example/x", "https://unknown.example/x", "https://noev.example/x"):
        with pytest.raises(NotPermitted):
            ing.fetch(u)
    assert net.calls == []


def test_robots_disallow_respected(tmp_path):
    pages = {"https://ok.example/robots.txt": Response(200, b"User-agent: *\nDisallow: /private/\n", {}),
             "https://ok.example/private/a": Response(200, b"x", {})}
    ing, net, _ = mk(tmp_path, pages)
    with pytest.raises(NotPermitted):
        ing.fetch("https://ok.example/private/a")
    assert "https://ok.example/private/a" not in net.calls


def test_unreadable_robots_fails_closed(tmp_path):
    pages = {"https://ok.example/robots.txt": Response(500, b"", {})}
    ing, _, _ = mk(tmp_path, pages)
    with pytest.raises(NotPermitted):
        ing.fetch("https://ok.example/a")


def test_snapshot_hash_resume_and_rate_limit(tmp_path):
    pages = {"https://ok.example/robots.txt": Response(404, b"", {}),
             "https://ok.example/a": Response(200, b"hello", {"Content-Type": "text/html"}),
             "https://ok.example/b": Response(200, b"world", {"Content-Type": "text/html"})}
    ing, net, sleeps = mk(tmp_path, pages)
    s1 = ing.fetch("https://ok.example/a")
    ing.fetch("https://ok.example/b")
    assert sleeps and sleeps[0] == pytest.approx(10)     # polite gap between requests
    assert s1.sha256 and s1.retrieved_at and s1.status == 200
    again = ing.fetch("https://ok.example/a")             # resume: no refetch
    assert again.sha256 == s1.sha256
    assert net.calls.count("https://ok.example/a") == 1


def test_block_is_recorded_not_bypassed(tmp_path):
    pages = {"https://ok.example/robots.txt": Response(404, b"", {}),
             "https://ok.example/a": Response(403, b"challenge", {})}
    ing, net, _ = mk(tmp_path, pages)
    with pytest.raises(Blocked):
        ing.fetch("https://ok.example/a")
    assert net.calls.count("https://ok.example/a") == 1
    assert ing.latest("https://ok.example/a") is None
