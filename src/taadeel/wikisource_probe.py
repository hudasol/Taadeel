"""Probe the parser on ONE real Arabic legal text held only locally; commit counts, never the text.

Source: Arabic Wikisource, "القانون الاتحادي رقم 7 لسنة 2002 في شأن حقوق المؤلف والحقوق المجاورة"
(UAE), page id 56374, revision (oldid) 137670, retrieved 2026-10-16 with the identifying user agent
(robots.txt read first; /w/ and /api/ are disallowed there, so only the plain /wiki/ page was read).
The page carries no explicit licence template; the site footer states CC BY-SA 4.0 for texts. The
text of Article 3 of that law excludes official documents such as texts of laws from protection, but
whether that law is still in force was not verified from a retrieved source. The page is therefore
NOT treated as clearly reusable: no wording from it is committed. Anyone can reproduce the counts by
saving https://ar.wikisource.org/w/index.php?oldid=137670 locally and running

    python -m taadeel.wikisource_probe PATH_TO_SAVED_HTML

Output: results/arabic_wikisource_probe.json (counts only). This is a transcription on a wiki, not
the official Gazette text, and one law is not a validation set; treat the result as a smoke test.
"""
from __future__ import annotations

import hashlib
import html
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

from . import align_v2
from .align import align as align_v1
from .heldout import RESULTS
from .model import Expression, Provision
from .normalize_v2 import preclean
from .parse import parse_structure

OLDID = 137670
_BLOCK = re.compile(r"</?(?:p|h[1-6]|dd|dt|li|div|br|tr)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_FORMAT = re.compile("[​-‏‪-‮⁦-⁩؜﻿­]")
_DIAC = re.compile("[ً-ٰٟ]")


def html_to_lines(raw: str) -> list[str]:
    start = raw.find('class="mw-content-rtl mw-parser-output"')
    body = raw[raw.find(">", start) + 1:raw.find('class="printfooter"')]
    body = re.sub(r"<(style|script)\b.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r'<div class="[^"]*(?:ws-header|noprint)[^"]*".*?</div>', " ", body, flags=re.S)
    text = html.unescape(_TAG.sub(" ", _BLOCK.sub("\n", body)))
    return [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n") if ln.strip()]


def _expr(lines: list[str]) -> Expression:
    e = Expression(work_id="local/wikisource-probe", expression_id=f"oldid-{OLDID}",
                   source_url=f"https://ar.wikisource.org/w/index.php?oldid={OLDID}", retrieved_at="2026-10-16")
    return parse_structure("\n".join(lines), e)


def _renumber_variant(e: Expression, rng: random.Random) -> tuple[Expression, dict[str, str]]:
    arts = e.articles()
    k = rng.randrange(1, len(arts) - 1)
    out, truth = [], {}
    for i, p in enumerate(arts):
        if i == k:
            out.append(Provision(eid="NEW", kind="article", number=p.number, text="نص مضاف لاختبار إعادة الترقيم فقط"))
        q = Provision(eid=p.eid + "~", kind="article", number=(p.number or 0) + (1 if i >= k else 0), bis=p.bis, text=p.text)
        out.append(q)
        truth[p.eid] = q.eid
    b = Expression(work_id=e.work_id, expression_id=e.expression_id + "~", source_url=e.source_url,
                   retrieved_at=e.retrieved_at, provisions=out)
    return b, truth


def probe(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.search(r'"wgRevisionId":(\d+)', raw)
    lines = html_to_lines(raw)
    text = "\n".join(lines)
    out = {"source": f"https://ar.wikisource.org/w/index.php?oldid={OLDID}", "revision_in_file": int(m.group(1)) if m else None,
           "html_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
           "note": "Counts only; no wording committed. One wiki transcription, not the official Gazette text.",
           "profile": {"lines": len(lines), "chars": len(text),
                       "diacritic_marks": len(_DIAC.findall(text)), "tatweel": text.count("ـ"),
                       "format_chars": len(_FORMAT.findall(text)),
                       "arabic_indic_digits": sum(text.count(d) for d in "٠١٢٣٤٥٦٧٨٩"),
                       "ascii_digits": sum(ch.isdigit() and ch.isascii() for ch in text),
                       "latin_letters": sum(ch.isascii() and ch.isalpha() for ch in text),
                       "lines_starting_with_article_word": sum(1 for ln in lines if ln.startswith(("المادة", "مادة")))}}
    for name, ls in (("v1_parser", lines), ("v1_parser_after_v2_preclean", [preclean(x) for x in lines])):
        e = _expr(ls)
        nums = [p.number for p in e.articles()]
        kinds = Counter(p.kind for p in e.provisions)
        expected = list(range(1, max(nums) + 1)) if nums else []
        out[name] = {"articles": len(nums), "max_number": max(nums) if nums else None,
                     "missing_numbers": len(set(expected) - set(nums)), "duplicate_numbers": len(nums) - len(set(nums)),
                     "in_order": nums == sorted(nums), "kinds": dict(kinds),
                     "empty_article_bodies": sum(1 for p in e.articles() if not p.text.strip())}
    e = _expr(lines)
    rng = random.Random(20261016)
    ren = {"v1": Counter(), "v2": Counter()}
    for _ in range(5):
        b, truth = _renumber_variant(e, rng)
        for ver, fn in (("v1", lambda x, y: align_v1(x, y)), ("v2", lambda x, y: align_v2.align(x, y))):
            pm = {p.a_eid: p.b_eid for p in fn(e, b).pairs}
            ren[ver]["articles"] += len(truth)
            ren[ver]["correct"] += sum(pm.get(a) == bb for a, bb in truth.items())
    out["renumbering_variant"] = {"note": "real text, synthetic renumbering (one inserted article, later numbers +1), 5 runs",
                                  **{k: dict(v) for k, v in ren.items()}}
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m taadeel.wikisource_probe PATH_TO_SAVED_HTML")
    r = probe(Path(sys.argv[1]))
    (RESULTS / "arabic_wikisource_probe.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in r.items() if k != "profile"}, indent=1))
