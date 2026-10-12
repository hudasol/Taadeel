"""Hand check material for the UK validation (the verdicts are written by the AI agent, not a lawyer).

Produces results/uk_handcheck.json: (a) a seeded sample of effects whose class agrees with the snapshots
(word level diff shown so a reader can compare it with the effect wording), (b) every recorded effect that
still shows no snapshot change on its date, with the dates at which that section does change.
Seed 20261012. The first run of the evaluation also had a seeded draw of 20 disagreeing effects
(results/uk_handcheck_run1_sample.json); reading it exposed two defects in the effects reader (see
docs/VALIDATION_UK.md).
"""
from __future__ import annotations

import difflib
import json
import random
from datetime import date, timedelta

from . import uk_validate as V
from .uk_fetch import ROOT, plan_snapshots

SEED = 20261012
CLS = {"section_inserted": "inserted", "section_repealed": "repealed",
       "section_substituted": "replaced", "text_modified": "replaced"}


def run() -> dict:
    corp = V.Corpus(V.make_ingestor())
    rows = []
    for act in V.ACTS:
        effs = V.effects_for(corp.ing, act)
        for d, a, b in V.one_day_windows(corp, act, effs):
            tmap = {(x or y): v for (x, y), v in V.truth_changes(a, b).items()}
            for e in effs:
                if e.status == "ok" and e.date == d and e.kind != "other":
                    for sid in e.sections:
                        rows.append(dict(act=act, date=str(d), sid=sid, effect_class=CLS[e.kind],
                                         snapshot_class=tmap.get(sid, "none"), effect=e.raw[:220], _a=a, _b=b))
    rng = random.Random(SEED)
    good = [r for r in rows if r["effect_class"] == r["snapshot_class"]]
    bad = [r for r in rows if r["effect_class"] != r["snapshot_class"]]
    agree = []
    for r in rng.sample(good, 10):
        ta, tb = V._texts(r["_a"]).get(r["sid"], ""), V._texts(r["_b"]).get(r["sid"], "")
        sm = difflib.SequenceMatcher(None, ta.split(), tb.split(), autojunk=False)
        ops = [[t, " ".join(ta.split()[i1:i2])[:60], " ".join(tb.split()[j1:j2])[:80]]
               for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"][:3]
        agree.append({k: v for k, v in r.items() if not k.startswith("_")} | {"word_ops": ops})
    dis = []
    for r in bad:
        pts, prev = [], None
        for dd in sorted(plan_snapshots(r["act"], corp.ing)):
            e = corp.snap(r["act"], dd)
            if e is None:
                continue
            t = V._texts(e).get(r["sid"])
            if prev is not None and t != prev:
                pts.append(dd)
            prev = t
        dis.append({k: v for k, v in r.items() if not k.startswith("_")} | {"section_changes_at": pts})
    return {"seed": SEED, "effects_in_one_day_windows": len(rows), "agreeing_sample": agree,
            "disagreements": dis, "verdicts": "see docs/VALIDATION_UK.md; made by the AI agent"}


if __name__ == "__main__":
    out = run()
    (ROOT / "results" / "uk_handcheck.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str),
                                                        encoding="utf-8")
    print(len(out["agreeing_sample"]), len(out["disagreements"]))
