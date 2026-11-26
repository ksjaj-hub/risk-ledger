#!/usr/bin/env python3
"""Five measurements that resemble the risk wave, scored against criteria fixed in advance.

Hindsight statistics for the reading aids. Not part of the ledger, not a forecast.
Definitions, the evidence rule and the pass rule are in patterns/criteria.json, which was committed before this
script produced any result. Date lists are in patterns/dates.json.

Inputs: Kenneth R. French Data Library (daily market return and 49 industries); FRED (Brent, 10-year Treasury
yield, Moody's Baa minus 10-year spread, VIX, Nikkei 225).
Standard library only. Needs FRED_API_KEY.
"""
import bisect, datetime as dt, json, math, pathlib, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series  # noqa: E402
from sector_sensitivity import french, SECTORS  # noqa: E402

START = "1990-01-01"
r2 = lambda x: None if x is None else round(x, 2)
med = lambda v: r2(statistics.median(v)) if v else None
share = lambda v, f: r2(100 * sum(1 for x in v if f(x)) / len(v)) if v else None


def evidence(rule, kind, value, background, n, halves_agree):
    """Apply patterns/criteria.json evidence_rule. Returns (score, effect)."""
    e = rule["effect"][kind]
    if value is None or n == 0:
        return 2, "no data"
    if kind == "ratio":
        eff = "strong" if value >= e["strong"] else "visible" if value >= e["visible"] else "none" if value < e["none_below"] else "weak"
    else:
        d = value - background
        eff = ("strong" if d >= e["strong_points_over_background"] else "visible" if d >= e["visible_points_over_background"]
               else "none" if abs(d) <= e["none_within_points"] else "weak")
    if eff == "none":
        return 1, eff
    if n < 8 or eff == "weak":
        return 2, eff
    if eff == "strong":
        if n >= 30 and halves_agree:
            return 5, eff
        if n >= 15 and halves_agree:
            return 4, eff
        return 3, eff
    return (3 if n >= 15 and halves_agree else 2), eff


