"""Command line entry point: ``taadeel diff``, ``taadeel serve``, ``taadeel baselines``, ``taadeel report``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .compare import CompareError, compare_texts

SYMBOL = {"inserted": "+", "repealed": "-", "replaced": "~", "renumbered": ">", "clarified": "="}


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"taadeel: cannot read {path}: {exc}") from exc


def cmd_diff(args: argparse.Namespace) -> int:
    try:
        res = compare_texts(_read(args.old), _read(args.new), args.lang)
    except CompareError as exc:
        print(f"taadeel: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    print(f"{res['articles_old']} articles in {args.old}, {res['articles_new']} in {args.new}; "
          f"{res['aligned']} aligned, {res['low_confidence']} low confidence")
    for c in res["changes"]:
        ref = c["b_eid"] or c["a_eid"]
        flag = "  (low confidence)" if c["confidence"] == "low" and c["kind"] not in ("inserted", "repealed") else ""
        print(f"{SYMBOL[c['kind']]} {c['kind']:<10} {ref}{flag}")
    print("counts:", ", ".join(f"{k} {v}" for k, v in sorted(res["counts"].items())) or "no changes")
    print("Research and navigation tool, not legal advice.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("taadeel.api:app", host=args.host, port=args.port)
    return 0


def cmd_baselines(_: argparse.Namespace) -> int:
    from . import baselines

    baselines.main()
    return 0


def cmd_report(_: argparse.Namespace) -> int:
    from . import report

    report.main()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="taadeel", description="Legislation change tracker (not legal advice).")
    ap.add_argument("--version", action="version", version=f"taadeel {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff", help="article level diff of two plain text versions of a law")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--lang", choices=["ar", "en"], help="default: detected from the text")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=cmd_diff)
    s = sub.add_parser("serve", help="run the API and web page")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)
    sub.add_parser("baselines", help="rerun the baseline comparison").set_defaults(fn=cmd_baselines)
    sub.add_parser("report", help="regenerate README results and generated docs").set_defaults(fn=cmd_report)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
