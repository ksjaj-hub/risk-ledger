#!/usr/bin/env python3
"""Run a published rule over past data. Output goes to backtest/<version>/, never to records/.

This is hindsight, not the ledger: it uses today's revised data and a rule written after the fact.
Components whose source has no data yet on a given day are left out and the score is scaled to
the components that exist. Only levels are written, never licensed raw values.

  python scripts/backtest.py                 # live, needs FRED_API_KEY
  python scripts/backtest.py --fixture DIR   # tests
"""
import argparse, bisect, csv, datetime as dt, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series, level_for  # noqa: E402

START = "1990-01-01"
MIN_WINDOW = 252  # the drawdown component needs a full year of prices before it counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--rule", default="v1", help="version name in rules/, or a path to a rule JSON file")
    ap.add_argument("--out", default=str(ROOT / "backtest"))
    a = ap.parse_args()
    rp = pathlib.Path(a.rule)
    rule = json.loads((rp if rp.suffix == ".json" else ROOT / "rules" / f"{a.rule}.json").read_text())
    comps = rule["components"]
    series, avail = {}, {}
    for c in comps:
        try:
            s = fetch_series(c["series"], START, a.fixture)
        except RuntimeError as e:
            print(f"{c['series']}: unavailable ({e})")
            s = []
        series[c["id"]] = ([d for d, _ in s], [v for _, v in s])
        avail[c["id"]] = {"series": c["series"], "first": s[0][0] if s else None,
                          "last": s[-1][0] if s else None, "observations": len(s)}
        print(c["series"], avail[c["id"]])
    days = sorted(set().union(*[set(series[c["id"]][0]) for c in comps if c["transform"] == "latest"
                                and c["series"] != "NFCI"]))
    names = [s["name"] for s in rule["states"]]
    conf = rule.get("confirmation", {})
    esc, de = conf.get("escalate_after_days", 1), conf.get("deescalate_after_days", 1)
    rows, hist, pub = [], [], None
    for day in days:
        levels = {}
        for c in comps:
            dates, vals = series[c["id"]]
            i = bisect.bisect_right(dates, day)
            if i == 0:
                continue
            if c["transform"] == "latest":
                value = vals[i - 1]
            else:
                if i < MIN_WINDOW:
                    continue
                value = 100 * (1 - vals[i - 1] / max(vals[i - 252:i]))
            levels[c["id"]] = level_for(value, c["thresholds"], c["direction"])
        if not levels:
            continue
        lv = list(levels.values())
        score = round(100 * sum(lv) / (3 * len(lv)))
        idx = max(k for k, s in enumerate(rule["states"]) if score >= s["min_score"])
        for f in rule["floors"]:
            ext = sum(l == 3 for k, l in levels.items() if k not in f.get("not_counting", []))
            if ext >= f["if_components_at_extreme_at_least"]:
                idx = max(idx, names.index(f["state_at_least"]))
        hist.append(idx)
        if pub is None:
            pub = idx
        elif len(hist) >= esc and all(h > pub for h in hist[-esc:]):
            pub = min(hist[-esc:])
        elif len(hist) >= de and all(h < pub for h in hist[-de:]):
            pub = max(hist[-de:])
        rows.append((day, names[pub], score, len(lv), levels))

    out = pathlib.Path(a.out) / rule["version"]
    out.mkdir(parents=True, exist_ok=True)
    ids = [c["id"] for c in comps]
    with open(out / "daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "state", "score", "components_used"] + [f"{i}_level" for i in ids])
        for day, st, sc, n, lv in rows:
            w.writerow([day, st, sc, n] + [lv.get(i, "") for i in ids])

    # runs of consecutive days in the same state
    runs, cur = [], None
    for day, st, sc, n, lv in rows:
        if cur and cur["state"] == st:
            cur["end"], cur["days"], cur["peak_score"] = day, cur["days"] + 1, max(cur["peak_score"], sc)
        else:
            cur = {"state": st, "start": day, "end": day, "days": 1, "peak_score": sc, "components_used": n}
            runs.append(cur)
    # episodes: stretches at Elevated or Stress, joined when the gap between them is under 20 trading days
    eps, gap, cur = [], 0, None
    for day, st, sc, n, lv in rows:
        hot = st in ("Elevated", "Stress")
        if hot:
            if cur is None:
                cur = {"start": day, "end": day, "days_elevated_or_stress": 0, "days_stress": 0,
                       "first_stress": None, "peak_score": 0, "peak_score_date": day, "components_used": n}
                eps.append(cur)
            cur["end"], gap = day, 0
            cur["days_elevated_or_stress"] += 1
            if st == "Stress":
                cur["days_stress"] += 1
                cur["first_stress"] = cur["first_stress"] or day
            if sc > cur["peak_score"]:
                cur["peak_score"], cur["peak_score_date"] = sc, day
        elif cur is not None:
            gap += 1
            if gap >= 20:
                cur = None
    by_year = {}
    for day, st, sc, n, lv in rows:
        y = by_year.setdefault(day[:4], {k: 0 for k in names})
        y[st] += 1
    total = {k: sum(1 for r in rows if r[1] == k) for k in names}
    summary = {
        "rule_version": rule["version"],
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warning": "Hindsight backtest on revised data. Not part of the ledger and not evidence of future results.",
        "data_availability": avail,
        "days": len(rows), "first_day": rows[0][0], "last_day": rows[-1][0],
        "days_by_state": total,
        "days_by_state_by_year": by_year,
        "state_changes": len(runs) - 1,
        "episodes_elevated_or_stress": eps,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("days", "first_day", "last_day", "days_by_state", "state_changes")}))
    print("episodes:", len(eps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
