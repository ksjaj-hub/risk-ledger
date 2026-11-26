#!/usr/bin/env python3
"""Second look at the risk patterns: longer history and robustness checks.

Hindsight statistics for the reading aids. Not part of the ledger, not a forecast.
The tests are fixed in patterns/criteria2.json, committed before this script produced any result. The evidence rule
and the pass rule are those of patterns/criteria.json, unchanged.

Inputs: Kenneth R. French Data Library (daily market return, from July 1926); FRED (Brent, 10-year Treasury yield,
Moody's Baa minus 10-year spread, VIX, Nikkei 225). Standard library only. Needs FRED_API_KEY.
"""
import bisect, datetime as dt, json, math, pathlib, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series  # noqa: E402
from sector_sensitivity import french  # noqa: E402
from patterns import evidence, r2, med, share  # noqa: E402

SPLIT = "1990-01-01"


class Series:
    """Daily market returns with the helpers the first round used."""
    def __init__(self, days, R):
        self.days, self.R, self.N = days, R, len(days)
        self.cum = [0.0]
        for x in R:
            self.cum.append(self.cum[-1] + math.log(1 + x / 100))

    def fall(self, i, h):
        seg = self.cum[i + 2: i + 2 + h]
        return 100 * (math.exp(min(0.0, min(seg) - self.cum[i + 1])) - 1) if seg else 0.0

    def rv(self, i):
        return statistics.pstdev(self.R[i - 20: i + 1]) if i >= 20 else None

    def episodes(self, lo, hi):
        """Drawdowns from a peak with lo < fall <= hi (both negative %), as (peak, trough, recovery, fall)."""
        cum, eps, p, t = self.cum, [], 0, 0
        for i in range(1, self.N):
            if cum[i + 1] >= cum[p + 1]:
                dd = 100 * (math.exp(cum[t + 1] - cum[p + 1]) - 1)
                if lo < dd <= hi:
                    eps.append((p, t, i, dd))
                p = t = i
            elif cum[i + 1] < cum[t + 1]:
                t = i
        return eps


def reverb(S, lo=-101.0, hi=-7.0, i_from=0, i_to=None):
    i_to = S.N if i_to is None else i_to
    rows = []
    for p, t, r, dd in S.episodes(lo, hi):
        if p < max(20, i_from) or r >= i_to:
            continue
        a, b = S.rv(p), S.rv(r)
        back = next((j - r for j in range(r + 1, min(S.N, r + 253)) if S.rv(j) <= a), None) if b > a else 0
        rows.append({"peak": S.days[p], "trough": S.days[t], "recovered": S.days[r], "fall_pct": r2(dd), "days_trough_to_recovery": r - t,
                     "rv_at_peak": r2(a), "rv_at_recovery": r2(b), "still_higher": b > a, "days_until_back": back,
                     "largest_fall_next_126": r2(S.fall(r, 126)) if r + 126 < S.N else None, "_r": r})
    return rows


def reverb_summary(rows, restricted=True):
    use = [x for x in rows if x["days_trough_to_recovery"] >= 21] if restricted else rows
    hi = [x for x in use if x["still_higher"]]
    lo = [x for x in use if not x["still_higher"]]
    f = lambda v: med([x["largest_fall_next_126"] for x in v if x["largest_fall_next_126"] is not None])
    return {"n": len(use), "still_higher": len(hi), "still_higher_share": share(use, lambda x: x["still_higher"]),
            "days_until_back_median": med([x["days_until_back"] for x in hi if x["days_until_back"] is not None]),
            "not_back_within_252": sum(1 for x in hi if x["days_until_back"] is None),
            "next_126_largest_fall_median": {"still_higher": f(hi), "back": f(lo)}}, use


def aftershocks(S):
    R, N = S.R, S.N
    big = [abs(x) >= 2 for x in R]
    bg = 100 * sum(big) / N
    mains = [i for i in range(N) if R[i] <= -3 and not any(R[j] <= -3 for j in range(max(0, i - 21), i))]
    full = [i for i in mains if i + 126 < N]
    def freq(idx, a, b):
        tot = hit = 0
        for i in idx:
            seg = big[i + a: i + b + 1]
            tot += len(seg); hit += sum(seg)
        return 100 * hit / tot if tot else None
    mid = N // 2
    halves = []
    for h in ([i for i in full if i < mid], [i for i in full if i >= mid]):
        lo_, hi_ = (0, mid) if h and h[0] < mid else (mid, N)
        hbg = 100 * sum(big[lo_:hi_]) / (hi_ - lo_)
        halves.append(r2(freq(h, 1, 21) / hbg) if h and hbg else None)
    wins = {"1-5": (1, 5), "6-21": (6, 21), "1-21": (1, 21), "22-63": (22, 63), "64-126": (64, 126)}
    return {"first_day": S.days[0], "last_day": S.days[-1], "main_shocks": len(mains), "with_full_window": len(full),
            "background_share_of_2pct_days": r2(bg), "ratio_to_background": {k: r2(freq(full, a, b) / bg) for k, (a, b) in wins.items()},
            "another_3pct_fall_within_21_days": sum(1 for i in full if any(x <= -3 for x in R[i + 1: i + 22])),
            "halves_ratio_1_21_against_own_half_background": halves, "half_split_day": S.days[mid]}


