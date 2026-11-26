#!/usr/bin/env python3
"""Daily collector: fetch inputs, apply the versioned rule, write an append-only record.

Standard library only. Usage:
  python scripts/collect.py                 # live fetch from FRED
  python scripts/collect.py --fixture DIR   # read <SERIES>.csv from DIR (tests)
"""
import argparse, csv, datetime as dt, hashlib, io, json, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"


def fetch_series(sid, start, fixture=None):
    """Return [(date_str, float)] ascending, skipping missing values."""
    if fixture:
        text = (pathlib.Path(fixture) / f"{sid}.csv").read_text()
    else:
        url, last = FRED.format(sid=sid, start=start), None
        ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        for attempt in range(4):
            try:
                # curl first: the site stalls some non-browser clients
                text = subprocess.run(
                    ["curl", "-sS", "--fail", "--compressed", "--max-time", "40", "-A", ua,
                     "-H", "Accept: text/csv,*/*", url],
                    check=True, capture_output=True, text=True).stdout
                break
            except Exception as e:  # network errors: retry with backoff
                last = getattr(e, "stderr", None) or e
                time.sleep(5 * 2 ** attempt)
        else:
            raise RuntimeError(f"could not fetch {sid}: {last}")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0]) != 2 or rows[0][1] != sid:
        raise RuntimeError(f"unexpected CSV header for {sid}: {rows[:1]}")
    out = []
    for d, v in rows[1:]:
        if v in ("", "."):
            continue
        out.append((d, float(v)))
    if not out:
        raise RuntimeError(f"no observations for {sid}")
    return out


def level_for(value, thresholds, direction):
    if direction == "higher_is_riskier":
        return sum(value >= t for t in thresholds)
    return sum(value < t for t in thresholds)


def evaluate(rule, series):
    comps = {}
    for c in rule["components"]:
        obs = series[c["series"]]
        obs_date = obs[-1][0]
        if c["transform"] == "latest":
            value = obs[-1][1]
        elif c["transform"] == "drawdown_pct_from_252d_high":
            window = [v for _, v in obs[-252:]]
            value = round(100 * (1 - obs[-1][1] / max(window)), 2)
        else:
            raise RuntimeError(f"unknown transform {c['transform']}")
        lvl = level_for(value, c["thresholds"], c["direction"])
        entry = {"observation_date": obs_date, "level": lvl, "label": rule["level_labels"][lvl]}
        if c["publish_value"]:
            entry["value"] = value
        else:
            entry["value_withheld"] = "source license does not allow republishing"
        comps[c["id"]] = entry
    levels = [e["level"] for e in comps.values()]
    score = round(100 * sum(levels) / (3 * len(levels)))
    names = [s["name"] for s in rule["states"]]
    idx = max(i for i, s in enumerate(rule["states"]) if score >= s["min_score"])
    extremes = sum(l == 3 for l in levels)
    for f in rule["floors"]:
        if extremes >= f["if_components_at_extreme_at_least"]:
            idx = max(idx, names.index(f["state_at_least"]))
    return comps, score, names[idx]


def latest_record(market_dir):
    files = sorted(market_dir.glob("*/*.json"))
    return files[-1] if files else None


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--now", help="override UTC timestamp (tests only)")
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    rule_path = sorted((ROOT / "rules").glob("v*.json"), key=lambda p: int(p.stem[1:]))[-1]
    rule_bytes = rule_path.read_bytes()
    rule = json.loads(rule_bytes)
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    start = (now - dt.timedelta(days=420)).strftime("%Y-%m-%d")
    series = {c["series"]: fetch_series(c["series"], start, a.fixture) for c in rule["components"]}
    comps, score, state = evaluate(rule, series)

    market = rule["market"].lower()
    mdir = root / "records" / market
    prev_path = latest_record(mdir)
    prev = json.loads(prev_path.read_text()) if prev_path else None
    obs_dates = {k: v["observation_date"] for k, v in comps.items()}
    if prev and prev["rule_version"] == rule["version"] and \
            {k: v["observation_date"] for k, v in prev["components"].items()} == obs_dates:
        print("no new observations since last record; nothing written")
        return 0

    day = now.strftime("%Y-%m-%d")
    rec_path = mdir / day[:4] / f"{day}.json"
    if rec_path.exists():
        print(f"{rec_path} already exists; records are never overwritten")
        return 0
    record = {
        "schema": 1,
        "market": rule["market"],
        "recorded_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule_version": rule["version"],
        "rule_sha256": hashlib.sha256(rule_bytes).hexdigest(),
        "state": state,
        "score": score,
        "components": comps,
        "previous_record": None if not prev_path else {
            "path": prev_path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(prev_path.read_bytes()).hexdigest(),
        },
        "note": "Risk state only. Not a forecast and not investment advice.",
    }
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(dump(record))
    print(f"wrote {rec_path.relative_to(root)}: {state} ({score})")

    changes = []
    if prev is None:
        kind = "baseline"
    else:
        kind = "change"
        if prev["state"] != state:
            changes.append({"what": "state", "from": prev["state"], "to": state})
        for k, v in comps.items():
            p = prev["components"].get(k)
            if p and p["level"] != v["level"]:
                changes.append({"what": k, "from": p["label"], "to": v["label"]})
    if kind == "baseline" or changes:
        adir = root / "alerts" / market / day[:4]
        adir.mkdir(parents=True, exist_ok=True)
        alert = {
            "schema": 1,
            "market": rule["market"],
            "issued_at_utc": record["recorded_at_utc"],
            "type": kind,
            "rule_version": rule["version"],
            "state": state,
            "score": score,
            "changes": changes,
            "record": rec_path.relative_to(root).as_posix(),
            "note": "Risk state only. Not a forecast and not investment advice.",
        }
        (adir / f"{day}.json").write_text(dump(alert))
        print(f"alert ({kind}): {changes or 'first record'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
