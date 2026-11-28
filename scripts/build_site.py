#!/usr/bin/env python3
"""Bundle records, alerts and event cards into docs/data.json for the public page."""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(pattern):
    return [json.loads(p.read_text()) | {"_path": p.relative_to(ROOT).as_posix()} for p in sorted(ROOT.glob(pattern))]


rule_path = sorted((ROOT / "rules").glob("v*.json"), key=lambda p: int(p.stem[1:]))[-1]
rule = json.loads(rule_path.read_text())
records = load("records/us/*/*.json")
data = {
    "rule": {"version": rule["version"], "components": {c["id"]: c["name"] for c in rule["components"]},
             "labels": rule["level_labels"],
             "states": [{"name": x["name"], "min_score": x["min_score"]} for x in rule.get("states", [])]},
    "latest": records[-1] if records else None,
    "history": [{"date": r["recorded_at_utc"][:10], "state": r["state"], "score": r["score"]} for r in records],
    "alerts": load("alerts/us/*/*.json"),
    "events": [e for e in load("events/*.json")],
    # reading aids and hindsight cases: editorial, not part of the record
    "aids": json.loads((ROOT / "aids" / "reading.json").read_text()),
    "hindsight": json.loads((ROOT / "hindsight" / "cases.json").read_text()) if (ROOT / "hindsight" / "cases.json").exists() else {"cases": []},
    # reading aid only: the English cards are the record
    "ko": json.loads((ROOT / "i18n" / "events.ko.json").read_text()),
}
# forecasts: the page shows deadline and odds only; the reasoning stays in the card file. Score summary from forecasts/scorecard.json
for _e in data["events"]:
    _e["forecasts"] = [{k: v for k, v in f.items() if k != "basis" and v is not None} for f in _e.get("forecasts", [])]
# selection criteria: a card that does not meet them carries a one-line mark (selection/criteria.json)
_sel = json.loads((ROOT / "selection" / "criteria.json").read_text())["audit"]["cards"]
for _e in data["events"]:
    if _sel.get(_e["id"], {}).get("mark"):
        _e["selection_mark"] = _sel[_e["id"]]["mark"]
_fs = json.loads((ROOT / "forecasts" / "scorecard.json").read_text()) if (ROOT / "forecasts" / "scorecard.json").exists() else {}
data["aids"]["forecast_score"] = {k: _fs.get(k) for k in ("settled", "brier", "yardstick_nothing_happens", "next_deadline")}
# card -> sector links with an evidence level, and a per-sector score. Reading aid, see sensitivity/README.md
def _j(name, default):
    p = ROOT / "sensitivity" / name
    return json.loads(p.read_text()) if p.exists() else default
sens = _j("sectors.json", {"table": {}, "factors": {}, "cases": {}})
mapping = _j("mapping.json", {"cards": {}, "score": {"points": {}, "top_groups": 5, "version": 0}})
case_names = {c["id"]: c for c in _j("cases.json", {"cases": []})["cases"]}
aids = data["aids"]
# what each state was followed by: hindsight from research/v4 (rule v3 on long series, test period only). Reading aid.
_rp = ROOT / "research" / "v4" / "results.json"
if _rp.exists():
    _t = json.loads(_rp.read_text())["test"]
    aids["state_ranges"] = {"first": _t["first"], "last": _t["last"], "horizon_trading_days": 63, "fall_pct": 10,
                            "states": [{"state": b["state"], "days": b["days"], "share": b["share_O1"], "worst5": b["fall63_5th_percentile"]}
                                       for b in _t["states"]["v3_long"]["by_state"]]}
# how long each state has lasted: hindsight from research/v4 round 5 (rule v3 from 1990). Reading aid.
_r5 = ROOT / "research" / "v4" / "results5.json"
if _r5.exists():
    _d = json.loads(_r5.read_text())["part_D_state_durations_since_1990"]
    aids["state_durations"] = {"since": 1990, "states": [{"state": k, "spells": v["spells"], "median": v["median_trading_days"],
                                                          "upper_quartile": v["upper_quartile"], "moved_up_share": v["share_ended_by_moving_up"]}
                                                         for k, v in _d.items()]}
# what followed past days at each ten-point band of the score (research/v4/score_bins.json). Reading aid.
_bn = ROOT / "research" / "v4" / "score_bins.json"
if _bn.exists():
    _b = json.loads(_bn.read_text())
    _long = {x["from"]: x for x in _b["since_1990"]["bands"]}
    aids["score_bands"] = {"first": _b["since_2007"]["first"], "last": _b["since_2007"]["last"], "long_first": _b["since_1990"]["first"],
                           "bands": [{"from": x["from"], "to": x["to"], "days": x["days"], "share": x["share_fall10"], "worst5": x["p5_deepest"],
                                      "thin": x["thin"], "mix": x.get("mix_lt5_5to10_10to20_ge20"), "days_to_fall": x.get("median_days_to_fall10"), "long_share": _long.get(x["from"], {}).get("share_fall10")}
                                     for x in _b["since_2007"]["bands"]]}
