#!/usr/bin/env python3
"""Round 5: trend, the yield curve, information near market highs, verifiable inputs, state durations.

Hindsight; not part of the ledger; not a forecast. Everything here is fixed in
research/v4/preregistration5.json, committed before this produced any number.

  python scripts/research_v4e.py
  python scripts/research_v4e.py --fixture DIR --draws 50   # smoke test on made-up data
"""
import argparse, bisect, copy, csv, datetime as dt, json, pathlib, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import research_v4 as R  # noqa: E402
import research_v4d as R4  # noqa: E402
from collect import ROOT, confirm, fetch_series, judge, level_for  # noqa: E402

SEED, BLOCK = 20261126, 63
SKEW_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv"
TRAIN, TEST_FROM, OLD = R.TRAIN, R.TEST_FROM, ("1927-01-03", "1985-12-31")
r3 = R.r3
HI = "higher_is_riskier"


SPDR = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
SPDR_URL = "https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/navhist-us-en-{}.xlsx"


def spdr_nav(tk, fixture):
    """[(date, NAV)] ascending from the issuer's NAV history file."""
    if fixture:
        rows = list(csv.reader(open(pathlib.Path(fixture) / f"navhist_{tk}.csv")))
    else:
        import io, urllib.request
        import openpyxl
        req = urllib.request.Request(SPDR_URL.format(tk.lower()), headers={"User-Agent": "Mozilla/5.0 (research script)"})
        with urllib.request.urlopen(req, timeout=90) as r_:
            wb = openpyxl.load_workbook(io.BytesIO(r_.read()), read_only=True, data_only=True)
        rows = [[c for c in row] for row in wb.worksheets[0].iter_rows(values_only=True)]
    out = []
    for row in rows:
        if not row or row[0] is None or len(row) < 2:
            continue
        d = row[0]
        if isinstance(d, (dt.datetime, dt.date)):
            day = d.strftime("%Y-%m-%d")
        else:
            day = None
            for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    day = dt.datetime.strptime(str(d).strip(), fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
        try:
            v = float(str(row[1]).replace(",", "").replace("$", ""))
        except ValueError:
            continue
        if day and v > 0:
            out.append((day, v))
    if len(out) < 300:
        raise RuntimeError(f"only {len(out)} rows parsed")
    return sorted(out)


def auc(s, y, m):
    ok = m & ~np.isnan(s) & ~np.isnan(y)
    if ok.sum() < 100:
        return None
    v = R.auroc_fast(s[ok], y[ok])
    return None if np.isnan(v) else float(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(R.OUT))
    ap.add_argument("--draws", type=int, default=2000)
    a = ap.parse_args()
    rule = json.loads((ROOT / "rules" / "v3.json").read_text())
    loaded = R.load(a.fixture)
    mkt, fred, _, _ = loaded
    notes = {}

    def get_fred(sid):
        try:
            s = fetch_series(sid, "1950-01-01", a.fixture)
            print(sid, len(s), s[0][0], s[-1][0])
            return s
        except Exception as e:  # noqa: BLE001
            notes[sid] = f"unavailable: {e}"
            print(sid, "unavailable", e)
            return []

    def get_table(name, url, cols):
        try:
            text = (pathlib.Path(a.fixture) / f"{name}.csv").read_text() if a.fixture else R4.get(url)
            s = R4.table(text, *cols)
            if len(s) < 500:
                raise RuntimeError(f"only {len(s)} rows")
            print(name, len(s), s[0][0], s[-1][0])
            return s
        except Exception as e:  # noqa: BLE001
            notes[name] = f"unavailable: {type(e).__name__}: {e}"
            print(name, "unavailable", e)
            return []

    days = sorted(mkt)
    N = len(days)
    darr = np.array(days)
    ret = np.array([mkt[d] for d in days]) / 100
    P = np.exp(np.cumsum(np.log1p(ret)))
    nan = lambda: np.full(N, np.nan)

    def mask(a_, b_=None):
        m = darr >= a_
        return m & (darr <= b_) if b_ else m

    tr, te, old = mask(*TRAIN), mask(TEST_FROM), mask(*OLD)

    def fwd_fall(h, thr):
        out = nan()
        for i in range(N - h - 1):
            out[i] = (P[i + 1: i + h + 1].min() / P[i] - 1) * 100 <= -thr
        return out

    O1, O2, O4 = fwd_fall(63, 10), fwd_fall(21, 5), fwd_fall(126, 15)
    dd, rv = nan(), nan()
    for i in range(N):
        if i >= 251:
            dd[i] = 100 * (1 - P[i] / P[i - 251: i + 1].max())
        if i >= 20:
            rv[i] = ret[i - 20: i + 1].std() * 100
    cs = np.concatenate([[0], np.cumsum(P)])
    ma = nan()
    ma[199:] = (cs[200:] - cs[:-200]) / 200
    trend = 100 * (1 - P / ma)
    near = dd < 5

    def asof(obs, lag=0):
        x = R.asof(obs, days, lag=lag) if obs else nan()
        if obs:
            x[: bisect.bisect_left(days, obs[0][0])] = np.nan
        return x

    vix = asof(fred["VIXCLS"])
    hy = asof(fred["BAMLH0A0HYM2"])
    t10 = asof(fred["T10Y3M"])
    nfci = asof(fred["NFCI"], 5)
    baa = asof(fred["BAA10Y"])
    ciss = asof(get_table("ciss_us", R4.CISS_URL, ("TIME_PERIOD", "OBS_VALUE")), 1)
    th = {c["id"]: (c["thresholds"], c["direction"]) for c in rule["components"]}
    mins = [s["min_score"] for s in rule["states"]]
    names = [s["name"] for s in rule["states"]]
    i90 = bisect.bisect_left(days, "1990-01-02")
    base_comps = {"equity_volatility": (vix, *th["equity_volatility"]), "credit_stress": (hy, *th["credit_stress"]),
                  "yield_curve": (t10, *th["yield_curve"]), "financial_conditions": (nfci, *th["financial_conditions"]),
                  "equity_drawdown": (dd, *th["equity_drawdown"])}

    def run(comps, uncounted=()):
        rr = copy.deepcopy(rule)
        for f in rr["floors"]:
            f["not_counting"] = list(f.get("not_counting", [])) + list(uncounted)
        score, idx = nan(), np.full(N, -1)
        for i in range(i90, N):
            lv = {k: level_for(arr[i], t, d) for k, (arr, t, d) in comps.items() if not np.isnan(arr[i])}
            if "equity_volatility" not in lv:
                continue
            sc, ix = judge(rr, lv)
            score[i], idx[i] = max(sc, mins[ix]), ix
        return score, idx

    def publish(idx, m):
        pub, hist, out = None, [], np.full(N, -1)
        for i in np.flatnonzero(m):
            if idx[i] < 0:
                continue
            hist = (hist + [int(idx[i])])[-5:]
            pub = confirm(pub, hist, rule)
            out[i] = pub
        return out

    rng = np.random.default_rng(SEED)

    def boot_diff(sa, sb, y, m, sub=None):
        """90% interval of AUROC(sa) - AUROC(sb) on mask m; with `sub`, only on resampled days where sub holds."""
        ok = m & ~np.isnan(sa) & ~np.isnan(sb) & ~np.isnan(y)
        idx = np.flatnonzero(ok)
        n = len(idx)
        if n < 4 * BLOCK:
            return None
        nb = -(-n // BLOCK)
        out = []
        for _ in range(a.draws):
            st = rng.integers(0, n - BLOCK + 1, nb)
            take = idx[(st[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n]]
            if sub is not None:
                take = take[sub[take]]
            yy = y[take]
            out.append(R.auroc_fast(sa[take], yy) - (R.auroc_fast(sb[take], yy) if sb is not sa else 0.5))
        return [r3(np.nanpercentile(out, 5)), r3(np.nanpercentile(out, 95))], out

    scores, idxs = {}, {}
    scores["v3"], idxs["v3"] = run(base_comps)
    # sanity: must equal round 1's v3_long from 1990 on
    Dv = R.Data(a.fixture, loaded=loaded)
    s_old, _ = R.v3_scores(Dv, rule)
    pos = {d: i for i, d in enumerate(days)}
    mism = sum(1 for j, d in enumerate(Dv.days) if d >= "1990-01-02" and not np.isnan(s_old[j]) and scores["v3"][pos[d]] != s_old[j])
    notes["days_where_v3_differs_from_round_1"] = int(mism)

    def card(name, with_bar=True):
        s, ix = scores[name], idxs[name]
        pub = publish(ix, te)
        pubb = publish(idxs["v3"], te)
        ch = lambda p: int((np.diff(p[te & (p >= 0)]) != 0).sum())
        ladder = []
        for k in range(5):
            mm = te & (pub == k) & ~np.isnan(O1)
            ladder.append(None if mm.sum() < 30 else float(O1[mm].mean()))
        vals = [x for x in ladder if x is not None]
        e = {"train_O1": r3(auc(s, O1, tr)), "test_O1": r3(auc(s, O1, te)), "test_O2": r3(auc(s, O2, te)),
             "train_near_high_O1": r3(auc(s, O1, tr & near)), "test_near_high_O1": r3(auc(s, O1, te & near)),
             "test_share_followed_by_10pct_fall_by_state": dict(zip(names, [r3(x) for x in ladder])),
             "test_state_changes": ch(pub), "test_share_elevated_or_stress": r3(float((pub[te & (pub >= 0)] >= 3).mean()))}
        if name != "v3":
            d = boot_diff(s, scores["v3"], O1, te)
            e["test_O1_minus_v3_90"] = d[0] if d else None
            b = {k: r3(auc(scores["v3"], y, m)) for k, (y, m) in {"tr": (O1, tr), "te": (O1, te), "te2": (O2, te)}.items()}
            if with_bar:
                chk = {"test_gain_at_least_0.02_and_interval_above_zero": bool(e["test_O1"] - b["te"] >= 0.02 and d and d[0][0] > 0),
                       "train_not_more_than_0.02_below": bool(e["train_O1"] >= b["tr"] - 0.02),
                       "O2_not_more_than_0.01_below": bool(e["test_O2"] >= b["te2"] - 0.01),
                       "ladder_rises": bool(sum(1 for x, y_ in zip(vals, vals[1:]) if y_ < x) == 0),
                       "state_changes_within_25pct": bool(ch(pub) <= 1.25 * ch(pubb))}
                e["bar"] = chk
            e["acceptable_swap"] = bool(e["test_O1"] >= b["te"] - 0.01 and e["train_O1"] >= b["tr"] - 0.01 and ch(pub) <= 1.25 * ch(pubb))
        return e

    out = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "warning": "Hindsight. Not part of the ledger. Not a forecast.", "notes": notes,
           "sample": {"last_day": days[-1], "train_days": int((tr & ~np.isnan(scores["v3"])).sum()),
                      "test_days": int((te & ~np.isnan(scores["v3"]) & ~np.isnan(O1)).sum())}}

    # ---------------- part A
    tcomp = {"trend": (trend, [0, 5, 10], HI)}
    no_curve = {k: v for k, v in base_comps.items() if k != "yield_curve"}
    scores["A1"], idxs["A1"] = run(no_curve)
    scores["A2"], idxs["A2"] = run({**base_comps, **tcomp}, uncounted=["trend"])
    scores["A3"], idxs["A3"] = run({**no_curve, **tcomp}, uncounted=["trend"])
    A = {"v3": card("v3")}
    for k in ("A1", "A2", "A3"):
        A[k] = card(k)
    lev = lambda x, t: np.where(np.isnan(x), np.nan, sum((x >= v).astype(float) for v in t))
    ld, lt = lev(dd, [5, 10, 20]), lev(trend, [0, 5, 10])
    both = (ld + lt) / 2
    d_old = boot_diff(both, ld, O1, old)
    clean = {"auroc_1927_1985": {"drawdown_level": r3(auc(ld, O1, old)), "trend_level": r3(auc(lt, O1, old)), "average_of_both": r3(auc(both, O1, old)),
                                 "trend_raw": r3(auc(trend, O1, old)), "drawdown_raw": r3(auc(dd, O1, old))},
             "both_minus_drawdown_90": d_old[0] if d_old else None,
             "near_high_only": {"drawdown_raw": r3(auc(dd, O1, old & near)), "trend_raw": r3(auc(trend, O1, old & near))},
             "auroc_1990_2006": {"drawdown_raw": r3(auc(dd, O1, tr)), "trend_raw": r3(auc(trend, O1, tr))},
             "auroc_2007_on": {"drawdown_raw": r3(auc(dd, O1, te)), "trend_raw": r3(auc(trend, O1, te))}}
    clean["passes"] = bool(d_old and d_old[0][0] > 0)
    for k in ("A2", "A3"):
        A[k]["bar"]["clean_check_1927_1985"] = clean["passes"]
    for k in ("A1", "A2", "A3"):
        A[k]["passes_bar"] = all(A[k]["bar"].values())
    passed = [k for k in ("A1", "A2", "A3") if A[k]["passes_bar"]]
    curve = -t10
    recf = nan()
    for j, d in enumerate(Dv.days):
        recf[pos[d]] = Dv.O["R1"][j]
    out["part_A"] = {"candidates": A, "clean_check_trend_1927_1985": clean, "passed": passed,
                     "chosen": max(passed, key=lambda k: A[k]["train_O1"]) if passed else None,
                     "yield_curve_alone": {"recession_6_to_18_months_later": {"train": r3(auc(curve, recf, tr)), "test": r3(auc(curve, recf, te))},
                                           "O1": {"train": r3(auc(curve, O1, tr)), "test": r3(auc(curve, O1, te))}}}

    # ---------------- part B
    cand = {}
    try:
        if a.fixture:
            rows = list(csv.reader(open(pathlib.Path(a.fixture) / "IND.csv")))
            ind = {r_[0]: [float(x) for x in r_[1:]] for r_ in rows[1:]}
        else:
            from sector_sensitivity import french
            _, ind = french("49_Industry_Portfolios_daily")
        K = len(next(iter(ind.values())))
        X = np.full((N, K), np.nan)
        for d, v in ind.items():
            if d in pos and len(v) == K:
                X[pos[d]] = v
        X[X <= -99] = np.nan
        X = X / 100
        valid = ~np.isnan(X)
        lp = np.cumsum(np.where(valid, np.log1p(np.where(valid, X, 0)), 0), axis=0)
        ip = np.exp(lp)
        c2 = np.concatenate([np.zeros((1, K)), np.cumsum(ip, axis=0)])
        cv = np.concatenate([np.zeros((1, K)), np.cumsum(valid, axis=0)])
        br, dp, co = nan(), nan(), nan()
        for i in range(199, N):
            full = (cv[i + 1] - cv[i - 199]) == 200
            if full.sum() >= 20:
                m200 = (c2[i + 1] - c2[i - 199]) / 200
                br[i] = float((ip[i][full] < m200[full]).mean())
            f63 = (cv[i + 1] - cv[i - 62]) == 63
            if f63.sum() >= 20 and i >= 63:
                dp[i] = float(np.std(np.exp(lp[i][f63] - lp[i - 63][f63]) - 1))
                W = X[i - 62: i + 1][:, f63]
                sd = W.std(axis=0)
                g = sd > 0
                Z = (W[:, g] - W[:, g].mean(axis=0)) / sd[g]
                n_ = g.sum()
                co[i] = float((Z.sum(axis=1).var() - n_) / (n_ * (n_ - 1)))
        cand["breadth"], cand["dispersion"], cand["correlation"] = br, dp, co
    except Exception as e:  # noqa: BLE001
        notes["industries"] = f"unavailable: {type(e).__name__}: {e}"
        print("industries unavailable", e)
    sk = get_table("skew", SKEW_URL, (0, 1))
    if sk:
        cand["skew"] = asof(sk)

    def quarterly(obs, lag=75):
        x = nan()
        for d, v in obs:
            y_, m_ = int(d[:4]), int(d[5:7]) + 2
            end = f"{y_:04d}-{m_:02d}-31"
            k = bisect.bisect_right(days, end) - 1 + lag
            if 0 <= k < N:
                x[k:] = v
        return x

    mg = get_fred("BOGZ1FL663067003Q")
    if len(mg) > 8:
        cand["margin_growth"] = quarterly([(mg[i][0], mg[i][1] / mg[i - 4][1] - 1) for i in range(4, len(mg)) if mg[i - 4][1] > 0])
    eq, gdp = get_fred("NCBEILQ027S"), dict(get_fred("GDP"))
    if eq and gdp:
        cand["valuation"] = quarterly([(d, v / gdp[d]) for d, v in eq if d in gdp])
    for name, sid, h, pct in (("rate_rise", "DGS2", 126, False), ("policy_rate_rise", "DFF", 252, False), ("oil_rise", "DCOILWTICO", 126, True)):
        s = get_fred(sid)
        if s:
            x = asof(s)
            y_ = nan()
            if pct:
                x = np.where(x > 0, x, np.nan)
                y_[h:] = x[h:] / x[:-h] - 1
            else:
                y_[h:] = x[h:] - x[:-h]
            cand[name] = y_
    ru = nan()
    ru[252:] = P[252:] / P[:-252] - 1
    cand["run_up"], cand["tight_credit"], cand["low_vol"] = ru, -baa, -vix
    v3m = get_fred("VXVCLS")
    if v3m:
        cand["vix_term"] = vix / asof(v3m)
    Kc = len(cand)
    price_based = {"breadth", "dispersion", "correlation", "run_up"}
    B, passers = {}, []
    for name, x in cand.items():
        e = {"near_high_O1": {"train": r3(auc(x, O1, tr & near)), "test": r3(auc(x, O1, te & near)), "1927_1985": r3(auc(x, O1, old & near))},
             "near_high_O4_15pct_in_126d": {"train": r3(auc(x, O4, tr & near)), "test": r3(auc(x, O4, te & near)), "1927_1985": r3(auc(x, O4, old & near))},
             "all_days_O1": {"train": r3(auc(x, O1, tr)), "test": r3(auc(x, O1, te))},
             "first_day": days[int(np.flatnonzero(~np.isnan(x))[0])] if (~np.isnan(x)).any() else None}
        bd = boot_diff(x, x, O1, te, sub=near)
        if bd:
            v = np.array(bd[1]) + 0.5
            e["test_interval_90"] = [r3(np.nanpercentile(v, 5)), r3(np.nanpercentile(v, 95))]
            e["test_lower_end_widened_for_all_candidates"] = r3(np.nanpercentile(v, 100 * 0.10 / Kc))
        nh = e["near_high_O1"]
        ok = (nh["train"] is not None and nh["test"] is not None and nh["train"] >= 0.58 and nh["test"] >= 0.58
              and (e.get("test_lower_end_widened_for_all_candidates") or 0) > 0.5)
        if ok and name in price_based:
            ok = nh["1927_1985"] is not None and nh["1927_1985"] >= 0.55
        e["passes"] = bool(ok)
        if ok:
            passers.append(name)
        B[name] = e
    added = {}
    for name in passers:
        x = cand[name]
        cuts = [float(np.nanpercentile(x[tr], q)) for q in (50, 75, 95)]
        key = f"B_{name}"
        scores[key], idxs[key] = run({**base_comps, name: (x, cuts, HI)}, uncounted=[name])
        added[key] = card(key) | {"levels": [r3(c) for c in cuts]}
        added[key]["passes_bar"] = all(added[key]["bar"].values())
    out["part_B"] = {"candidates_tried": Kc, "v3_near_high_O1": {"train": r3(auc(scores["v3"], O1, tr & near)), "test": r3(auc(scores["v3"], O1, te & near))},
                     "base_rate_near_high": {"train": r3(float(np.nanmean(O1[tr & near]))), "test": r3(float(np.nanmean(O1[te & near]))),
                                             "1927_1985": r3(float(np.nanmean(O1[old & near])))},
                     "candidates": B, "passed": passers, "added_to_v3": added}

    # ---------------- part C
    q = lambda x: [float(np.nanpercentile(x[tr], p)) for p in (50, 75, 95)]
    C = {}
    c1 = {**base_comps, "credit_stress": (baa, q(baa), HI)}
    scores["C1"], idxs["C1"] = run(c1)
    C["C1"] = card("C1", with_bar=True) | {"levels": [r3(v) for v in q(baa)]}
    if not np.isnan(ciss[tr]).all():
        scores["C2"], idxs["C2"] = run({**c1, "financial_conditions": (ciss, q(ciss), HI)})
        scores["C3"], idxs["C3"] = run({**c1, "ciss": (ciss, q(ciss), HI)}, uncounted=["ciss"])
        for k in ("C2", "C3"):
            C[k] = card(k) | {"levels": [r3(v) for v in q(ciss)]}
    for k in C:
        C[k]["passes_bar"] = all(C[k]["bar"].values())
    out["part_C"] = C

    # ---------------- part D
    full = mask("1990-01-02")
    pub = publish(idxs["v3"], full)
    seq = [(days[i], int(pub[i])) for i in np.flatnonzero(full & (pub >= 0))]
    spells, start = [], 0
    for i in range(1, len(seq) + 1):
        if i == len(seq) or seq[i][1] != seq[start][1]:
            spells.append((seq[start][1], i - start, seq[i][1] if i < len(seq) else None, seq[start][0]))
            start = i
    Dd = {}
    for k, nm in enumerate(names):
        L = [s for s in spells if s[0] == k and s[2] is not None]
        if not L:
            continue
        ln = np.array([s[1] for s in L])
        longest = max(L, key=lambda s: s[1])
        Dd[nm] = {"spells": len(L), "median_trading_days": float(np.median(ln)), "upper_quartile": float(np.percentile(ln, 75)),
                  "longest": int(ln.max()), "longest_began": longest[3],
                  "share_ended_by_moving_up": r3(float(np.mean([s[2] > k for s in L]))),
                  "share_of_all_days": r3(float(ln.sum() / len(seq)))}
    out["part_D_state_durations_since_1990"] = Dd

    # ---------------- part E (preregistration5b.json): exploratory follow-up on breadth
    outE = None
    if "breadth" in cand:
        rng = np.random.default_rng(SEED + 5)
        x = cand["breadth"]
        cuts = [float(np.nanpercentile(x[tr], p_)) for p_ in (50, 75, 95)]
        bcomp = {"breadth": (x, cuts, HI)}
        scores["E1"], idxs["E1"] = run({**base_comps, **bcomp}, uncounted=["breadth"])
        scores["E2"], idxs["E2"] = run({**no_curve, **bcomp}, uncounted=["breadth"])
        E = {k: card(k) for k in ("E1", "E2")}
        for k in E:
            E[k]["passes_bar"] = all(E[k]["bar"].values())
            dn = boot_diff(scores[k], scores["v3"], O1, te, sub=near)
            E[k]["test_near_high_minus_v3_90"] = dn[0] if dn else None
        lb = lev(x, cuts)
        bb = (ld + lb) / 2
        da, dnh = boot_diff(bb, ld, O1, old), boot_diff(bb, ld, O1, old, sub=near)
        chk = {"all_days": {"drawdown_level": r3(auc(ld, O1, old)), "breadth_level": r3(auc(lb, O1, old)), "average_of_both": r3(auc(bb, O1, old)),
                            "both_minus_drawdown_90": da[0] if da else None},
               "near_high_days": {"drawdown_level": r3(auc(ld, O1, old & near)), "breadth_level": r3(auc(lb, O1, old & near)),
                                  "average_of_both": r3(auc(bb, O1, old & near)), "both_minus_drawdown_90": dnh[0] if dnh else None}}
        pos_all = bool(da and da[0][0] is not None and da[0][0] > 0)
        pos_nh = bool(dnh and dnh[0][0] is not None and dnh[0][0] > 0)
        strong = pos_all and any(E[k]["passes_bar"] for k in E)
        outE = {"warning": "Exploratory. Breadth was chosen after seeing round 5. Hindsight; not a forecast.", "levels": [r3(c) for c in cuts],
                "candidates": E, "check_1927_1985": chk, "reading": "strong" if strong else "worth_recording" if (pos_all or pos_nh) else "drop",
                "breadth_now": {"day": days[-1], "value": r3(x[-1])}}
    # ---------------- part G (preregistration7.json): second look at the near misses, exploratory
    outG = None
    if outE and all(k in cand for k in ("dispersion", "margin_growth", "rate_rise")):
        rng = np.random.default_rng(SEED + 7)
        qc = lambda z: [float(np.nanpercentile(z[tr], p_)) for p_ in (50, 75, 95)]
        cp = {k: (cand[k], qc(cand[k]), HI) for k in ("breadth", "dispersion", "margin_growth", "rate_rise")}
        cp["trend"] = tcomp["trend"]
        defs = {"G1": (base_comps, ["dispersion"]), "G2": (base_comps, ["margin_growth"]), "G3": (base_comps, ["rate_rise"]),
                "G4": (base_comps, ["breadth", "dispersion"]), "G5": (base_comps, ["breadth", "margin_growth"]),
                "G6": (c1, ["breadth"]), "G7": (base_comps, ["breadth", "trend"])}
        G = {}
        wide = lambda v: r3(np.nanpercentile(v, 100 * 0.10 / len(defs)))
        for k, (bc, extra) in defs.items():
            scores[k], idxs[k] = run({**bc, **{e_: cp[e_] for e_ in extra}}, uncounted=extra)
            g = card(k)
            g["passes_bar"] = all(g["bar"].values())
            d3, dE = boot_diff(scores[k], scores["v3"], O1, te), boot_diff(scores[k], scores["E1"], O1, te)
            g["test_minus_v3_lower_end_widened"] = wide(d3[1]) if d3 else None
            g["test_minus_E1_90"] = dE[0] if dE else None
            g["test_minus_E1_lower_end_widened"] = wide(dE[1]) if dE else None
            g["train_minus_E1"] = r3(g["train_O1"] - E["E1"]["train_O1"])
            g["test_minus_E1"] = r3(g["test_O1"] - E["E1"]["test_O1"])
            G[k] = g
        lv = {k: lev(v[0], v[1]) for k, v in cp.items()}
        oldc = {}
        for k in ("dispersion", "margin_growth", "rate_rise"):
            both_ = (ld + lv[k]) / 2
            dd_ = boot_diff(both_, ld, O1, old)
            okk = old & ~np.isnan(lv[k])
            oldc[k] = {"from": days[int(np.flatnonzero(okk)[0])] if okk.any() else None, "drawdown_level_same_days": r3(auc(ld, O1, okk)),
                       "with_candidate": r3(auc(both_, O1, old)), "difference_90": dd_[0] if dd_ else None,
                       "near_high_drawdown": r3(auc(ld, O1, okk & near)), "near_high_with_candidate": r3(auc(both_, O1, old & near))}
        b2, b3 = (ld + lv["breadth"]) / 2, (ld + lv["breadth"] + lv["dispersion"]) / 3
        d43 = boot_diff(b3, b2, O1, old)
        oldc["dispersion_on_top_of_breadth"] = {"drawdown_plus_breadth": r3(auc(b2, O1, old)), "plus_dispersion": r3(auc(b3, O1, old)),
                                                "difference_90": d43[0] if d43 else None}
        b4 = (ld + lv["breadth"] + lt) / 3
        d44 = boot_diff(b4, b2, O1, old)
        oldc["trend_on_top_of_breadth"] = {"drawdown_plus_breadth": r3(auc(b2, O1, old)), "plus_trend": r3(auc(b4, O1, old)),
                                           "difference_90": d44[0] if d44 else None}
        corr = {}
        for k in ("dispersion", "margin_growth", "rate_rise"):
            m_ = ~np.isnan(cand[k]) & ~np.isnan(cand["breadth"]) & (darr >= "1990-01-02")
            corr[k] = r3(R4.spearman(cand[k][m_], cand["breadth"][m_]))
        alone = [k for k in ("G1", "G2", "G3") if G[k]["passes_bar"] and (G[k]["test_minus_v3_lower_end_widened"] or -1) > 0]
        nonneg = {"G4": (oldc["dispersion_on_top_of_breadth"]["difference_90"] or [-1, -1])[1] >= 0, "G5": True,
                  "G7": (oldc["trend_on_top_of_breadth"]["difference_90"] or [-1, -1])[1] >= 0}
        adds = [k for k in ("G4", "G5", "G7") if (G[k]["test_minus_E1_lower_end_widened"] or -1) > 0 and G[k]["train_minus_E1"] >= -0.02 and nonneg[k]]
        outG = {"warning": "Exploratory. Candidates were chosen after seeing round 5. Hindsight; not a forecast.",
                "levels": {k: [r3(x) for x in v[1]] for k, v in cp.items()}, "E1_for_reference": {"train_O1": E["E1"]["train_O1"], "test_O1": E["E1"]["test_O1"],
                                                                                                "test_near_high_O1": E["E1"]["test_near_high_O1"]},
                "candidates": G, "check_before_1986": oldc, "rank_correlation_with_breadth_1990_on": corr,
                "reading": {"useful_alone": alone, "adds_to_breadth": adds,
                            "verifiable_and_no_worse": bool(G["G6"]["train_minus_E1"] >= -0.01 and G["G6"]["test_minus_E1"] >= -0.01)}}
    # ---------------- part F (preregistration6.json): a breadth measure that can be collected daily
    outF = {"warning": "Hindsight. Not part of the ledger. Not a forecast.", "funds": {}}
    navs = {}
    for tk in SPDR:
        try:
            navs[tk] = spdr_nav(tk, a.fixture)
            outF["funds"][tk] = {"first_day": navs[tk][0][0], "last_day": navs[tk][-1][0], "days": len(navs[tk])}
        except Exception as e_:  # noqa: BLE001
            outF["funds"][tk] = {"unavailable": f"{type(e_).__name__}: {e_}"[:200]}
            print(tk, "unavailable", e_)
    if len(navs) >= 9 and "breadth" in cand:
        below, have = np.zeros(N), np.zeros(N)
        for tk, obs in navs.items():
            v = asof(obs)
            c_ = np.concatenate([[0], np.cumsum(np.nan_to_num(v))])
            ok_ = np.concatenate([[0], np.cumsum(~np.isnan(v))])
            for i in range(199, N):
                if ok_[i + 1] - ok_[i - 199] == 200:
                    have[i] += 1
                    below[i] += v[i] < (c_[i + 1] - c_[i - 199]) / 200
        px = np.where(have >= 9, below / np.maximum(have, 1), np.nan)
        both_ok = ~np.isnan(px) & ~np.isnan(cand["breadth"])
        rho = R4.spearman(px[both_ok], cand["breadth"][both_ok]) if both_ok.sum() > 500 else None
        cuts6 = [0.245, 0.49, 0.857]
        scores["F1"], idxs["F1"] = run({**base_comps, "breadth": (px, cuts6, HI)}, uncounted=["breadth"])
        cov = te & ~np.isnan(px)
        f1, b1 = auc(scores["F1"], O1, cov), auc(scores["v3"], O1, cov)
        nh = auc(px, O1, cov & near)
        rngF = np.random.default_rng(SEED + 6)
        rng = rngF
        dF = boot_diff(scores["F1"], scores["v3"], O1, cov)
        chk = {"same_information": bool(rho is not None and rho >= 0.80), "near_highs": bool(nh is not None and nh >= 0.58),
               "in_the_rule": bool(f1 is not None and b1 is not None and f1 - b1 >= 0.02)}
        outF.update({"first_day_with_9_funds": days[int(np.flatnonzero(~np.isnan(px))[0])], "common_days_with_49_industry_breadth": int(both_ok.sum()),
                     "spearman_with_49_industry_breadth": r3(rho),
                     "near_high_O1_2007_on": {"proxy": r3(nh), "49_industry_breadth_same_days": r3(auc(cand["breadth"], O1, cov & near)),
                                              "v3_same_days": r3(auc(scores["v3"], O1, cov & near))},
                     "all_days_O1_2007_on": {"proxy": r3(auc(px, O1, cov)), "49_industry_breadth_same_days": r3(auc(cand["breadth"], O1, cov))},
                     "v3_plus_proxy": {"test_O1": r3(f1), "v3_same_days": r3(b1), "minus_v3_90": dF[0] if dF else None,
                                       "test_near_high_O1": r3(auc(scores["F1"], O1, cov & near)), "card": card("F1")},
                     "checks": chk, "reading": "record_live" if all(chk.values()) else "failed_a_check",
                     "proxy_now": {"day": days[int(np.flatnonzero(~np.isnan(px))[-1])], "value": r3(px[int(np.flatnonzero(~np.isnan(px))[-1])])}})
    else:
        outF["reading"] = "source_unreachable"
    pathlib.Path(a.out).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(a.out) / "results5.json").write_text(json.dumps(out, indent=1) + "\n")
    (pathlib.Path(a.out) / "results6.json").write_text(json.dumps(outF, indent=1) + "\n")
    print("F", outF["reading"], outF.get("checks"), outF.get("spearman_with_49_industry_breadth"))
    if outG:
        (pathlib.Path(a.out) / "results7.json").write_text(json.dumps(outG, indent=1) + "\n")
        print("G", outG["reading"], {k: (v["train_O1"], v["test_O1"], v["test_near_high_O1"]) for k, v in outG["candidates"].items()})
    if outE:
        (pathlib.Path(a.out) / "results5b.json").write_text(json.dumps(outE, indent=1) + "\n")
        print("E", outE["reading"], {k: (v["test_O1"], v["passes_bar"]) for k, v in outE["candidates"].items()})
    print(json.dumps({"A": {k: (v["test_O1"], v.get("passes_bar")) for k, v in A.items()}, "B_passed": passers,
                      "C": {k: (v["test_O1"], v["acceptable_swap"]) for k, v in C.items()}, "notes": notes}, indent=1))


if __name__ == "__main__":
    main()