def main():
    crit = json.loads((ROOT / "patterns" / "criteria.json").read_text())
    dates = json.loads((ROOT / "patterns" / "dates.json").read_text())
    rule = crit["evidence_rule"]
    fh, fac = french("F-F_Research_Data_Factors_daily")
    mkt = {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}
    alld = sorted(mkt)
    ALL = Series(alld, [mkt[d] for d in alld])
    k90 = bisect.bisect_left(alld, SPLIT)
    PRE = Series(alld[:k90], ALL.R[:k90])
    POST = Series(alld[k90:], ALL.R[k90:])
    out = {}

    # ---- reverberation, second look
    pre_rows = reverb(PRE)
    s_pre, use = reverb_summary(pre_rows)
    mid = PRE.N // 2
    hs = [share([x for x in use if (x["_r"] < mid) == first], lambda x: x["still_higher"]) for first in (True, False)]
    hn = [sum(1 for x in use if (x["_r"] < mid) == first) for first in (True, False)]
    post_rows = reverb(POST)
    all_rows = reverb(ALL)
    s_all, use_all = reverb_summary(all_rows)
    a, b = s_all["next_126_largest_fall_median"]["still_higher"], s_all["next_126_largest_fall_median"]["back"]
    midA = ALL.N // 2
    def fr(v):
        x = med([y["largest_fall_next_126"] for y in v if y["still_higher"] and y["largest_fall_next_126"] is not None])
        z = med([y["largest_fall_next_126"] for y in v if not y["still_higher"] and y["largest_fall_next_126"] is not None])
        return r2(x / z) if x is not None and z else None
    strip = lambda rows: [{k: v for k, v in x.items() if k != "_r"} for x in rows]
    out["reverberation_2"] = {
        "period": [PRE.days[0], PRE.days[-1]], "half_split_day": PRE.days[mid],
        "untouched_period_1926_1989": s_pre, "halves_share": hs, "halves_n": hn,
        "same_without_21_day_restriction": reverb_summary(pre_rows, False)[0],
        "from_1990_same_sample_as_first_round": reverb_summary(post_rows)[0],
        "from_1990_without_restriction": reverb_summary(post_rows, False)[0],
        "placebo_small_dips_2_to_7pct_1926_1989": reverb_summary(reverb(PRE, -7.0, -2.0))[0],
        "placebo_small_dips_without_restriction": reverb_summary(reverb(PRE, -7.0, -2.0), False)[0],
        "does_it_matter_1926_to_latest": {"summary": s_all, "ratio_fall_still_higher_over_back": r2(a / b) if a is not None and b else None,
                                          "halves_ratio": [fr([x for x in use_all if (x["_r"] < midA) == first]) for first in (True, False)],
                                          "ordinary_largest_fall_126_median": med([ALL.fall(i, 126) for i in range(0, ALL.N - 126, 21)])},
        "episodes_1926_1989": strip(pre_rows), "episodes_from_1990": strip(post_rows),
        "headline": {"kind": "share", "value": s_pre["still_higher_share"], "background": 50.0, "n": s_pre["n"],
                     "halves_agree": all(x is not None and x - 50 >= rule["effect"]["share"]["visible_points_over_background"] for x in hs)}}

    # ---- aftershocks, replication
    A = aftershocks(PRE)
    hr = A["halves_ratio_1_21_against_own_half_background"]
    A["first_round_method_check_from_1990"] = aftershocks(POST)["ratio_to_background"]
    A["headline"] = {"kind": "ratio", "value": A["ratio_to_background"]["1-21"], "background": 1.0, "n": A["with_full_window"],
                     "halves_agree": all(x is not None and x >= rule["effect"]["ratio"]["visible"] for x in hr)}
    out["aftershocks_2"] = A

    # ---- dates, second look
    days, R, N = POST.days, POST.R, POST.N
    pos = {d: i for i, d in enumerate(days)}
    fomc = [pos[d] for d in dates["fomc"]["dates"] if d in pos]
    fs = set(fomc)
    years = {days[i][:4] for i in fomc}
    other = [i for i in range(N) if days[i][:4] in years and i not in fs]
    up = lambda idx: share([R[i] for i in idx], lambda x: x > 0)
    fm = len(fomc) // 2
    hd = []
    for h in (fomc[:fm], fomc[fm:]):
        ys = {days[i][:4] for i in h}
        hd.append(r2(up(h) - up([i for i in other if days[i][:4] in ys])))
    vix = fetch_series("VIXCLS", "2014-12-01")
    vd, vv = [d for d, _ in vix], [v for _, v in vix]
    vchg = {vd[k]: vv[k] - vv[k - 1] for k in range(1, len(vd))}
    vo = [vchg[days[i]] for i in other if days[i] in vchg]
    vf = [vchg[days[i]] for i in fomc if days[i] in vchg]
    D = {"meetings_used": len(fomc), "up_share_fomc_days": up(fomc), "up_share_other_days": up(other),
         "mean_return_fomc_days": r2(statistics.fmean(R[i] for i in fomc)), "mean_return_other_days": round(statistics.fmean(R[i] for i in other), 3),
         "halves_points_over_other_days": hd,
         "vix_fell_share_fomc_days": share(vf, lambda x: x < 0), "vix_fell_share_other_days": share(vo, lambda x: x < 0)}
    D["headline"] = {"kind": "share", "value": D["up_share_fomc_days"], "background": D["up_share_other_days"], "n": len(fomc),
                     "halves_agree": all(x is not None and x >= rule["effect"]["share"]["visible_points_over_background"] for x in hd)}
    out["dates_2"] = D

    # ---- overlap, robustness
    k0 = bisect.bisect_left(days, "1990-01-01")
    fred = {}
    for sid in ("DCOILBRENTEU", "DGS10", "BAA10Y", "VIXCLS"):
        obs = fetch_series(sid, "1989-01-01")
        fred[sid] = ([d for d, _ in obs], [v for _, v in obs])
    def asof(sid, day, max_gap=7):
        ds, vs = fred[sid]
        k = bisect.bisect_right(ds, day) - 1
        if k < 0 or (dt.date.fromisoformat(day) - dt.date.fromisoformat(ds[k])).days > max_gap:
            return None
        return vs[k]
    def change20(sid, pct):
        res = {}
        for i, d in enumerate(days):
            x = asof(sid, d); y = asof(sid, days[i - 20]) if i >= 20 else None
            if x is not None and y is not None and (not pct or y > 0):
                res[i] = 100 * (x / y - 1) if pct else x - y
        return res
    states = {"oil": change20("DCOILBRENTEU", True), "rates": change20("DGS10", False), "credit": change20("BAA10Y", False), "vol": change20("VIXCLS", False)}
    def variant(q, step, leave=None):
        st = {k: v for k, v in states.items() if k != leave}
        cuts = {k: sorted(v.values())[int(len(v) * q)] for k, v in st.items()}
        g = {0: [], 1: [], 2: []}
        for i in range(21, N - 63, step):
            n_act = sum(1 for k, v in st.items() if i in v and v[i] >= cuts[k])
            g[min(2, n_act)].append((i, POST.fall(i, 63)))
        m = [med([f for _, f in g[k]]) for k in (0, 1, 2)]
        idx2 = [i for i, _ in g[2]]
        return {"median_largest_fall_63": {"none": m[0], "one": m[1], "two_or_more": m[2]},
                "ratio_two_or_more_over_one": r2(m[2] / m[1]) if m[2] is not None and m[1] else None,
                "samples_two_or_more": len(idx2), "separate_stretches": sum(1 for j, i in enumerate(idx2) if j == 0 or i - idx2[j - 1] > 63)}
    out["overlap_2"] = {"first_round_again_top5_every21": variant(0.95, 21), "top_10pct": variant(0.90, 21), "every_5th_day": variant(0.95, 5),
                        "leave_one_out": {k: variant(0.95, 21, k) for k in states}}

    # ---- other market: Nikkei 225 (FRED), added in the second commit of criteria2.json
    nobs = fetch_series("NIKKEI225", "1949-01-01")
    nd = [d for d, _ in nobs][1:]
    nr = [100 * (nobs[k][1] / nobs[k - 1][1] - 1) for k in range(1, len(nobs))]
    NK = Series(nd, nr)
    An = aftershocks(NK)
    hn_ = An["halves_ratio_1_21_against_own_half_background"]
    An["headline"] = {"kind": "ratio", "value": An["ratio_to_background"]["1-21"], "background": 1.0, "n": An["with_full_window"],
                      "halves_agree": all(x is not None and x >= rule["effect"]["ratio"]["visible"] for x in hn_)}
    out["aftershocks_nikkei"] = An
    nrows = reverb(NK)
    s_n, use_n = reverb_summary(nrows)
    midn = NK.N // 2
    hsn = [share([x for x in use_n if (x["_r"] < midn) == first], lambda x: x["still_higher"]) for first in (True, False)]
    out["reverberation_nikkei"] = {"period": [nd[0], nd[-1]], "summary": s_n, "halves_share": hsn,
                                   "without_21_day_restriction": reverb_summary(nrows, False)[0], "episodes": strip(nrows),
                                   "headline": {"kind": "share", "value": s_n["still_higher_share"], "background": 50.0, "n": s_n["n"],
                                                "halves_agree": all(x is not None and x - 50 >= rule["effect"]["share"]["visible_points_over_background"] for x in hsn)}}
    # contagion before 1990, first-round definition
    kn = bisect.bisect_left(nd, SPLIT)
    nk = dict(zip(nd[:kn], nr[:kn]))
    nk_days = nd[:kn]
    us_i = [i for i in range(PRE.N) if PRE.days[i] >= nk_days[0]]
    usR = [PRE.R[i] for i in us_i]
    cut_us = sorted(usR)[max(0, int(len(usR) * 0.025) - 1)]
    shock = [i for i in us_i if PRE.R[i] <= cut_us and not any(PRE.R[j] <= cut_us for j in range(max(0, i - 5), i))]
    nxt = []
    for i in shock:
        k = bisect.bisect_right(nk_days, PRE.days[i])
        if k < len(nk_days) and (dt.date.fromisoformat(nk_days[k]) - dt.date.fromisoformat(PRE.days[i])).days <= 5:
            nxt.append((i, nk[nk_days[k]]))
    vals = [v for _, v in nxt]
    mc = us_i[len(us_i) // 2]
    bg_down = share(list(nk.values()), lambda x: x < 0)
    hc = [share([v for i, v in nxt if (i < mc) == first], lambda x: x < 0) for first in (True, False)]
    nv_sorted = sorted(nk.values())
    cut_jp = nv_sorted[max(0, int(len(nv_sorted) * 0.025) - 1)]
    jp = [d for k, d in enumerate(nk_days) if nk[d] <= cut_jp and not any(nk[x] <= cut_jp for x in nk_days[max(0, k - 5): k])]
    us_same = [mkt[d] for d in jp if d in mkt]
    out["contagion_2"] = {"period": [nk_days[0], nk_days[-1]], "half_split_day": PRE.days[mc], "us_shock_threshold_pct": r2(cut_us),
                          "us_shock_days_with_nikkei_next_day": len(vals), "nikkei_next_day_down": sum(1 for v in vals if v < 0),
                          "nikkei_next_day_down_share": share(vals, lambda x: x < 0), "nikkei_next_day_median_pct": med(vals),
                          "nikkei_all_days_down_share": bg_down, "halves_down_share": hc,
                          "reverse": {"japan_shock_days": len(us_same), "us_same_date_down_share": share(us_same, lambda x: x < 0),
                                      "us_all_days_down_share": share(usR, lambda x: x < 0)},
                          "headline": {"kind": "share", "value": share(vals, lambda x: x < 0), "background": bg_down, "n": len(vals),
                                       "halves_agree": all(x is not None and x - bg_down >= rule["effect"]["share"]["visible_points_over_background"] for x in hc)}}

    for k in ("reverberation_2", "aftershocks_2", "dates_2", "aftershocks_nikkei", "reverberation_nikkei", "contagion_2"):
        h = out[k]["headline"]
        h["evidence_score"], h["effect"] = evidence(rule, h["kind"], h["value"], h["background"], h["n"], h["halves_agree"])
        print(k, json.dumps(h))
    print(json.dumps({k: {a: b for a, b in v.items() if not a.startswith("episodes")} for k, v in out.items()}, indent=1))
    out["meta"] = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "warning": "Hindsight statistics. A range of what happened, not a forecast and not a recommendation.",
                   "first_day": alld[0], "last_equity_day": alld[-1],
                   "sources": ["Kenneth R. French Data Library, Fama/French factors (daily)", "FRED, Federal Reserve Bank of St. Louis"],
                   "method": __doc__.strip()}
    (ROOT / "patterns" / "second_look.json").write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
