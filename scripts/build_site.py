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
             "labels": rule["level_labels"]},
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
# card -> sector links with an evidence level, and a per-sector score. Reading aid, see sensitivity/README.md
def _j(name, default):
    p = ROOT / "sensitivity" / name
    return json.loads(p.read_text()) if p.exists() else default
sens = _j("sectors.json", {"table": {}, "factors": {}, "cases": {}})
mapping = _j("mapping.json", {"cards": {}, "score": {"points": {}, "top_groups": 5, "version": 0}})
case_names = {c["id"]: c for c in _j("cases.json", {"cases": []})["cases"]}
aids = data["aids"]
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
sc_path = ROOT / "sector_scores" / "scorecard.json"
aids["scorecard"] = json.loads(sc_path.read_text()) if sc_path.exists() else None
out = ROOT / "docs" / "data.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {out.relative_to(ROOT)}: {len(records)} records, {len(data['alerts'])} alerts, {len(data['events'])} events")
