"""What followed past days at each level of the score (ten-point bands). A reading aid.

The plan is fixed in research/v4/score_bins_plan.json before computing. Hindsight on revised data: past
frequencies, not forecasts. Usage: python scripts/score_bins.py [--fixture DIR]
"""
import argparse, csv, datetime as dt, json, pathlib, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
r3 = lambda x: None if x is None or np.isnan(x) else round(float(x), 3)


def market(fixture):
    if fixture:
        rows = list(csv.reader(open(pathlib.Path(fixture) / "MKT.csv")))[1:]
        return {d: float(v) for d, v in rows}
    from sector_sensitivity import french
    fh, fac = french("F-F_Research_Data_Factors_daily")
    return {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}


def summarise(rows, lo_day):
    rows = [r for r in rows if r["day"] >= lo_day and r["fall"] is not None]
    out = []
    for lo in range(0, 100, 10):
        hi = 100 if lo == 90 else lo + 9
        idx = [k for k, r in enumerate(rows) if lo <= r["score"] <= hi]
        if not idx:
            continue
        f = np.array([rows[k]["fall"] for k in idx])
        spells = 1 + sum(1 for a, b in zip(idx, idx[1:]) if b != a + 1)
        out.append({"from": lo, "to": hi, "days": len(idx), "spells": spells,
                    "share_fall10": r3((f <= -10).mean()), "share_fall20": r3((f <= -20).mean()),
                    "median_deepest": r3(np.median(f)), "p5_deepest": r3(np.percentile(f, 5)),
                    "thin": bool(len(idx) < 250 or spells < 10)})
    states = {}
    for r in rows:
        states.setdefault(r["state"], []).append(r["fall"] <= -10)
    return {"first": rows[0]["day"], "last": rows[-1]["day"], "days": len(rows), "bands": out,
            "check_share_fall10_by_state": {k: r3(np.mean(v)) for k, v in states.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    a = ap.parse_args()
    mkt = market(a.fixture)
    days = [d for d in sorted(mkt) if d >= "1985-01-01"]
    P = np.exp(np.cumsum(np.log1p(np.array([mkt[d] for d in days]) / 100)))
    pos = {d: i for i, d in enumerate(days)}
    rows = []
    for r in csv.DictReader(open(ROOT / "research" / "v4" / "daily.csv")):
        i = pos.get(r["date"])
        if i is None:
            continue
        fall = 100 * (P[i + 1: i + 64].min() / P[i] - 1) if i + 63 < len(days) else None
        rows.append({"day": r["date"], "score": int(r["v3_long_score"]), "state": r["v3_long_state"], "fall": fall})
    res = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "warning": "Hindsight on revised data. Past frequencies, not forecasts. Plan: score_bins_plan.json.",
           "horizon_trading_days": 63, "market_last": days[-1],
           "since_2007": summarise(rows, "2007-01-03"), "since_1990": summarise(rows, "1990-01-02")}
    if not a.fixture:
        (ROOT / "research" / "v4" / "score_bins.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
