#!/usr/bin/env python3
"""The wave after a shock: how large, in what order it spread, how long it lasted.

Hindsight measurements of past episodes for the reading aids. Not part of the ledger, not a forecast.

Inputs
  - Kenneth R. French Data Library: 49 industry portfolios (daily, value weighted) and the daily market return.
  - FRED: Brent spot (EIA), 2- and 10-year Treasury yields, Moody's Baa minus 10-year spread, VIX,
    5-year breakeven inflation.
  - waves/episodes.json: named episodes with a start date quoted from a source, and the oil rule.
Definitions (the same for every episode)
  - Baseline: the close of the last trading day before the start date. Day 1 is the first trading day on or
    after the start date.
  - Size: cumulative market return and sector return minus market return at fixed horizons; the largest
    market fall from the baseline within the window and the day it happened.
  - Order: for each series, the extreme of its move within the window, and the first day the move reached
    half of that extreme ("arrival day"). Series are listed by arrival day.
  - Half-life: trading days from the extreme until half of the move had been given back, searched up to the
    half-life window. "None" means it was not given back inside that window.
  - Back at baseline: the first day after the extreme on which the series was back at or through its
    baseline level.
  - Background: the same market measurements taken from every trading day since 1990, so that a number after
    a shock can be compared with an ordinary period.
  - Rule-based oil episodes: see oil_rule in waves/episodes.json. For those, day 0 is the day the rule fired
    and the pre-shock oil price is the close 20 trading days earlier.
Standard library only. Needs FRED_API_KEY.
"""
import bisect, datetime as dt, json, math, statistics, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series  # noqa: E402
from sector_sensitivity import french, SECTORS  # noqa: E402

MACRO = {  # id: (FRED series, pct or diff)
    "brent": ("DCOILBRENTEU", "pct"),
    "yield_2y": ("DGS2", "diff"),
    "yield_10y": ("DGS10", "diff"),
    "breakeven_5y": ("T5YIE", "diff"),
    "credit_spread": ("BAA10Y", "diff"),
    "vix": ("VIXCLS", "diff"),
}
NO_PATH = {"vix"}  # daily values are not republished; only summary numbers


def r1(x):
    return None if x is None else round(x, 1)


def wave(path):
    """path: list of moves from baseline, index 0 = day 1. Returns extreme, its day, arrival day, half-life."""
    return wave_w(path, len(path))


def wave_w(path, window):
    head = path[:window]
    if not head:
        return None
    i = max(range(len(head)), key=lambda k: abs(head[k]))
    ext = head[i]
    if ext == 0:
        return None
    arrive = next(k for k, v in enumerate(head) if abs(v) >= abs(ext) / 2 and (v > 0) == (ext > 0))
    half = next((k - i for k in range(i + 1, len(path)) if abs(path[k]) <= abs(ext) / 2 or (path[k] > 0) != (ext > 0)), None)
    back = next((k + 1 for k in range(i + 1, len(path)) if path[k] == 0 or (path[k] > 0) != (ext > 0)), None)
    return {"extreme": round(ext, 2), "extreme_day": i + 1, "arrival_day": arrive + 1,
            "half_life_days": half, "back_at_baseline_day": back, "days_observed_after_extreme": len(path) - 1 - i}