def main():
    crit = json.loads((ROOT / "patterns" / "criteria.json").read_text())
    dates = json.loads((ROOT / "patterns" / "dates.json").read_text())
    rule = crit["evidence_rule"]
    ih, ind = french("49_Industry_Portfolios_daily")
    fh, fac = french("F-F_Research_Data_Factors_daily")
    mkt_all = {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}
    days = sorted(d for d in ind if d >= START and d in mkt_all)
    R = [mkt_all[d] for d in days]
    N = len(days)
    mid = N // 2
    cum = [0.0]
    for x in R:
        cum.append(cum[-1] + math.log(1 + x / 100))  # cum[i+1] = log index after day i
    ret = lambda i, h: 100 * (math.exp(cum[min(N, i + 1 + h)] - cum[i + 1]) - 1)  # return over the h days after day i
    def fall(i, h):  # largest fall from the close of day i within the next h days, as a non-positive %
        seg = cum[i + 2: i + 2 + h]
        return 100 * (math.exp(min(0.0, min(seg) - cum[i + 1])) - 1) if seg else 0.0
    fred = {}
    for sid in ("DCOILBRENTEU", "DGS10", "BAA10Y", "VIXCLS", "NIKKEI225"):
        obs = fetch_series(sid, "1989-01-01")
        fred[sid] = ([d for d, _ in obs], [v for _, v in obs])
    def asof(sid, day, max_gap=7):
        ds, vs = fred[sid]
        k = bisect.bisect_right(ds, day) - 1
        if k < 0 or (dt.date.fromisoformat(day) - dt.date.fromisoformat(ds[k])).days > max_gap:
            return None
        return vs[k]
    out = {}

    # ---- aftershocks
    big = [abs(x) >= 2 for x in R]
    bg = 100 * sum(big) / N
    mains = [i for i in range(N) if R[i] <= -3 and not any(R[j] <= -3 for j in range(max(0, i - 21), i))]
    wins = {"1-5": (1, 5), "6-21": (6, 21), "22-63": (22, 63), "64-126": (64, 126)}
    def freq(idx, a, b):
        tot = hit = 0
        for i in idx:
            seg = big[i + a: i + b + 1]
            tot += len(seg); hit += sum(seg)
        return 100 * hit / tot if tot else None
    full = [i for i in mains if i + 126 < N]
    per = [sum(big[i + 1: i + 22]) for i in full]
    f21 = freq(full, 1, 21)
    h1, h2 = [i for i in full if i < mid], [i for i in full if i >= mid]
    hr = [freq(h, 1, 21) / bg if h and freq(h, 1, 21) is not None else None for h in (h1, h2)]
    A = {"main_shocks": len(mains), "with_full_window": len(full), "first": days[mains[0]] if mains else None, "last": days[mains[-1]] if mains else None,
         "background_share_of_2pct_days": r2(bg),
         "share_of_2pct_days_after": {k: r2(freq(full, a, b)) for k, (a, b) in wins.items()},
         "ratio_to_background": {k: r2(freq(full, a, b) / bg) for k, (a, b) in wins.items()},
         "big_days_in_next_21": {"median": med(per), "min": min(per) if per else None, "max": max(per) if per else None,
                                 "ordinary_expected": r2(21 * bg / 100)},
         "another_3pct_fall_within_21_days": sum(1 for i in full if any(x <= -3 for x in R[i + 1: i + 22])),
         "halves_ratio_1_21": [r2(x) for x in hr]}
    A["headline"] = {"kind": "ratio", "value": r2(f21 / bg), "background": 1.0, "n": len(full),
                     "halves_agree": all(x is not None and x >= rule["effect"]["ratio"]["visible"] for x in hr)}
    out["aftershocks"] = A

    # ---- contagion (a) countries
    nd, nv = fred["NIKKEI225"]
    k0 = bisect.bisect_left(nd, START)
    nk = {nd[k]: 100 * (nv[k] / nv[k - 1] - 1) for k in range(max(1, k0), len(nd)) if nv[k - 1] > 0}
    nk_days = sorted(nk)
    nk_bg_down, nk_bg_med = share(list(nk.values()), lambda x: x < 0), med(list(nk.values()))
    cut_us = sorted(R)[max(0, int(N * 0.025) - 1)]
    us_shock = [i for i in range(N) if R[i] <= cut_us and not any(R[j] <= cut_us for j in range(max(0, i - 5), i))]
    nxt = []
    for i in us_shock:
        k = bisect.bisect_right(nk_days, days[i])
        if k < len(nk_days) and (dt.date.fromisoformat(nk_days[k]) - dt.date.fromisoformat(days[i])).days <= 5:
            nxt.append((i, nk[nk_days[k]]))
    vals = [v for _, v in nxt]
    hv = [[v for i, v in nxt if i < mid], [v for i, v in nxt if i >= mid]]
    nk_vals = sorted(nk.values())
    cut_jp = nk_vals[max(0, int(len(nk_vals) * 0.025) - 1)]
    jp_shock = [d for k, d in enumerate(nk_days) if nk[d] <= cut_jp and not any(nk[x] <= cut_jp for x in nk_days[max(0, k - 5): k])]
    us_same = [mkt_all[d] for d in jp_shock if d in mkt_all and d >= START]  # Tokyo closes before New York opens on the same date
    Ba = {"us_shock_threshold_pct": r2(cut_us), "us_shock_days": len(us_shock), "with_nikkei_next_day": len(vals),
          "nikkei_next_day_down_share": share(vals, lambda x: x < 0), "nikkei_next_day_median_pct": med(vals),
          "nikkei_all_days_down_share": nk_bg_down, "nikkei_all_days_median_pct": nk_bg_med,
          "halves_down_share": [share(h, lambda x: x < 0) for h in hv],
          "reverse": {"japan_shock_threshold_pct": r2(cut_jp), "japan_shock_days": len(us_same),
                      "us_same_date_down_share": share(us_same, lambda x: x < 0), "us_same_date_median_pct": med(us_same),
                      "us_all_days_down_share": share(R, lambda x: x < 0)}}
    # (b) sectors
    Bb, pooled5, pooled21, pool_idx = {}, [], [], []
    for s, names in SECTORS.items():
        idx = [ih.index(n) for n in names]
        ex = []
        for d in days:
            v = [ind[d][i] for i in idx if ind[d][i] > -99]
            ex.append(statistics.fmean(v) - mkt_all[d] if v else 0.0)
        cut = sorted(ex)[max(0, int(N * 0.01) - 1)]
        sh = [i for i in range(N - 21) if ex[i] <= cut and R[i] > -1 and not any(ex[j] <= cut and R[j] > -1 for j in range(max(0, i - 5), i))]
        a5, a21 = [ret(i, 5) for i in sh], [ret(i, 21) for i in sh]
        Bb[s] = {"n": len(sh), "market_next_5_median": med(a5), "market_next_21_median": med(a21), "market_next_21_down_share": share(a21, lambda x: x < 0)}
        pooled5 += a5; pooled21 += a21; pool_idx += sh
    all21 = [ret(i, 21) for i in range(N - 21)]
    all5 = [ret(i, 5) for i in range(N - 5)]
    Bsec = {"by_sector": Bb, "pooled_n": len(pooled21), "market_next_5_median": med(pooled5), "market_next_21_median": med(pooled21),
            "market_next_21_down_share": share(pooled21, lambda x: x < 0),
            "ordinary": {"market_next_5_median": med(all5), "market_next_21_median": med(all21), "market_next_21_down_share": share(all21, lambda x: x < 0)}}
    ha = [share(h, lambda x: x < 0) for h in hv]
    out["contagion"] = {"countries": Ba, "sectors": Bsec,
                        "headline": {"kind": "share", "value": Ba["nikkei_next_day_down_share"], "background": nk_bg_down, "n": len(vals),
                                     "halves_agree": all(x is not None and x - nk_bg_down >= rule["effect"]["share"]["visible_points_over_background"] for x in ha)}}

    # ---- overlap
    def change20(sid, pct):
        ds, vs = fred[sid]
        res = {}
        for i, d in enumerate(days):
            a = asof(sid, d); b = asof(sid, days[i - 20]) if i >= 20 else None
            if a is not None and b is not None and (not pct or b > 0):
                res[i] = 100 * (a / b - 1) if pct else a - b
        return res
    states = {"oil": change20("DCOILBRENTEU", True), "rates": change20("DGS10", False), "credit": change20("BAA10Y", False), "vol": change20("VIXCLS", False)}
    cuts = {k: sorted(v.values())[int(len(v) * 0.95)] for k, v in states.items()}
    groups = {0: [], 1: [], 2: []}
    combos = {}
    for i in range(21, N - 63, 21):
        act = sorted(k for k, v in states.items() if i in v and v[i] >= cuts[k])
        g = min(2, len(act))
        groups[g].append((i, fall(i, 63), ret(i, 21), ret(i, 63)))
        if len(act) >= 2:
            combos["+".join(act)] = combos.get("+".join(act), 0) + 1
    def gsum(rows):
        return {"n": len(rows), "largest_fall_63_median": med([r[1] for r in rows]), "return_21_median": med([r[2] for r in rows]),
                "return_63_median": med([r[3] for r in rows]), "fall_of_10pct_or_more_share": share([r[1] for r in rows], lambda x: x <= -10)}
    C = {"thresholds_top_5pct_of_20_day_change": {k: r2(v) for k, v in cuts.items()},
         "none_active": gsum(groups[0]), "one_active": gsum(groups[1]), "two_or_more_active": gsum(groups[2]), "combinations": combos}
    def ratio(rows2, rows1):
        a, b = med([r[1] for r in rows2]), med([r[1] for r in rows1])
        return r2(a / b) if a is not None and b else None
    hC = [ratio([r for r in groups[2] if (r[0] < mid) == first], [r for r in groups[1] if (r[0] < mid) == first]) for first in (True, False)]
    C["halves_ratio"] = hC
    # samples taken 21 trading days apart inside one crisis are not independent: count separate stretches instead
    idx2 = [r[0] for r in groups[2]]
    stretches = sum(1 for j, i in enumerate(idx2) if j == 0 or i - idx2[j - 1] > 63)
    C["two_or_more_sample_days"] = [days[i] for i in idx2]
    C["two_or_more_separate_stretches"] = stretches
    # the present: which states are active on the latest day FRED has, on the VIX calendar
    vd = fred["VIXCLS"][0]
    last = vd[-1]
    now = {}
    for key, (sid, pct) in {"oil": ("DCOILBRENTEU", True), "rates": ("DGS10", False), "credit": ("BAA10Y", False), "vol": ("VIXCLS", False)}.items():
        a, b = asof(sid, last), asof(sid, vd[-21])
        if a is None or b is None or (pct and b <= 0):
            now[key] = None
            continue
        chg = 100 * (a / b - 1) if pct else a - b
        now[key] = {"change_20_days": r2(chg), "threshold": r2(cuts[key]), "active": chg >= cuts[key]}
    C["now"] = {"as_of": last, "states": now, "active": sorted(k for k, v in now.items() if v and v["active"])}
    C["headline"] = {"kind": "ratio", "value": ratio(groups[2], groups[1]), "background": 1.0, "n": stretches,
                     "halves_agree": all(x is not None and x >= rule["effect"]["ratio"]["visible"] for x in hC)}
    out["overlap"] = C

    # ---- reverberation
    eps, peak_i, trough_i = [], 0, 0
    for i in range(1, N):
        if cum[i + 1] >= cum[peak_i + 1]:
            dd = 100 * (math.exp(cum[trough_i + 1] - cum[peak_i + 1]) - 1)
            if dd <= -7:
                eps.append((peak_i, trough_i, i, dd))
            peak_i = trough_i = i
        elif cum[i + 1] < cum[trough_i + 1]:
            trough_i = i
    rows = []
    for p, t, r, dd in eps:
        row = {"peak": days[p], "trough": days[t], "recovered": days[r], "fall_pct": r2(dd), "days_peak_to_recovery": r - p}
        for key, sid in (("vix", "VIXCLS"), ("spread", "BAA10Y")):
            a, b = asof(sid, days[p]), asof(sid, days[r])
            row[key + "_at_peak"], row[key + "_at_recovery"] = a, b
            row[key + "_still_higher"] = None if a is None or b is None else b > a
            back = None
            if a is not None and b is not None and b > a:
                back = next((j - r for j in range(r + 1, min(N, r + 253)) if (asof(sid, days[j]) or 1e9) <= a), None)
            row[key + "_days_until_back"] = back if (a is not None and b is not None and b > a) else 0
        row["largest_fall_next_126"] = r2(fall(r, 126)) if r + 126 < N else None
        rows.append(row)
    ok = [x for x in rows if x["spread_still_higher"] is not None]
    hi = [x for x in ok if x["spread_still_higher"]]
    lo = [x for x in ok if not x["spread_still_higher"]]
    vh = [x for x in rows if x["vix_still_higher"]]
    hD = [share([x for x in ok if (x["recovered"] < days[mid]) == first], lambda x: x["spread_still_higher"]) for first in (True, False)]
    D = {"episodes": rows, "n": len(ok),
         "spread_still_higher_share": share(ok, lambda x: x["spread_still_higher"]),
         "vix_still_higher_share": share([x for x in rows if x["vix_still_higher"] is not None], lambda x: x["vix_still_higher"]),
         "spread_days_until_back_median": med([x["spread_days_until_back"] for x in hi if x["spread_days_until_back"] is not None]),
         "spread_not_back_within_252": sum(1 for x in hi if x["spread_days_until_back"] is None),
         "vix_days_until_back_median": med([x["vix_days_until_back"] for x in vh if x["vix_days_until_back"] is not None]),
         "vix_not_back_within_252": sum(1 for x in vh if x["vix_days_until_back"] is None),
         "next_126_largest_fall_median": {"spread_still_higher": med([x["largest_fall_next_126"] for x in hi if x["largest_fall_next_126"] is not None]),
                                          "spread_back": med([x["largest_fall_next_126"] for x in lo if x["largest_fall_next_126"] is not None]),
                                          "ordinary": med([fall(i, 126) for i in range(0, N - 126, 21)])},
         "halves_share": hD}
    D["headline"] = {"kind": "share", "value": D["spread_still_higher_share"], "background": 50.0, "n": len(ok),
                     "halves_agree": all(x is not None and x - 50 >= rule["effect"]["share"]["visible_points_over_background"] for x in hD)}
    out["reverberation"] = D

    # ---- dates
    pos = {d: i for i, d in enumerate(days)}
    fomc = [pos[d] for d in dates["fomc"]["dates"] if d in pos]
    years = sorted({days[i][:4] for i in fomc})
    other = [i for i in range(N) if days[i][:4] in years and i not in set(fomc)]
    mabs = lambda idx: statistics.fmean(abs(R[i]) for i in idx) if idx else None
    vixchg = [(asof("VIXCLS", days[i]) or 0) - (asof("VIXCLS", days[i - 1]) or 0) for i in fomc if i > 0]
    fmid = len(fomc) // 2
    hE = [mabs(h) / statistics.fmean(abs(R[i]) for i in other if days[i][:4] in {days[j][:4] for j in h}) if h else None for h in (fomc[:fmid], fomc[fmid:])]
    E1 = {"meetings_used": len(fomc), "years": years, "mean_abs_move_fomc_day": r2(mabs(fomc)), "mean_abs_move_other_days": r2(mabs(other)),
          "share_1pct_moves_fomc": share([R[i] for i in fomc], lambda x: abs(x) >= 1), "share_1pct_moves_other": share([R[i] for i in other], lambda x: abs(x) >= 1),
          "vix_fell_on_the_day_share": share(vixchg, lambda x: x < 0), "halves_ratio": [r2(x) for x in hE]}
    gaps = []
    for g in dates["funding_gaps"]["gaps"]:
        i = bisect.bisect_right(days, g["funding_ended"]) - 1
        if i < 10 or i + 21 >= N:
            continue
        gaps.append({"funding_ended": g["funding_ended"], "full_days": g["full_days"], "return_10_before": r2(ret(i - 10, 10)),
                     "return_21_after": r2(ret(i, 21)), "largest_fall_21_after": r2(fall(i, 21))})
    all10 = [ret(i, 10) for i in range(N - 10)]
    E2 = {"gaps": gaps, "n": len(gaps), "down_before_count": sum(1 for g in gaps if g["return_10_before"] < 0),
          "return_10_before_median": med([g["return_10_before"] for g in gaps]), "return_21_after_median": med([g["return_21_after"] for g in gaps]),
          "ordinary": {"return_10_median": med(all10), "return_10_down_share": share(all10, lambda x: x < 0), "return_21_median": med(all21)}}
    val = r2(mabs(fomc) / mabs(other)) if fomc and other else None
    out["dates"] = {"fomc": E1, "funding_gaps": E2,
                    "headline": {"kind": "ratio", "value": val, "background": 1.0, "n": len(fomc),
                                 "halves_agree": all(x is not None and x >= rule["effect"]["ratio"]["visible"] for x in hE)}}

    for k, v in out.items():
        h = v["headline"]
        h["evidence_score"], h["effect"] = evidence(rule, h["kind"], h["value"], h["background"], h["n"], h["halves_agree"])
        print(k, json.dumps(h))
    print(json.dumps({k: {a: b for a, b in v.items() if a not in ("episodes",)} for k, v in out.items()})[:6000])
    out["meta"] = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "warning": "Hindsight statistics. A range of what happened, not a forecast and not a recommendation.",
                   "first_day": days[0], "last_equity_day": days[-1], "trading_days": N, "half_split_day": days[mid],
                   "sources": ["Kenneth R. French Data Library, 49 Industry Portfolios (daily) and Fama/French factors (daily)",
                               "FRED, Federal Reserve Bank of St. Louis"], "method": __doc__.strip()}
    (ROOT / "patterns" / "patterns.json").write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
