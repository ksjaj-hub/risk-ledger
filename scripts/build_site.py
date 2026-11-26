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
}
out = ROOT / "docs" / "data.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {out.relative_to(ROOT)}: {len(records)} records, {len(data['alerts'])} alerts, {len(data['events'])} events")
