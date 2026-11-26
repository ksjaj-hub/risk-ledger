#!/usr/bin/env python3
"""Daily collector: fetch inputs, apply the versioned rule, write an append-only record.

Standard library only. Usage:
  python scripts/collect.py                 # live fetch from the FRED API (needs FRED_API_KEY)
  python scripts/collect.py --fixture DIR   # read <SERIES>.csv from DIR (tests)
"""
import argparse, bisect, csv, datetime as dt, hashlib, io, json, os, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = ("https://api.stlouisfed.org/fred/series/observations"
       "?series_id={sid}&observation_start={start}&file_type=json&api_key={key}")


def fetch_series(sid, start, fixture=None):
    """Return [(date_str, float)] ascending, skipping missing values."""
    if fixture:
        rows = list(csv.reader(io.StringIO((pathlib.Path(fixture) / f"{sid}.csv").read_text())))
        if not rows or len(rows[0]) != 2 or rows[0][1] != sid:
            raise RuntimeError(f"unexpected CSV header for {sid}: {rows[:1]}")
        pairs = rows[1:]
    else:
        key = os.environ.get("FRED_API_KEY")
        if not key:
            raise RuntimeError("FRED_API_KEY is not set")
        url, last = API.format(sid=sid, start=start, key=key), None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=40) as r:
                    data = json.load(r)
                break
            except Exception as e:  # network errors: retry with backoff
                last = type(e).__name__ + (f" {e.code}" if hasattr(e, "code") else "")
                time.sleep(5 * 2 ** attempt)
        else:
            raise RuntimeError(f"could not fetch {sid}: {last}")  # never print the URL: it holds the key
        pairs = [(o["date"], o["value"]) for o in data["observations"]]
    out = [(d, float(v)) for d, v in pairs if v not in ("", ".")]
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
    score, idx = judge(rule, {k: e["level"] for k, e in comps.items()})
    return comps, score, [s["name"] for s in rule["states"]][idx]


def judge(rule, levels):
    """levels: {component_id: level}. Returns (score, index of the state the rule indicates)."""
    names = [s["name"] for s in rule["states"]]
    lv = list(levels.values())
    score = round(100 * sum(lv) / (3 * len(lv)))
    idx = max(i for i, s in enumerate(rule["states"]) if score >= s["min_score"])
    for f in rule["floors"]:
        extremes = sum(l == 3 for k, l in levels.items() if k not in f.get("not_counting", []))
        if extremes >= f["if_components_at_extreme_at_least"]:
            idx = max(idx, names.index(f["state_at_least"]))
    return score, idx


def levels_asof(rule, series, day, min_window=1):
    """Component levels using only observations dated on or before `day`."""
    out = {}
    for c in rule["components"]:
        obs = series[c["series"]]
        i = bisect.bisect_right([d for d, _ in obs], day)
        if i == 0:
            continue
        if c["transform"] == "latest":
            value = obs[i - 1][1]
        else:
            if i < min_window:
                continue
            value = 100 * (1 - obs[i - 1][1] / max(v for _, v in obs[max(0, i - 252):i]))
        out[c["id"]] = level_for(value, c["thresholds"], c["direction"])
    return out


def confirm(published, recent, rule):
    """Apply the rule's confirmation step. `recent` = indicated state indexes, oldest first, ending today.

    Up: after `escalate_after_days` days in a row above the published state (default 1 = at once).
    Down: after `deescalate_after_days` days in a row below it, and then only to the highest of those days.
    A rule without a confirmation block publishes what it indicates.
    """
    conf = rule.get("confirmation", {})
    esc, de = conf.get("escalate_after_days", 1), conf.get("deescalate_after_days", 1)
    if published is None:
        return recent[-1]
    if len(recent) >= esc and all(h > published for h in recent[-esc:]):
        return min(recent[-esc:])
    if len(recent) >= de and all(h < published for h in recent[-de:]):
        return max(recent[-de:])
    return published


def trading_days(rule, series):
    """Days that count for confirmation: dates of the daily market inputs."""
    ds = set()
    for c in rule["components"]:
        if c["transform"] == "latest" and c["series"] != "NFCI":
            ds.update(d for d, _ in series[c["series"]])
    return sorted(ds)


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
    comps, score, indicated = evaluate(rule, series)
    names = [s["name"] for s in rule["states"]]

    market = rule["market"].lower()
    mdir = root / "records" / market
    prev_path = latest_record(mdir)
    prev = json.loads(prev_path.read_text()) if prev_path else None
    obs_dates = {k: v["observation_date"] for k, v in comps.items()}
    if prev and prev["rule_version"] == rule["version"] and \
            {k: v["observation_date"] for k, v in prev["components"].items()} == obs_dates:
        print("no new observations since last record; nothing written")
        return 0

    # Confirmation: start from the last published state and walk the trading days since that record.
    days = trading_days(rule, series)
    prev_day = None
    if prev:
        daily = {c["id"] for c in rule["components"] if c["transform"] == "latest" and c["series"] != "NFCI"}
        prev_day = max(v["observation_date"] for k, v in prev["components"].items() if k in daily)
    todo = [d for d in days if prev_day is None or d >= prev_day][-30:] or days[-1:]
    lookback = max(rule.get("confirmation", {}).get("deescalate_after_days", 1),
                   rule.get("confirmation", {}).get("escalate_after_days", 1))
    first = days.index(todo[0])
    window = days[max(0, first - lookback + 1):]
    ind = {d: judge(rule, levels_asof(rule, series, d))[1] for d in window}
    ind[window[-1]] = names.index(indicated)  # the last day uses every latest observation, as recorded above
    published = names.index(prev["state"]) if prev else None
    for d in todo:
        recent = [ind[x] for x in window if x <= d]
        published = confirm(published, recent, rule)
    state = names[published]
    recent_days = [{"date": d, "indicated": names[ind[d]]} for d in window[-lookback:]]

    day = now.strftime("%Y-%m-%d")
    stem = day
    if (mdir / day[:4] / f"{day}.json").exists():
        # a later record on the same day gets the time in its name; nothing is overwritten
        stem = now.strftime("%Y-%m-%dT%H%MZ")
    rec_path = mdir / day[:4] / f"{stem}.json"
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
        **({"indicated_state": indicated, "recent_indicated_states": recent_days}
           if "confirmation" in rule else {}),
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
        if prev["rule_version"] != rule["version"]:
            changes.append({"what": "rule_version", "from": prev["rule_version"], "to": rule["version"]})
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
        (adir / f"{stem}.json").write_text(dump(alert))
        print(f"alert ({kind}): {changes or 'first record'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
