#!/usr/bin/env python3
"""How did each US equity sector behave, relative to the market, on days of large risk shocks?

Hindsight statistics for the reading aids. Not part of the ledger, not a forecast.

Inputs
  - Kenneth R. French Data Library: 49 industry portfolios (daily, value weighted) and the daily market return.
  - FRED: daily series that stand for each kind of shock.
Method
  - A sector is the simple average of the French industries listed in SECTORS.
  - Excess return = sector return minus market return, same day.
  - A shock day is a day in the worst 5% for that factor (in the risk direction) since START.
  - For each factor and sector: mean excess return on shock days, Welch t statistic against all other days,
    and whether the sign is the same in the first and second half of the sample.
  - Evidence: strong = |t| >= 3 and same sign in both halves; moderate = |t| >= 2 and same sign; else weak.
Standard library only. Needs FRED_API_KEY.
"""
import csv, io, json, math, pathlib, statistics, sys, urllib.request, zipfile, datetime as dt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series  # noqa: E402

START = "1990-01-01"
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
SECTORS = {
    "technology": ["Hardw", "Softw", "Chips"],
    "communication": ["Telcm", "Fun"],
    "consumer_discretionary": ["Autos", "Rtail", "Meals", "Clths", "Toys"],
    "consumer_staples": ["Food", "Soda", "Beer", "Smoke", "Hshld"],
    "energy": ["Oil", "Coal"],
    "financials": ["Banks", "Insur", "Fin"],
    "health_care": ["Hlth", "MedEq", "Drugs"],
    "industrials": ["Mach", "ElcEq", "Aero", "Trans", "Cnstr", "BldMt"],
    "materials": ["Chems", "Steel", "Mines", "Paper", "Boxes"],
    "real_estate": ["RlEst"],
    "utilities": ["Util"],
}
# id: (FRED series or None, how to turn it into a daily move, which tail is the risk direction, description)
FACTORS = {
    "oil_spike": ("DCOILWTICO", "pct", "high", "Oil price jumps (WTI spot, daily % change, top 5%)"),
    "long_rates_up": ("DGS10", "diff", "high", "10-year Treasury yield jumps (daily change, top 5%)"),
    "short_rates_up": ("DGS2", "diff", "high", "2-year Treasury yield jumps (daily change, top 5%)"),
    "credit_widening": ("BAA10Y", "diff", "high", "Corporate credit spread widens (Moody's Baa minus 10-year, daily change, top 5%)"),
    "volatility_spike": ("VIXCLS", "diff", "high", "VIX jumps (daily change, top 5%)"),
    "yen_surge": ("DEXJPUS", "pct", "low", "Yen strengthens sharply against the dollar (daily % change, 5% largest)"),
    "chip_selloff": (None, "chips", "low", "Semiconductor stocks fall hard relative to the market (worst 5% of days)"),
}


def french(name):
    with urllib.request.urlopen(FRENCH + name + "_CSV.zip", timeout=90) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    text = z.read(z.namelist()[0]).decode("latin-1")
    rows, header = {}, None
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if header is None:
            if len(parts) > 3 and parts[0] == "":
                header = parts[1:]
            continue
        if not parts[0].isdigit() or len(parts[0]) != 8:
            if rows:
                break  # end of the first (value weighted) block
            continue
        d = f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]}"
        rows[d] = [float(x) for x in parts[1:]]
    return header, rows


def welch(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    va, vb = statistics.variance(a), statistics.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    return (statistics.fmean(a) - statistics.fmean(b)) / se if se else 0.0


def main():
    ih, ind = french("49_Industry_Portfolios_daily")
    fh, fac = french("F-F_Research_Data_Factors_daily")
    mkt = {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}
    days = sorted(d for d in ind if d >= START and d in mkt)
    sector_ex = {}
    for s, names in SECTORS.items():
        idx = [ih.index(n) for n in names]
        out = {}
        for d in days:
            vals = [ind[d][i] for i in idx if ind[d][i] > -99]
            if vals:
                out[d] = statistics.fmean(vals) - mkt[d]
        sector_ex[s] = out
    chips_i = ih.index("Chips")
    result = {"factors": {}, "table": {}}
    for fid, (sid, how, tail, desc) in FACTORS.items():
        if how == "chips":
            move = {d: ind[d][chips_i] - mkt[d] for d in days if ind[d][chips_i] > -99}
        else:
            obs = fetch_series(sid, "1989-06-01")
            move = {}
            for (d0, v0), (d1, v1) in zip(obs, obs[1:]):
                if d1 in mkt and d1 >= START and (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days <= 5:
                    move[d1] = (100 * (v1 / v0 - 1)) if how == "pct" and v0 > 0 else (v1 - v0)
        ds = sorted(move)
        vals = sorted(move[d] for d in ds)
        k = max(1, len(vals) // 20)
        if tail == "high":
            cut = vals[-k]
            shock = [d for d in ds if move[d] >= cut]
        else:
            cut = vals[k - 1]
            shock = [d for d in ds if move[d] <= cut]
        shock_set, mid = set(shock), ds[len(ds) // 2]
        mk_on = statistics.fmean(mkt[d] for d in shock)
        mk_all = statistics.fmean(mkt[d] for d in ds)
        result["factors"][fid] = {"description": desc, "source": sid or "Kenneth R. French Data Library (Chips industry)",
                                  "first_day": ds[0], "last_day": ds[-1], "days": len(ds), "shock_days": len(shock),
                                  "threshold": round(cut, 3), "market_mean_return_on_shock_days_pct": round(mk_on, 2),
                                  "market_mean_return_all_days_pct": round(mk_all, 3)}
        row = {}
        for s, ex in sector_ex.items():
            if fid == "chip_selloff" and s == "technology":
                continue  # the factor is built from this sector
            on = [ex[d] for d in shock if d in ex]
            off = [ex[d] for d in ds if d not in shock_set and d in ex]
            h1 = [ex[d] for d in shock if d in ex and d < mid]
            h2 = [ex[d] for d in shock if d in ex and d >= mid]
            if len(on) < 30 or not h1 or not h2:
                continue
            m, t = statistics.fmean(on), welch(on, off)
            same = (statistics.fmean(h1) > 0) == (statistics.fmean(h2) > 0) == (m > 0)
            level = "strong" if abs(t) >= 3 and same else "moderate" if abs(t) >= 2 and same else "weak"
            row[s] = {"mean_excess_pct": round(m, 2), "t": round(t, 1), "n": len(on),
                      "first_half_pct": round(statistics.fmean(h1), 2), "second_half_pct": round(statistics.fmean(h2), 2),
                      "evidence": level, "direction": "lagged" if m < 0 else "led"}
        result["table"][fid] = row
        print(fid, result["factors"][fid])
        for s, v in sorted(row.items(), key=lambda kv: kv[1]["mean_excess_pct"]):
            print(f"   {s:24s} {v['mean_excess_pct']:+.2f}  t={v['t']:+.1f}  n={v['n']}  halves {v['first_half_pct']:+.2f}/{v['second_half_pct']:+.2f}  {v['evidence']}")
    result["meta"] = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warning": "Hindsight statistics on same-day moves. Association, not cause. Not a forecast and not a recommendation.",
        "sectors": SECTORS, "start": START,
        "sources": ["Kenneth R. French Data Library, 49 Industry Portfolios (daily) and Fama/French factors (daily)",
                    "FRED, Federal Reserve Bank of St. Louis"],
        "method": __doc__.strip(),
    }
    out = ROOT / "sensitivity" / "sectors.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
