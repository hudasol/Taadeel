"""Validate the locked engine on real UK amendment histories (England & Wales view).

Real English UK legislation, Open Government Licence v3.0. This validates the engine on English
text only and says nothing about UAE law. The engine files are NOT modified or tuned here.

Ground truths (independent of the engine, which never sees section ids):
* alignment and change class: the stable section id (eid) in two dated snapshots served by
  legislation.gov.uk (identity = same eid; change = text differs; inserted/repealed = eid only in one side).
* recorded effects: the Commentary Type F footnotes of the current text, with their parsed dates.
* point in time: independently fetched snapshots on the day before and on each effect date.

Labels such as 3ZA are mapped to (number, bis) injectively with a bijective base 26 value, so the
locked model and aligner are used unchanged.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import clml
from .align import align
from .diff import diff
from .ingest import Ingestor
from .labels import suffix_value
from .model import Expression, Provision
from .temporal import Version, as_of
from .uk_fetch import ROOT, make_ingestor, plan_snapshots, snapshot_dates, url_at, url_current

ACTS = ["ukpga/1990/18", "ukpga/2015/30", "ukpga/1968/60", "ukpga/1998/42",
        "ukpga/1989/6", "ukpga/1997/40", "ukpga/1971/38"]
OUT = ROOT / "results" / "uk_validation.json"
ADV_SEED = 424242


def to_expression(act: str, d: str, secs: list[clml.Section], url: str, retrieved: str) -> Expression:
    provs = [Provision(eid=s.eid, kind="article", number=s.number, bis=suffix_value(s.suffix), text=s.text)
             for s in secs if not s.placeholder]
    return Expression(work_id=f"uk/{act}", expression_id=f"uk/{act}@{d}", source_url=url,
                      retrieved_at=retrieved, language="en", valid_from=date.fromisoformat(d),
                      effective_status="known", synthetic=False, provisions=provs)


class Corpus:
    def __init__(self, ing: Ingestor):
        self.ing = ing
        self.cache: dict[tuple[str, str], Expression | None] = {}

    def snap(self, act: str, d: str) -> Expression | None:
        k = (act, d)
        if k not in self.cache:
            u = url_at(act, d)
            s = self.ing.latest(u)
            if s is not None:
                ids = [x.eid for x in clml.parse_sections(clml.load(s.path)) if not x.placeholder]
                if len(ids) != len(set(ids)):
                    raise ValueError(f"duplicate section ids in {u}")
            self.cache[k] = None if s is None else to_expression(
                act, d, clml.parse_sections(clml.load(s.path)), u, s.retrieved_at)
        return self.cache[k]


def first_snapshot(corp: Corpus, act: str) -> str | None:
    """Earliest planned date that exists (Acts later than the 1991 base 404 on the base date)."""
    for d in sorted(plan_snapshots(act, corp.ing)):
        if corp.snap(act, d) is not None:
            return d
    return None


def effects_for(ing: Ingestor, act: str) -> list[clml.Effect]:
    s = ing.latest(url_current(act))
    return clml.parse_effects(clml.load(s.path))


def _texts(e: Expression) -> dict[str, str]:
    return {p.eid: p.text for p in e.provisions}


def truth_changes(a: Expression, b: Expression) -> dict[tuple, str]:
    ta, tb = _texts(a), _texts(b)
    out: dict[tuple, str] = {}
    for eid in sorted(ta.keys() | tb.keys()):
        if eid in ta and eid in tb:
            if ta[eid] != tb[eid]:
                out[(eid, eid)] = "replaced"
        elif eid in ta:
            out[(eid, None)] = "repealed"
        else:
            out[(None, eid)] = "inserted"
    return out


def engine_changes(a: Expression, b: Expression):
    res = align(a, b)
    ch = diff(a, b, res)
    return res, {(c.a_eid, c.b_eid): c.kind for c in ch}


def score_pair(a: Expression, b: Expression) -> dict:
    res, pred = engine_changes(a, b)
    truth = truth_changes(a, b)
    ta, tb = _texts(a), _texts(b)
    shared = ta.keys() & tb.keys()
    pm = {p.a_eid: p.b_eid for p in res.pairs}
    correct = sum(1 for e in shared if pm.get(e) == e)
    wrong = sum(1 for e in shared if e in pm and pm[e] != e)
    missed = sum(1 for e in shared if e not in pm)
    false_match = sum(1 for x, y in pm.items() if x not in tb or y not in ta)
    low_conf = sum(1 for p in res.pairs if p.confidence == "low")
    cls: dict[str, Counter] = defaultdict(Counter)
    for k, v in truth.items():
        if pred.get(k) == v:
            cls[v]["tp"] += 1
        else:
            cls[v]["fn"] += 1
    for k, v in pred.items():
        if truth.get(k) != v:
            cls[v]["fp"] += 1
    return {"shared": len(shared), "correct": correct, "wrong": wrong, "unmatched_shared": missed,
            "false_match": false_match, "low_conf_pairs": low_conf, "n_a": len(ta), "n_b": len(tb),
            "classes": {k: dict(v) for k, v in cls.items()},
            "pred_classes": dict(Counter(pred.values())), "truth_classes": dict(Counter(truth.values()))}


def merge(rows: list[dict]) -> dict:
    tot = Counter()
    cls: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for k in ("shared", "correct", "wrong", "unmatched_shared", "false_match", "low_conf_pairs"):
            tot[k] += r[k]
        for c, d in r["classes"].items():
            cls[c].update(d)
    out = {"alignment": {
        "shared_sections": tot["shared"], "correct": tot["correct"], "wrong": tot["wrong"],
        "unmatched": tot["unmatched_shared"], "false_matches": tot["false_match"],
        "low_confidence_pairs": tot["low_conf_pairs"],
        "accuracy": round(tot["correct"] / tot["shared"], 4) if tot["shared"] else None}, "classes": {}}
    for c, d in sorted(cls.items()):
        tp, fp, fn = d.get("tp", 0), d.get("fp", 0), d.get("fn", 0)
        out["classes"][c] = {"tp": tp, "fp": fp, "fn": fn,
                             "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                             "recall": round(tp / (tp + fn), 4) if tp + fn else None}
    return out


# ---- recorded effects vs snapshots, and engine vs recorded effects -------------------------
def effect_expectations(effs: list[clml.Effect], d: date) -> dict[str, str]:
    """eid -> expected class for effects dated exactly d."""
    exp: dict[str, str] = {}
    for e in effs:
        if e.status != "ok" or e.date != d or e.kind == "other":
            continue
        cls = {"section_inserted": "inserted", "section_repealed": "repealed",
               "section_substituted": "replaced", "text_modified": "replaced"}[e.kind]
        for sid in e.sections:
            exp.setdefault(sid, cls)
    return exp


def one_day_windows(corp: Corpus, act: str, effs: list[clml.Effect]):
    for ds in snapshot_dates(act, corp.ing):
        d = date.fromisoformat(ds)
        a, b = corp.snap(act, (d - timedelta(days=1)).isoformat()), corp.snap(act, ds)
        if a is not None and b is not None:
            yield d, a, b


def eval_act(corp: Corpus, act: str) -> dict:
    effs = effects_for(corp.ing, act)
    rows, eff_rows = [], []
    rec = Counter()
    engine_vs_eff = Counter()
    for d, a, b in one_day_windows(corp, act, effs):
        rows.append(score_pair(a, b))
        truth = truth_changes(a, b)
        exp = effect_expectations(effs, d)
        tmap = {(x or y): v for (x, y), v in truth.items()}
        # recorded effects vs snapshots
        for eid, cls in exp.items():
            rec["effects_checked"] += 1
            if eid in tmap:
                rec["effects_with_snapshot_change"] += 1
                if tmap[eid] == cls:
                    rec["effects_class_agrees"] += 1
        for eid in tmap:
            rec["snapshot_changes"] += 1
            if eid in exp:
                rec["snapshot_changes_with_effect"] += 1
        # engine vs recorded effects (eid level)
        _, pred = engine_changes(a, b)
        pmap = {(x or y): v for (x, y), v in pred.items()}
        for eid, cls in exp.items():
            if pmap.get(eid) == cls:
                engine_vs_eff["tp"] += 1
            else:
                engine_vs_eff["fn"] += 1
        for eid in pmap:
            if eid not in exp:
                engine_vs_eff["fp"] += 1
        eff_rows.append((str(d), len(exp), len(tmap)))
    long = None
    dates = sorted(plan_snapshots(act, corp.ing))
    fs = first_snapshot(corp, act)
    a0 = corp.snap(act, fs) if fs else None
    b0 = corp.snap(act, dates[-1])
    if a0 is not None and b0 is not None and a0 is not b0:
        long = score_pair(a0, b0)
        long["from"], long["to"] = a0.expression_id, b0.expression_id
    return {"act": act, "windows": len(rows), "one_day": merge(rows) if rows else None,
            "recorded_effects": dict(rec), "engine_vs_recorded_effects": dict(engine_vs_eff),
            "long_gap": long, "window_detail": eff_rows}


# ---- point in time ------------------------------------------------------------------------
def same_text(a: Expression, b: Expression) -> bool:
    return _texts(a) == _texts(b)


def eval_point_in_time(corp: Corpus, act: str) -> dict:
    dates = snapshot_dates(act, corp.ing)
    base = first_snapshot(corp, act)
    if base is None:
        return {"act": act, "skipped": "no snapshot"}
    vers = [Version(f"{act}@{base}", date.fromisoformat(base), "known")]
    vers += [Version(f"{act}@{d}", date.fromisoformat(d), "known") for d in dates]
    res = Counter()
    fails = []
    for d in dates:
        dd = date.fromisoformat(d)
        for qd, expect_snap in ((dd - timedelta(days=1), (dd - timedelta(days=1)).isoformat()), (dd, d)):
            truth = corp.snap(act, expect_snap)
            if truth is None:
                res["no_snapshot"] += 1
                continue
            p = as_of(vers, qd)
            vid = (p.version_id or "").split("@")[-1]
            rep = corp.snap(act, vid) if vid else None
            kind = "prior_day" if qd < dd else "on_date"
            res["queries"] += 1
            res[f"{kind}_queries"] += 1
            if rep is not None and same_text(rep, truth):
                res["correct"] += 1
                res[f"{kind}_correct"] += 1
            else:
                res["wrong"] += 1
                res[f"{kind}_wrong"] += 1
                fails.append({"query": qd.isoformat(), "served_version": vid, "reason":
                              "text of the version served differs from the independently fetched snapshot"})
        res["boundary_pairs"] += 1
    return {"act": act, **dict(res), "failures": fails[:20]}


# ---- adversarial renumbering variant (real text, synthetic renumbering) ----------------------
def renumber_variant(a: Expression, rng: random.Random) -> tuple[Expression, dict[str, str]]:
    """Insert a new section at a random point and shift later numbers by one. Truth: eid map."""
    provs = a.provisions
    k = rng.randrange(1, max(2, len(provs) - 1))
    out, truth = [], {}
    for i, p in enumerate(provs):
        if i == k:
            donor = provs[(k + len(provs) // 2) % len(provs)]
            out.append(Provision(eid="NEW", kind="article", number=p.number, bis=0,
                                 text=donor.text + " [inserted for the renumbering test]"))
        shift = 1 if i >= k else 0
        q = Provision(eid=p.eid + "~", kind="article", number=(p.number or 0) + shift, bis=p.bis, text=p.text)
        out.append(q)
        truth[p.eid] = q.eid
    b = Expression(work_id=a.work_id, expression_id=a.expression_id + "~renum", source_url=a.source_url,
                   retrieved_at=a.retrieved_at, language="en", valid_from=a.valid_from,
                   effective_status="known", synthetic=False, provisions=out)
    return b, truth


def eval_renumber(corp: Corpus, act: str, runs: int = 5) -> dict:
    dates = sorted(plan_snapshots(act, corp.ing))
    base = corp.snap(act, dates[-1])
    if base is None:
        return {"act": act, "skipped": "no snapshot"}
    rng = random.Random(f"{ADV_SEED}-{act}")
    tot = Counter()
    for _ in range(runs):
        b, truth = renumber_variant(base, rng)
        res = align(base, b)
        pm = {p.a_eid: p.b_eid for p in res.pairs}
        for a_eid, b_eid in truth.items():
            tot["sections"] += 1
            tot["correct"] += pm.get(a_eid) == b_eid
        ch = diff(base, b, res)
        tot["renumbered_labelled"] += sum(1 for c in ch if c.kind == "renumbered" or c.renumbered)
        tot["inserted_detected"] += sum(1 for c in ch if c.kind == "inserted" and c.b_eid == "NEW")
        tot["runs"] += 1
    return {"act": act, **dict(tot), "accuracy": round(tot["correct"] / tot["sections"], 4) if tot["sections"] else None}


def run(acts: list[str] | None = None) -> dict:
    corp = Corpus(make_ingestor())
    acts = acts or ACTS
    per, pit, adv = [], [], []
    for act in acts:
        if corp.ing.latest(url_current(act)) is None:
            continue
        per.append(eval_act(corp, act))
        pit.append(eval_point_in_time(corp, act))
        adv.append(eval_renumber(corp, act))
    res = {"scope": "England and Wales view of English UK Acts, legislation.gov.uk, OGL v3.0. "
                    "Says nothing about UAE law.",
           "engine_modified_or_tuned": False, "acts": per, "point_in_time": pit, "renumbering_variant": adv}
    return res


def aggregate(res: dict) -> dict:
    """Pool one-day window class counts across Acts."""
    cls: dict[str, Counter] = defaultdict(Counter)
    al = Counter()
    for a in res["acts"]:
        if a["one_day"]:
            for k in ("shared_sections", "correct", "wrong", "unmatched", "false_matches", "low_confidence_pairs"):
                al[k] += a["one_day"]["alignment"][k]
            for c, d in a["one_day"]["classes"].items():
                cls[c].update({k: d[k] for k in ("tp", "fp", "fn")})
    out = {"alignment_one_day": dict(al)}
    out["alignment_one_day"]["accuracy"] = round(al["correct"] / al["shared_sections"], 4) if al["shared_sections"] else None
    out["classes_one_day"] = {}
    for c, d in sorted(cls.items()):
        tp, fp, fn = d["tp"], d["fp"], d["fn"]
        out["classes_one_day"][c] = {"tp": tp, "fp": fp, "fn": fn,
                                     "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                                     "recall": round(tp / (tp + fn), 4) if tp + fn else None}
    pq = Counter()
    for p in res["point_in_time"]:
        for k in ("queries", "correct", "wrong", "prior_day_queries", "prior_day_correct", "on_date_queries", "on_date_correct"):
            pq[k] += p.get(k, 0)
    out["point_in_time"] = dict(pq)
    out["point_in_time"]["accuracy"] = round(pq["correct"] / pq["queries"], 4) if pq["queries"] else None
    out["point_in_time"]["prior_day_accuracy"] = round(pq["prior_day_correct"] / pq["prior_day_queries"], 4) if pq["prior_day_queries"] else None
    out["point_in_time"]["on_date_accuracy"] = round(pq["on_date_correct"] / pq["on_date_queries"], 4) if pq["on_date_queries"] else None
    rec, ev = Counter(), Counter()
    for a in res["acts"]:
        rec.update(a["recorded_effects"])
        ev.update(a["engine_vs_recorded_effects"])
    out["recorded_effects"] = dict(rec)
    out["engine_vs_recorded_effects"] = dict(ev)
    s = Counter()
    for r in res["renumbering_variant"]:
        for k in ("sections", "correct", "renumbered_labelled", "inserted_detected", "runs"):
            s[k] += r.get(k, 0)
    out["renumbering_variant"] = dict(s)
    out["renumbering_variant"]["accuracy"] = round(s["correct"] / s["sections"], 4) if s["sections"] else None
    return out


if __name__ == "__main__":
    r = run()
    r["aggregate"] = aggregate(r)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(r, indent=1, ensure_ascii=False, default=str, sort_keys=True), encoding="utf-8")
    print(json.dumps(r["aggregate"], indent=1))