def main():
    cfg = json.loads((ROOT / "waves" / "episodes.json").read_text())
    W, HL, HZ = cfg["window_trading_days"], cfg["half_life_search_trading_days"], cfg["horizons"]
    ih, ind = french("49_Industry_Portfolios_daily")
    fh, fac = french("F-F_Research_Data_Factors_daily")
    mkt = {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}
    days = sorted(d for d in ind if d >= "1989-01-01" and d in mkt)
    sec_ret = {}
    for s, names in SECTORS.items():
        idx = [ih.index(n) for n in names]
        sec_ret[s] = {d: statistics.fmean([ind[d][i] for i in idx if ind[d][i] > -99] or [mkt[d]]) for d in days}
    macro = {}
    for mid, (sid, how) in MACRO.items():
        try:
            obs = fetch_series(sid, "1988-01-01")
        except Exception as e:
            print("skip", mid, e)
            continue
        macro[mid] = ([d for d, _ in obs], [v for _, v in obs], how)

    def macro_path(mid, base_date, n):
        """moves from the last observation on or before base_date, for the next n observations"""
        ds, vs, how = macro[mid]
        b = bisect.bisect_right(ds, base_date) - 1
        if b < 0 or (dt.date.fromisoformat(base_date) - dt.date.fromisoformat(ds[b])).days > 7:
            return None, None
        seg = vs[b + 1: b + 1 + n]
        if not seg or vs[b] <= 0:
            return None, None
        return [(100 * (v / vs[b] - 1)) if how == "pct" else (v - vs[b]) for v in seg], vs[b]

    def equity(base_i, n):
        """cumulative market % and sector excess % for days base_i+1 .. base_i+n"""
        win = days[base_i + 1: base_i + 1 + n]
        cm, cs = 1.0, {s: 1.0 for s in SECTORS}
        m_path, s_path = [], {s: [] for s in SECTORS}
        for d in win:
            cm *= 1 + mkt[d] / 100
            m_path.append(100 * (cm - 1))
            for s in SECTORS:
                cs[s] *= 1 + sec_ret[s][d] / 100
                s_path[s].append(100 * (cs[s] - cm))
        return win, m_path, s_path

    def measure(base_i, with_paths):
        base_date = days[base_i]
        win, m_path, s_path = equity(base_i, HL)
        out = {"baseline": base_date, "day_1": win[0] if win else None, "last_equity_day": win[-1] if win else None,
               "equity_days": len(win)}
        if not win:
            return out
        out["market"] = {"at": {str(h): r1(m_path[h - 1]) for h in HZ if len(m_path) >= h}}
        low = min(range(min(W, len(m_path))), key=lambda k: m_path[k])
        out["market"]["largest_fall_pct"] = r1(min(0.0, m_path[low]))
        out["market"]["largest_fall_day"] = low + 1
        rec = next((k - low for k in range(low + 1, len(m_path)) if m_path[k] >= m_path[low] / 2), None) if m_path[low] < 0 else None
        out["market"]["days_to_recover_half"] = rec
        out["sectors"] = {}
        for s in SECTORS:
            w = wave_w(s_path[s], W)
            out["sectors"][s] = {"at": {str(h): r1(s_path[s][h - 1]) for h in HZ if len(s_path[s]) >= h}, **(w or {})}
        out["macro"] = {}
        for mid in macro:
            p, base = macro_path(mid, base_date, HL)
            if p:
                out["macro"][mid] = {"base": base, "at": {str(h): round(p[h - 1], 2) for h in HZ if len(p) >= h}, **(wave_w(p, W) or {})}
        order = []
        for s, v in out["sectors"].items():
            if "arrival_day" in v and abs(v["extreme"]) >= 5:
                order.append({"id": s, "type": "sector", "arrival_day": v["arrival_day"], "extreme": v["extreme"], "extreme_day": v["extreme_day"]})
        for mid, v in out["macro"].items():
            if "arrival_day" in v:
                order.append({"id": mid, "type": "macro", "arrival_day": v["arrival_day"], "extreme": v["extreme"], "extreme_day": v["extreme_day"]})
        if m_path[low] < 0:
            mw = wave_w([min(0.0, x) for x in m_path], W)
            if mw:
                order.append({"id": "market", "type": "market", "arrival_day": mw["arrival_day"], "extreme": mw["extreme"], "extreme_day": mw["extreme_day"]})
        out["order"] = sorted(order, key=lambda o: (o["arrival_day"], o["extreme_day"]))
        if with_paths:
            step = lambda p: [round(x, 1) for x in p[:HL]]
            out["paths"] = {"market": step(m_path), "sectors": {s: step(s_path[s]) for s in SECTORS},
                            "macro": {mid: [round(x, 2) for x in macro_path(mid, base_date, HL)[0]] for mid in out["macro"] if mid not in NO_PATH}}
        return out

    result = {"named": {}, "oil_rule_episodes": [], "cards": cfg["cards"]}
    for ep in cfg["episodes"]:
        i = bisect.bisect_left(days, ep["start"]) - 1
        m = measure(i, True)
        result["named"][ep["id"]] = {**{k: ep[k] for k in ("kind", "start", "en", "ko", "source")}, **m}
        print(ep["id"], json.dumps({k: m[k] for k in ("baseline", "market", "order") if k in m})[:1500])

    # rule-based oil episodes
    rule = cfg["oil_rule"]
    ds, vs, _ = macro["brent"]
    L, H, CD = rule["over_trading_days"], rule["must_be_high_of_trading_days"], rule["cooldown_trading_days"]
    last = -10 ** 9
    for k in range(H, len(vs)):
        if ds[k] < "1990-01-01" or k - last < CD:
            continue
        if vs[k] >= vs[k - L] * (1 + rule["rise_pct"] / 100) and vs[k] >= max(vs[k - H + 1: k + 1]):
            last = k
            pre = vs[k - L]
            oil = [100 * (v / pre - 1) for v in vs[k: k + 1 + HL]]  # index 0 = day 0, measured from pre-shock price
            pk = max(range(min(W + 1, len(oil))), key=lambda j: oil[j])
            half = next((j - pk for j in range(pk + 1, len(oil)) if oil[j] <= oil[pk] / 2), None)
            back = next((j for j in range(pk + 1, len(oil)) if oil[j] <= 0), None)
            again = None if half is None else next((j for j in range(pk + half + 1, len(oil)) if oil[j] > oil[pk]), None)
            e = {"current": ds[k] >= cfg.get("current_from", "9999"),
                 "back_at_pre_shock_day": back, "new_high_after_half_day": again,
                 "rise_at": {str(h): r1(oil[h]) for h in (63, 126, 252) if len(oil) > h},
                 "latest_rise_pct": r1(oil[-1]), "latest_day": len(oil) - 1,
                 "day_0": ds[k], "pre_shock_date": ds[k - L], "pre_shock_price": pre, "price_day_0": vs[k],
                 "rise_at_day_0_pct": r1(oil[0]), "peak_rise_pct": r1(oil[pk]), "peak_day": pk,
                 "half_life_days": half, "days_observed_after_peak": len(oil) - 1 - pk,
                 "oil_path": [round(x, 1) for x in oil]}
            i = bisect.bisect_right(days, ds[k]) - 1
            if i >= 0 and i + 1 < len(days) and (dt.date.fromisoformat(ds[k]) - dt.date.fromisoformat(days[i])).days <= 7:
                m = measure(i, False)
                e["equity"] = {k2: m[k2] for k2 in ("baseline", "last_equity_day", "equity_days", "market", "sectors") if k2 in m}
                for mid in ("yield_2y", "yield_10y", "vix", "credit_spread", "breakeven_5y"):
                    if mid in m.get("macro", {}):
                        e.setdefault("macro", {})[mid] = m["macro"][mid]
            result["oil_rule_episodes"].append(e)
            print("oil episode", {k2: e[k2] for k2 in e if k2 not in ("oil_path", "equity", "macro")}, e.get("equity", {}).get("market"))

    # summary over rule-based episodes with a full window
    def summ(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        return {"n": len(vals), "median": r1(statistics.median(vals)), "min": r1(vals[0]), "max": r1(vals[-1]),
                "q1": r1(vals[(len(vals) - 1) // 4]), "q3": r1(vals[(3 * (len(vals) - 1) + 3) // 4]),
                "negative": sum(v < 0 for v in vals)}
    past = [e for e in result["oil_rule_episodes"] if not e["current"]]
    full = [e for e in past if e.get("equity", {}).get("equity_days", 0) >= W]
    # the same market measurements from every trading day since 1990, as the ordinary background
    cum = [0.0]
    for d in days:
        cum.append(cum[-1] + math.log(1 + mkt[d] / 100))
    i0 = bisect.bisect_left(days, "1990-01-01")
    starts = range(i0, len(days) - W)
    base_at = {str(h): summ([100 * (math.exp(cum[i + 1 + h] - cum[i + 1]) - 1) for i in starts]) for h in HZ}
    falls = []
    for i in starts:
        lo = min(cum[i + 2: i + 2 + W]) - cum[i + 1]
        falls.append(100 * (math.exp(min(0.0, lo)) - 1))
    base_fall = summ(falls)
    S = {"episodes_with_full_window": len(full), "episodes_total": len(past),
         "any_day_since_1990": {"market_at": base_at, "market_largest_fall_pct": base_fall},
         "oil_peak_before_market_low": sum(e["peak_day"] < e["equity"]["market"]["largest_fall_day"] for e in full),
         "oil_back_at_pre_shock_day": summ([e["back_at_pre_shock_day"] for e in past]),
         "oil_not_back_at_pre_shock_within_window": sum(e["back_at_pre_shock_day"] is None for e in past),
         "oil_still_above_pre_shock_at": {h: sum(e["rise_at"].get(h, 0) > 0 for e in past) for h in ("63", "126", "252")},
         "oil_new_high_after_half": sum(e["new_high_after_half_day"] is not None for e in past),
         "market_at": {str(h): summ([e["equity"]["market"]["at"].get(str(h)) for e in full]) for h in HZ},
         "market_largest_fall_pct": summ([e["equity"]["market"]["largest_fall_pct"] for e in full]),
         "sector_excess_at": {s: {str(h): summ([e["equity"]["sectors"][s]["at"].get(str(h)) for e in full]) for h in HZ} for s in SECTORS},
         "oil_peak_rise_pct": summ([e["peak_rise_pct"] for e in past if e["days_observed_after_peak"] >= 1]),
         "oil_peak_day": summ([e["peak_day"] for e in past]),
         "oil_half_life_days": summ([e["half_life_days"] for e in past]),
         "oil_half_life_not_reached": sum(e["half_life_days"] is None for e in past)}
    result["oil_rule_summary"] = S
    print(json.dumps(S)[:3000])
    result["meta"] = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warning": "Hindsight measurements of a small number of past episodes. A range of what happened, not a forecast and not a recommendation.",
        "window_trading_days": W, "half_life_search_trading_days": HL, "oil_rule": rule,
        "last_equity_day": days[-1], "last_brent_day": ds[-1],
        "sources": ["Kenneth R. French Data Library, 49 Industry Portfolios (daily) and Fama/French factors (daily)",
                    "FRED, Federal Reserve Bank of St. Louis (Brent spot from the U.S. Energy Information Administration)"],
        "method": __doc__.strip(),
    }
    (ROOT / "waves" / "waves.json").write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
