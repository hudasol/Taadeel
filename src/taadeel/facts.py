"""Every number quoted in the README, the proposal briefs and the evaluation card, read from results/.

Templates in docs/templates/*.md use ``{key}`` placeholders; ``python -m taadeel.report`` renders them.
A template that names a key not defined here fails loudly, so a number cannot be typed by hand.
Keys for a result file that does not exist yet are simply absent (rendering then fails, by design).
"""
from __future__ import annotations

import json
from pathlib import Path

R = Path(__file__).resolve().parents[2] / "results"


def _load(name: str) -> dict | None:
    p = R / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def f3(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def facts() -> dict[str, str]:
    F: dict[str, str] = {}
    ho = _load("heldout_synthetic.json")
    F["v1_heldout_hits"], F["v1_heldout_total"] = str(ho["hits"]), str(ho["total"])
    F["v1_heldout_misses"] = str(ho["total"] - ho["hits"])
    F["v1_heldout_directional_hits"] = str(sum(v["ok"] for v in ho["directional"].values()))
    F["v1_heldout_directional_total"] = str(len(ho["directional"]))
    for key, name in (("templated", "templated near-duplicates, small edits"), ("e40", "templated, 40% of words edited"),
                      ("e70", "templated, 70% of words edited"), ("many", "templated, many inserts/repeals")):
        pc = ho["results"][name]["per_class"]
        F[f"v1_{key}_repealed_R"] = f3(pc["repealed"]["recall"])
        F[f"v1_{key}_inserted_R"] = f3(pc["inserted"]["recall"])

    uk = _load("uk_validation.json")
    ag = uk["aggregate"]
    al, pit = ag["alignment_one_day"], ag["point_in_time"]
    F["uk_oneday_correct"], F["uk_oneday_shared"] = str(al["correct"]), str(al["shared_sections"])
    F["uk_acts"] = str(len(uk["acts"]))
    lg = [a["long_gap"] for a in uk["acts"] if a["long_gap"]]
    F["uk_longgap_correct"] = str(sum(x["correct"] for x in lg))
    F["uk_longgap_shared"] = str(sum(x["shared"] for x in lg))
    F["uk_pit_prior_correct"], F["uk_pit_prior_total"] = str(pit["prior_day_correct"]), str(pit["prior_day_queries"])
    F["uk_pit_prior_pct"] = pct(pit["prior_day_accuracy"])
    F["uk_pit_prior_wrong"] = str(pit["prior_day_queries"] - pit["prior_day_correct"])
    rv = ag["renumbering_variant"]
    F["uk_renumber_correct"], F["uk_renumber_total"] = str(rv["correct"]), str(rv["sections"])

    am = _load("uk_amending.json")
    t = am["test"]["extended_patterns"]
    F["am1_test_found"], F["am1_test_effects"], F["am1_test_recall"] = str(t["effects_found"]), str(t["recorded_effects"]), pct(t["recall"])
    F["am1_test_sections"] = str(t["sections"])
    F["am1_test_prec"] = pct(t["precision_lower_bound"])

    am2 = _load("uk_amending_2.json")
    if am2:
        c = am2["combined"]
        e = c["all"]["extended_patterns"]
        F["am2_fetched"], F["am2_bearing"] = str(c["fetched"]), str(c["instruction_bearing"])
        F["am2_found"], F["am2_effects"], F["am2_recall"] = str(e["effects_found"]), str(e["recorded_effects"]), pct(e["recall"])
        F["am2_matched"], F["am2_instr"], F["am2_prec"] = (str(e["instructions_matching_a_recorded_effect"]),
                                                          str(e["parsed_instructions"]), pct(e["precision_lower_bound"]))
        s = am2["schedule_paragraphs"]["all"]["extended_patterns"]
        F["am2_sched_recall"], F["am2_sched_found"], F["am2_sched_effects"] = pct(s["recall"]), str(s["effects_found"]), str(s["recorded_effects"])
        o = c["all"]["original_patterns"]
        F["am2_orig_recall"] = pct(o["recall"])

    tl = _load("uk_timeline_v2.json")
    if tl:
        t = tl["total"]
        unc = t["new_uncertain_truth_in_candidates"] + t["new_uncertain_truth_missing"]
        F["tl_queries"], F["tl_old_correct"] = str(t["queries"]), str(t["old_correct"])
        F["tl_old_wrong"] = str(t["queries"] - t["old_correct"])
        F["tl_certain_correct"], F["tl_certain_wrong"] = str(t["new_certain_correct"]), str(t["new_certain_wrong"])
        F["tl_uncertain"], F["tl_uncertain_hit"] = str(unc), str(t["new_uncertain_truth_in_candidates"])
        F["tl_uncertain_miss"] = str(t["new_uncertain_truth_missing"])
        F["tl_uncertain_first"] = str(t["new_uncertain_truth_is_first_candidate"])
        F["tl_uncertain_pct"] = pct(unc / t["queries"])
        checks = {"T0": abs(t["old_correct"] - 63) <= 2, "T1": t["new_certain_wrong"] <= 5, "T2": unc / t["queries"] <= 0.30,
                  "T3": unc == 0 or t["new_uncertain_truth_in_candidates"] / unc >= 0.80, "T4": t["new_certain_correct"] >= 50}
        F["tl_pred_hits"], F["tl_pred_total"] = str(sum(checks.values())), str(len(checks))
        F["tl_pred_detail"] = ", ".join(f"{k} {'hit' if v else 'miss'}" for k, v in checks.items())

    v2 = _load("heldout_v2.json")
    if v2:
        F["v2_hits"], F["v2_total"] = str(v2["hits"]), str(v2["total"])
        F["v2_dir_hits"], F["v2_dir_total"] = str(v2["directional_hits"]), str(v2["directional_total"])
        F["v2_dir_misses"] = ", ".join(k for k, v in v2["directional"].items() if not v["ok"]) or "none"
        d = v2["directional"]
        better = all(d[k]["ok"] for k in ("V1", "V2", "V3", "V7")) and all(d[k]["ok"] for k in ("U1", "U2"))
        F["v2_verdict"] = (
            "On the pre registered bar (V1, V2, V3, V7 on synthetic data and U1, U2 on UK text) v2 is better than v1 on synthetic text and no worse on UK text. "
            "v1 stays the default engine because the v2 gain relies on number offsets that real UAE amendments may not follow and v2 is not checked on real Arabic text; v2 is available as a separate module."
            if better else
            f"v2 did not meet the pre registered bar (claims not held: {F['v2_dir_misses']})"
            + (f": it raised repealed and inserted recall in every templated scenario and aligned the UK pairs as correctly as v1, but was slightly worse than v1 on the easy scenario (lowest v2 metric there {d['V6']['detail'].split('=')[-1]}). "
               if d["V2"]["ok"] and d["V3"]["ok"] and not d["V6"]["ok"] else ". ")
            + (f"It also marks more UK pairs as low confidence ({v2['uk_v2']['one_day']['alignment']['low_confidence_pairs']} against "
               f"{v2['uk_v1']['one_day']['alignment']['low_confidence_pairs']} on one day windows) and has lower inserted precision in the many inserts scenario "
               f"({f3(v2['heldout_v2']['templated, many inserts/repeals']['per_class']['inserted']['precision'])} against "
               f"{f3(v2['heldout_v1']['templated, many inserts/repeals']['per_class']['inserted']['precision'])}). ")
            + "v1 stays the default engine.")
        for key, name in (("templated", "templated near-duplicates, small edits"), ("e40", "templated, 40% of words edited"),
                          ("e70", "templated, 70% of words edited"), ("many", "templated, many inserts/repeals"),
                          ("easy", "easy (random text, small edits)")):
            for ver in ("v1", "v2"):
                r = v2[f"heldout_{ver}"][name]
                pc = r["per_class"]
                F[f"h2_{ver}_{key}_acc"] = f3(r["alignment_accuracy"])
                F[f"h2_{ver}_{key}_repealed_R"] = f3(pc["repealed"]["recall"])
                F[f"h2_{ver}_{key}_inserted_R"] = f3(pc["inserted"]["recall"])
                F[f"h2_{ver}_{key}_replaced_P"] = f3(pc["replaced"]["precision"])
                F[f"h2_{ver}_{key}_clarified_R"] = f3(pc["clarified"]["recall"])
        for ver in ("v1", "v2"):
            u = v2[f"uk_{ver}"]
            F[f"h2_uk_{ver}_oneday"] = f"{u['one_day']['alignment']['correct']} of {u['one_day']['alignment']['shared_sections']}"
            F[f"h2_uk_{ver}_longgap"] = f"{u['long_gap']['alignment']['correct']} of {u['long_gap']['alignment']['shared_sections']}"
            F[f"h2_uk_{ver}_longgap_false"] = str(u["long_gap"]["alignment"]["false_matches"])
            F[f"h2_uk_{ver}_renumber"] = f"{u['renumber']['correct']} of {u['renumber']['sections']}"

    st = _load("arabic_stress.json")
    if st:
        n, l = st["summary"]["normalise"], st["summary"]["labels"]
        F["ar_cases"] = str(n["cases"] + l["cases"])
        F["ar_v1_ok"], F["ar_v2_ok"] = str(n["v1_ok"] + l["v1_ok"]), str(n["v2_ok"] + l["v2_ok"])
        F["ar_label_cases"], F["ar_label_v1_ok"] = str(l["cases"]), str(l["v1_ok"])

    wp = _load("arabic_wikisource_probe.json")
    if wp:
        F["ws_articles"], F["ws_max"] = str(wp["v1_parser"]["articles"]), str(wp["v1_parser"]["max_number"])
        F["ws_missing"] = str(wp["v1_parser"]["missing_numbers"])
        r = wp["renumbering_variant"]
        F["ws_renumber_v1"] = f"{r['v1']['correct']} of {r['v1']['articles']}"
        F["ws_renumber_v2"] = f"{r['v2']['correct']} of {r['v2']['articles']}"

    ak = _load("akn_validation.json")
    if ak:
        F["akn_valid"], F["akn_total"] = str(ak["valid"]), str(ak["total"])
        F["akn_controls"], F["akn_controls_total"] = str(ak["negative_controls_rejected"]), str(len(ak["negative_controls"]))
    return F


if __name__ == "__main__":
    for k, v in facts().items():
        print(f"{k} = {v}")