# market breadth: a reference reading under test, outside the rule (shadow/README.md). Reading aid.
_sb = ROOT / "shadow" / "breadth.csv"
if _sb.exists():
    import csv as _csv
    _last = {}
    for _r in _csv.DictReader(open(_sb)):
        _last[_r["measure"]] = _r
    aids["shadow_breadth"] = {m: {"as_of": r["as_of"], "below": round(float(r["breadth"]) * int(r["members"])), "members": int(r["members"]),
                                  "level": int(r["level"])} for m, r in _last.items()}
POINTS, TOPN = mapping["score"]["points"], mapping["score"]["top_groups"]
links = {}
for e in data["events"]:
    cid, out_l = e["id"], {}
    m = mapping["cards"].get(cid, {})
    judged = aids.get("sectors", {}).get(cid, {})
    for s_id in aids.get("sector_names", {}):
        best = None
        for f in m.get("factors", []):
            v = sens["table"].get(f, {}).get(s_id)
            if v and v["evidence"] != "weak" and (best is None or abs(v["t"]) > abs(best["t"])):
                best = {"level": v["evidence"], "direction": v["direction"], "factor": f, "mean_excess_pct": v["mean_excess_pct"],
                        "t": v["t"], "n": v["n"], "since": sens["factors"][f]["first_day"][:4]}
        if best is None:
            for c in m.get("cases", []):
                cv = sens.get("cases", {}).get(c)
                if cv and cv["sectors"][s_id]["direction"] != "flat":
                    best = {"level": "case", "direction": cv["sectors"][s_id]["direction"], "case": c, "excess_pct": cv["sectors"][s_id]["excess_pct"],
                            "start": cv["start"], "end": cv["end"], "case_en": case_names[c]["en"], "case_ko": case_names[c]["ko"]}
        if s_id in m.get("about", []):
            best = (best or {}) | {"level": "direct", "direction": (best or {}).get("direction", "lagged")}
        elif best is None and s_id in judged.get("direct", []):
            best = {"level": "unconfirmed", "direction": "lagged"}
        if best:
            out_l[s_id] = best
    links[cid] = out_l
live = [e for e in data["events"] if e["status"] != "resolved"]
scores = {}
for s_id in aids.get("sector_names", {}):
    groups, cards = {}, 0
    for e in live:
        l = links[e["id"]].get(s_id)
        if l and (l["direction"] == "lagged" or l["level"] == "direct"):
            lev = l["level"]; cards += 1
        elif not l and aids.get("sectors", {}).get(e["id"], {}).get("market_wide"):
            lev = "market_wide"
        else:
            continue
        g = mapping["cards"].get(e["id"], {}).get("group", e["id"])
        if g not in groups or POINTS[lev] > POINTS[groups[g][0]]:
            groups[g] = (lev, e["id"])
    ranked = sorted(groups.values(), key=lambda v: (-POINTS[v[0]], v[0] != "direct"))[:TOPN]
    top = [v[0] for v in ranked]
    pts = sum(POINTS[v] for v in top)
    sc = round(100 * pts / (3 * TOPN))
    bands = mapping["score"]["bands"]
    scores[s_id] = {"score": sc, "band": "high" if sc >= bands["high_from"] else "moderate" if sc >= bands["moderate_from"] else "low",
                    "reasons": [c for lev, c in ranked if lev != "market_wide"][:2], "points": pts, "max_points": 3 * TOPN, "open_cards": cards,
                    "groups": len(groups), "counted": {k: top.count(k) for k in POINTS if top.count(k)}}
