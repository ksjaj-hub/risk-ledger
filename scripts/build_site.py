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
sens_path = ROOT / "sensitivity" / "sectors.json"
sens = json.loads(sens_path.read_text()) if sens_path.exists() else {"table": {}, "factors": {}}
aids = data["aids"]
POINTS = {"direct": 3, "strong": 3, "moderate": 2, "unconfirmed": 1, "market_wide": 1}
links = {}
for e in data["events"]:
    cid, out_l = e["id"], {}
    judged = aids.get("sectors", {}).get(cid, {})
    for s_id in aids.get("sector_names", {}):
        best = None
        for f in aids.get("risk_factors", {}).get(cid, []):
            v = sens["table"].get(f, {}).get(s_id)
            if v and v["evidence"] != "weak" and (best is None or abs(v["t"]) > abs(best["t"])):
                best = {"level": v["evidence"], "direction": v["direction"], "factor": f, "mean_excess_pct": v["mean_excess_pct"],
                        "t": v["t"], "n": v["n"], "since": sens["factors"][f]["first_day"][:4]}
        if s_id in aids.get("about", {}).get(cid, []):
            best = (best or {}) | {"level": "direct", "direction": (best or {}).get("direction", "lagged")}
        elif best is None and s_id in judged.get("direct", []):
            best = {"level": "unconfirmed", "direction": "lagged"}
        if best:
            out_l[s_id] = best
    links[cid] = out_l
live = [e for e in data["events"] if e["status"] != "resolved"]
scores = {}
for s_id in aids.get("sector_names", {}):
    pts, counts = 0, {k: 0 for k in POINTS}
    for e in live:
        l = links[e["id"]].get(s_id)
        if l and (l["direction"] == "lagged" or l["level"] == "direct"):
            pts += POINTS[l["level"]]; counts[l["level"]] += 1
        elif not l and aids.get("sectors", {}).get(e["id"], {}).get("market_wide"):
            pts += POINTS["market_wide"]; counts["market_wide"] += 1
    scores[s_id] = {"score": round(100 * pts / (3 * len(live))) if live else 0, "points": pts, "max_points": 3 * len(live), "counts": counts}
aids["links"], aids["sector_scores"], aids["score_points"] = links, scores, POINTS
aids["sensitivity_generated"] = sens.get("meta", {}).get("generated_at_utc")
out = ROOT / "docs" / "data.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {out.relative_to(ROOT)}: {len(records)} records, {len(data['alerts'])} alerts, {len(data['events'])} events")