aids["links"], aids["sector_scores"], aids["score_points"] = links, scores, POINTS
aids["score_version"], aids["mapping_version"] = mapping["score"]["version"], mapping.get("version")
aids["card_factors"] = {k: v.get("factors", []) for k, v in mapping["cards"].items()}
aids["sensitivity_generated"] = sens.get("meta", {}).get("generated_at_utc")
# past waves after similar shocks: reading aid, see waves/README.md
def _waves():
    import datetime as _dt
    wp, ep = ROOT / "waves" / "waves.json", ROOT / "waves" / "episodes.json"
    if not (wp.exists() and ep.exists()):
        return {}
    W, E = json.loads(wp.read_text()), json.loads(ep.read_text())
    names = {x["id"]: x for x in E["episodes"]}
    S, rule_eps, out = W["oil_rule_summary"], W["oil_rule_episodes"], {}
    past = [x for x in rule_eps if not x["current"]]
    cur = next((x for x in rule_eps if x["current"]), None)
    gap = lambda a, b: abs((_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days)
    for cid, ids in W["cards"].items():
        eps = [W["named"][i] | {"id": i} for i in ids if i in W["named"]]
        if not eps:
            continue
        if eps[0]["kind"] == "oil" and past:
            sx, n = S["sector_excess_at"], len(past)
            series = []
            if cur:
                series.append({"k": "now", "y": cur["day_0"][:4], "now": True, "p": cur["oil_path"]})
            for k, e in zip("ab", eps):
                r = min(past, key=lambda x: gap(x["day_0"], e["start"]))
                series.append({"k": k, "y": e["start"][:4], "en": names[e["id"]]["en"], "ko": names[e["id"]]["ko"], "p": r["oil_path"]})
            out[cid] = {"kind": "oil", "n": n, "series": series, "x0": 0,
                        "fall_med": S["market_largest_fall_pct"]["median"], "fall_min": S["market_largest_fall_pct"]["min"],
                        "fall_base": S["any_day_since_1990"]["market_largest_fall_pct"]["median"],
                        "hl": int(S["oil_half_life_days"]["median"]), "hl_min": int(S["oil_half_life_days"]["min"]),
                        "hl_max": int(S["oil_half_life_days"]["max"]),
                        "still": S["oil_still_above_pre_shock_at"]["252"], "oil_first": S["oil_peak_before_market_low"],
                        "util_led": n - sx["utilities"]["21"]["negative"], "stap_led": n - sx["consumer_staples"]["21"]["negative"],
                        "disc_lag": sx["consumer_discretionary"]["21"]["negative"],
                        "cur": cur and {"fall": cur.get("equity", {}).get("market", {}).get("largest_fall_pct"),
                                        "half": cur["half_life_days"], "now": cur["latest_rise_pct"], "day": cur["latest_day"]},
                        "last_equity": W["meta"]["last_equity_day"], "last_brent": W["meta"]["last_brent_day"]}
        elif eps[0]["kind"] == "tariff" and len(eps) >= 2:
            out[cid] = {"kind": "tariff", "x0": 1,
                        "series": [{"k": k, "y": e["start"][:4], "en": names[e["id"]]["en"], "ko": names[e["id"]]["ko"],
                                    "p": e["paths"]["market"][:126]} for k, e in zip("ab", eps)],
                        "eps": [{"y": e["start"][:4], "fall": e["market"]["largest_fall_pct"], "day": e["market"]["largest_fall_day"],
                                 "rec": e["market"]["days_to_recover_half"], "end": e["market"]["at"]["126"],
                                 "mat": e["sectors"]["materials"]["at"]["126"], "fin": e["sectors"]["financials"]["at"]["126"]}
                                for e in eps[:2]]}
    return out
aids["waves"] = _waves()
# past cases set beside a card (waves/episodes.json) and the market price check (market/README.md). Reading aids.
def _past():
    import datetime as _dt
    wp, ep = ROOT / "waves" / "waves.json", ROOT / "waves" / "episodes.json"
    if not (wp.exists() and ep.exists()):
        return {}
    W, E = json.loads(wp.read_text()), json.loads(ep.read_text())
    names, out = {x["id"]: x for x in E["episodes"]}, {"cards": {}, "none": E.get("no_past_case", {})}
    out["base_fall"] = W["oil_rule_summary"]["any_day_since_1990"]["market_largest_fall_pct"]["median"]
    for cid, ids in E["cards"].items():
        rows = []
        for i in ids:
            n, m = names[i], W["named"].get(i, {}).get("market")
            if not m:
                continue
            r = {"en": n["en"], "ko": n["ko"], "start": n["start"], "src": n["source"], "fall": m["largest_fall_pct"],
                 "day": m["largest_fall_day"], "rec": m["days_to_recover_half"], "end6": m["at"].get("126")}
            if n.get("end"):
                r["end"] = n["end"]
                r["days"] = n.get("lasted_days") or (_dt.date.fromisoformat(n["end"]) - _dt.date.fromisoformat(n["start"])).days  # the source's own count where it gives one
            rows.append(r)
        if rows:
            out["cards"][cid] = rows
    return out
aids["past"] = _past()
_mk = ROOT / "market" / "check.json"
if _mk.exists():
    _m = json.loads(_mk.read_text())
    aids["market"] = {"as_of": _m["meta"]["generated_at_utc"][:10], "at": _m["meta"]["generated_at_utc"][11:16], "cards": {
        k: {"verdict": v["verdict"], "none": v.get("none"),
            "readings": [{x: r[x] for x in ("en", "ko", "unit", "value", "as_of", "percentile_5y", "steps", "shows", "rule") if x in r}
                         for r in v["readings"] if "shows" in r]} for k, v in _m["cards"].items()}}
# patterns that passed the scoring rule fixed in advance: reading aid, see patterns/README.md
def _patterns():
    d = ROOT / "patterns"
    if not all((d / f).exists() for f in ("patterns.json", "criteria.json", "judgment.json")):
        return {}
    S2 = json.loads((d / "second_look.json").read_text()) if (d / "second_look.json").exists() else {}
    P, J = json.loads((d / "patterns.json").read_text()), json.loads((d / "judgment.json").read_text())["scores"]
    out = {"as_of_equity": P["meta"]["last_equity_day"], "scorecard": {}, "shown": {}}
    for k, j in J.items():
        e = P[k]["headline"]["evidence_score"]
        total = e + j["usefulness"] + j["fit"] + j["upkeep"]
        out["scorecard"][k] = {"evidence": e, "usefulness": j["usefulness"], "fit": j["fit"], "upkeep": j["upkeep"],
                               "total": total, "shown": e >= 3 and total >= 14}  # pass rule in patterns/criteria.json
    if out["scorecard"].get("overlap", {}).get("shown"):
        o = P["overlap"]
        out["shown"]["overlap"] = {"now": {"as_of": o["now"]["as_of"], "active": o["now"]["active"]},
                                   "falls": [o["none_active"]["largest_fall_63_median"], o["one_active"]["largest_fall_63_median"],
                                             o["two_or_more_active"]["largest_fall_63_median"]],
                                   "stretches": o["two_or_more_separate_stretches"]}
        if "overlap_2" in S2:  # robustness variants, see patterns/criteria2.json
            v2 = S2["overlap_2"]
            rs = [v2[k]["ratio_two_or_more_over_one"] for k in ("top_10pct", "every_5th_day")] + [x["ratio_two_or_more_over_one"] for x in v2["leave_one_out"].values()]
            out["shown"]["overlap"]["more"] = [min(rs), max(rs)]
    if out["scorecard"].get("aftershocks", {}).get("shown"):
        a = P["aftershocks"]
        out["shown"]["aftershocks"] = {"n": a["with_full_window"], "ratios": [a["headline"]["value"], a["ratio_to_background"]["22-63"],
                                                                               a["ratio_to_background"]["64-126"]],
                                       "again": a["another_3pct_fall_within_21_days"]}
        if "aftershocks_2" in S2 and "aftershocks_nikkei" in S2:  # untouched period and another market
            out["shown"]["aftershocks"]["more"] = {"pre": S2["aftershocks_2"]["headline"]["value"], "pre_n": S2["aftershocks_2"]["with_full_window"],
                                                   "nk": S2["aftershocks_nikkei"]["headline"]["value"], "nk_n": S2["aftershocks_nikkei"]["with_full_window"]}
    return out
aids["patterns"] = _patterns()
sc_path = ROOT / "sector_scores" / "scorecard.json"
aids["scorecard"] = json.loads(sc_path.read_text()) if sc_path.exists() else None
# residual risk index (residual/preregistration.json): a sum of AFMX's own judgment, shown with its limits
_rp = ROOT / "residual" / "index.json"
if _rp.exists():
    _r = json.loads(_rp.read_text())
    aids["residual"] = {**{k: _r["latest"][k] for k in ("date", "index", "open_cards", "equal_reach")}, "max": _r["max_if_all_worsened"],
                        "cards": [[c["card"], c["share"]] for c in _r["cards"][:5]], "history": [[h["date"], h["index"]] for h in _r["history"]]}
# Page weight: the page file carries only what the page shows. Everything dropped here stays in the source files
# (events/*.json and hindsight/cases.json), which are the record; docs/data.json is a copy for the screen.
for _e in data["events"]:
    for _k in ("superseded_sources", "conditions_as_first_written", "_path", "schema", "note", "category", "first_recorded"):
        _e.pop(_k, None)
    for _k in ("numeric_criteria", "counter_view", "condition_reading_notes"):
        if isinstance(_e.get(_k), dict):
            _e[_k].pop("note", None)
for _k in ("withdrawn", "source_rule", "note"):
    data["hindsight"].pop(_k, None)
out = ROOT / "docs" / "data.json"
out.parent.mkdir(exist_ok=True)
# Korean card text goes in its own file, fetched only when the page is shown in Korean (page weight, 2026-11-28).
(ROOT / "docs" / "ko.json").write_text(json.dumps(data.pop("ko"), indent=0, ensure_ascii=False) + "\n")
out.write_text(json.dumps(data, indent=0, ensure_ascii=False) + "\n")  # no indent: keeps one value per line for diffs, smaller file
print(f"wrote {out.relative_to(ROOT)}: {len(records)} records, {len(data['alerts'])} alerts, {len(data['events'])} events")
