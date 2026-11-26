#!/usr/bin/env python3
"""Research round for a possible rule v4. Hindsight; not part of the ledger; not a forecast.

Everything this script tests, and the bar a candidate has to clear, is fixed in
research/v4/preregistration.json, committed before this script produced any number.

Inputs: Kenneth R. French Data Library (daily US market return), FRED (needs FRED_API_KEY),
Federal Reserve excess bond premium CSV. Needs numpy.

  python scripts/research_v4.py                 # live
  python scripts/research_v4.py --fixture DIR   # smoke test on made-up data (MKT.csv, EBP.csv, <SERIES>.csv)
"""
import argparse, bisect, csv, datetime as dt, io, json, pathlib, sys, urllib.request

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, confirm, fetch_series, judge, level_for  # noqa: E402

OUT = ROOT / "research" / "v4"
EBP_URL = "https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv"
TRAIN = ("1990-01-02", "2006-12-29")
TEST_FROM = "2007-01-03"
UNTOUCHED = ("1986-01-02", "1989-12-29")
SEED, BLOCK, DRAWS = 20261126, 63, 2000
ORDER = ["C1_no_curve", "C7_market_only", "C2_percentile", "C3_pca_weights", "C5_realized_vol", "C6_ebp",
         "C4_correlation_weighted"]
WINDOWS = {"2007-2009": ("2007-01-03", "2009-12-31"), "2011": ("2011-06-01", "2011-12-30"),
           "2015-16": ("2015-06-01", "2016-06-30"), "2018": ("2018-01-02", "2018-12-31"),
           "2020": ("2020-01-02", "2020-12-31"), "2022": ("2022-01-03", "2022-12-30"),
           "2025": ("2025-01-02", "2025-12-31")}
r3 = lambda x: None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 3)


# ---------------------------------------------------------------- data
def load(fixture):
    if fixture:
        rows = list(csv.reader(open(pathlib.Path(fixture) / "MKT.csv")))[1:]
        mkt = {d: float(v) for d, v in rows}
    else:
        from sector_sensitivity import french
        fh, fac = french("F-F_Research_Data_Factors_daily")
        mkt = {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}
    fred = {}
    for sid in ("VIXCLS", "VXOCLS", "BAA10Y", "T10Y3M", "NFCI", "USRECD", "BAMLH0A0HYM2"):
        try:
            fred[sid] = fetch_series(sid, "1970-01-01", fixture)
        except Exception as e:  # noqa: BLE001
            print(f"{sid}: unavailable ({e})")
            fred[sid] = []
        print(sid, len(fred[sid]), fred[sid][0][0] if fred[sid] else None, fred[sid][-1][0] if fred[sid] else None)
    ebp, ebp_note = [], None
    try:
        if fixture:
            text = (pathlib.Path(fixture) / "EBP.csv").read_text()
        else:
            req = urllib.request.Request(EBP_URL, headers={"User-Agent": "risk-ledger research script"})
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        head = [h.strip().lower() for h in rows[0]]
        ci = head.index("ebp")
        for row in rows[1:]:
            try:
                d = row[0].strip()
                if "/" in d:
                    m, _, y = d.split("/")
                    ym = f"{int(y):04d}-{int(m):02d}"
                else:
                    ym = d[:7]
                ebp.append((ym, float(row[ci])))
            except (ValueError, IndexError):
                continue
        ebp.sort()
        print("EBP", len(ebp), ebp[0][0], ebp[-1][0])
    except Exception as e:  # noqa: BLE001
        ebp_note = f"{type(e).__name__}: {e}"
        print("EBP: unavailable", ebp_note)
    return mkt, fred, ebp, ebp_note


def asof(obs, days, lag=0):
    """Latest observation dated on or before the trading day `lag` days earlier. NaN when none."""
    od, ov = [d for d, _ in obs], [v for _, v in obs]
    out = np.full(len(days), np.nan)
    for i in range(len(days)):
        if i - lag < 0:
            continue
        k = bisect.bisect_right(od, days[i - lag])
        if k:
            out[i] = ov[k - 1]
    return out


class Data:
    def __init__(self, fixture):
        mkt, fred, ebp, self.ebp_note = load(fixture)
        alld = sorted(mkt)
        k0 = bisect.bisect_left(alld, "1985-01-01")
        self.days = days = alld[k0:]
        self.N = N = len(days)
        ret = np.array([mkt[d] for d in days]) / 100
        self.P = P = np.exp(np.cumsum(np.log1p(ret)))
        self.ret = ret
        vix, vxo = asof(fred["VIXCLS"], days), asof(fred["VXOCLS"], days)
        first_vix = bisect.bisect_left(days, "1990-01-02")
        self.vol = np.where(np.arange(N) >= first_vix, vix, vxo)  # VXO stands in before 1990
        self.baa = asof(fred["BAA10Y"], days)
        self.t10y3m = asof(fred["T10Y3M"], days)
        self.nfci = asof(fred["NFCI"], days, lag=5)
        self.hy = asof(fred["BAMLH0A0HYM2"], days)
        if fred["BAMLH0A0HYM2"]:
            self.hy[: bisect.bisect_left(days, fred["BAMLH0A0HYM2"][0][0])] = np.nan
        self.rec = asof(fred["USRECD"], days)
        dd = np.full(N, np.nan)
        rv = np.full(N, np.nan)
        for i in range(N):
            if i >= 251:
                dd[i] = 100 * (1 - P[i] / P[i - 251: i + 1].max())
            if i >= 20:
                rv[i] = ret[i - 20: i + 1].std() * 100
        self.dd, self.rv = dd, rv
        e = np.full(N, np.nan)
        if ebp:
            month_last = {}
            for i, d in enumerate(days):
                month_last[d[:7]] = i
            for ym, v in ebp:
                if ym in month_last:
                    a = month_last[ym] + 25
                    if a < N:
                        e[a:] = v
        self.ebp = e
        # outcomes
        fall63, fall21, vmax60, recf = (np.full(N, np.nan) for _ in range(4))
        for i in range(N):
            if i + 63 < N:
                fall63[i] = 100 * (P[i + 1: i + 64].min() / P[i] - 1)
            if i + 21 < N:
                fall21[i] = 100 * (P[i + 1: i + 22].min() / P[i] - 1)
            if i + 60 < N and not np.isnan(self.vol[i + 1: i + 61]).all():
                vmax60[i] = np.nanmax(self.vol[i + 1: i + 61])
            if i + 378 < N and not np.isnan(self.rec[i + 126: i + 379]).any():
                recf[i] = self.rec[i + 126: i + 379].max()
        self.fall63, self.fall21 = fall63, fall21
        self.O = {"O1": np.where(np.isnan(fall63), np.nan, fall63 <= -10),
                  "O2": np.where(np.isnan(fall21), np.nan, fall21 <= -5),
                  "O3": np.where(np.isnan(vmax60), np.nan, vmax60 >= 30),
                  "R1": recf}
        self.raw = {"vol": self.vol, "credit": self.baa, "nfci": self.nfci, "drawdown": dd,
                    "curve": -self.t10y3m, "realized_vol": rv, "ebp": self.ebp}

    def mask(self, a, b=None):
        i0 = bisect.bisect_left(self.days, a)
        i1 = bisect.bisect_right(self.days, b) if b else self.N
        m = np.zeros(self.N, bool)
        m[i0:i1] = True
        return m


# ---------------------------------------------------------------- measures
def auroc(score, y):
    ok = ~np.isnan(score) & ~np.isnan(y)
    s, y = score[ok], y[ok].astype(bool)
    npos, nneg = int(y.sum()), int((~y).sum())
    if not npos or not nneg:
        return None
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i: j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def auroc_fast(score, y):
    """Same as auroc for arrays without NaN, vectorised for the bootstrap."""
    y = y.astype(bool)
    npos, nneg = int(y.sum()), int((~y).sum())
    if not npos or not nneg:
        return np.nan
    u, inv, cnt = np.unique(score, return_inverse=True, return_counts=True)
    start = np.cumsum(cnt) - cnt
    ranks = start[inv] + (cnt[inv] + 1) / 2
    return (ranks[y].sum() - npos * (npos + 1) / 2) / (npos * nneg)


def boot(scores, y, base, rng):
    """Moving-block bootstrap. Returns {name: (lo, hi)} and {name: (lo, hi) of difference to base}, 90%."""
    names = list(scores)
    ok = ~np.isnan(y)
    for n in names:
        ok &= ~np.isnan(scores[n])
    idx = np.flatnonzero(ok)
    n = len(idx)
    if n < 2 * BLOCK:
        return {}, {}, n
    S = {k: scores[k][idx] for k in names}
    Y = y[idx]
    nb = -(-n // BLOCK)
    vals = {k: [] for k in names}
    for _ in range(DRAWS):
        starts = rng.integers(0, n - BLOCK + 1, nb)
        take = (starts[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n]
        yy = Y[take]
        for k in names:
            vals[k].append(auroc_fast(S[k][take], yy))
    q = lambda v: [r3(np.nanpercentile(v, 5)), r3(np.nanpercentile(v, 95))]
    ci = {k: q(np.array(vals[k])) for k in names}
    diff = {k: q(np.array(vals[k]) - np.array(vals[base])) for k in names if k != base}
    return ci, diff, n


# ---------------------------------------------------------------- scores
def v3_scores(D, rule, drop=()):
    """v3 thresholds on the long series. Returns (score lifted to the floor state, indicated state index)."""
    th = {c["id"]: c for c in rule["components"]}
    mins = [s["min_score"] for s in rule["states"]]
    score, idx = np.full(D.N, np.nan), np.full(D.N, -1)
    src = {"equity_volatility": D.vol, "credit_stress": D.hy, "yield_curve": D.t10y3m,
           "financial_conditions": D.nfci, "equity_drawdown": D.dd}
    for i in range(D.N):
        lv = {}
        for cid, arr in src.items():
            if cid in drop or np.isnan(arr[i]):
                continue
            lv[cid] = level_for(arr[i], th[cid]["thresholds"], th[cid]["direction"])
        if "equity_volatility" not in lv:
            continue
        sc, ix = judge(rule, lv)
        score[i], idx[i] = max(sc, mins[ix]), ix
    return score, idx


class Pct:
    """Frozen percentile transform: cutpoints at every 5th percentile of the training days."""

    def __init__(self, x_train):
        x = x_train[~np.isnan(x_train)]
        p = np.linspace(0, 1, 21)
        c = np.percentile(x, p * 100)
        u = np.unique(c)
        self.c = u
        self.p = np.array([p[c == v].mean() for v in u])

    def __call__(self, x):
        out = np.interp(x, self.c, self.p) if len(self.c) > 1 else np.full(len(x), 0.5)
        return np.where(np.isnan(x), np.nan, out)


def build(D, rule, tr):
    """All scores with every fitted quantity taken from the days in mask `tr`. Returns scores, indicated states, notes."""
    notes = {}
    scores, ind = {}, {}
    scores["v3_long"], ind["v3_long"] = v3_scores(D, rule)
    scores["C1_no_curve"], ind["C1_no_curve"] = v3_scores(D, rule, drop=("yield_curve",))
    a0 = auroc(scores["v3_long"][tr], D.O["O1"][tr])
    a1 = auroc(scores["C1_no_curve"][tr], D.O["O1"][tr])
    use_curve = not (a0 is not None and a1 is not None and a1 > a0)
    notes["train_auroc_O1_v3_long"], notes["train_auroc_O1_C1"] = r3(a0), r3(a1)
    notes["curve_included_in_percentile_candidates"] = use_curve
    P = {k: Pct(v[tr])(v) for k, v in D.raw.items() if not np.isnan(v[tr]).all()}
    notes["cutpoints"] = {k: {"values": [r3(x) for x in Pct(D.raw[k][tr]).c], "percentiles": [r3(x) for x in Pct(D.raw[k][tr]).p]}
                          for k in P}
    base = ["vol", "credit", "nfci", "drawdown"] + (["curve"] if use_curve else [])
    sets = {"C2_percentile": base, "C7_market_only": [c for c in base if c != "nfci"],
            "C5_realized_vol": base + ["realized_vol"]}
    if "ebp" in P:
        sets["C6_ebp"] = base + ["ebp"]
    notes["components"] = dict(sets)
    for name, comps in sets.items():
        scores[name] = 100 * np.mean([P[c] for c in comps], axis=0)
    # C3: first principal component weights
    X = np.column_stack([P[c] for c in base])
    okt = tr & ~np.isnan(X).any(axis=1)
    Xc = X[okt] - X[okt].mean(axis=0)
    w, v = np.linalg.eigh(np.cov(Xc.T))
    pc = v[:, -1] * (1 if v[:, -1].sum() >= 0 else -1)
    wts = np.clip(pc, 0, None)
    wts = wts / wts.sum()
    notes["pca"] = {"weights": dict(zip(base, [r3(x) for x in wts])), "share_of_variance": r3(w[-1] / w.sum())}
    scores["C3_pca_weights"] = 100 * X @ wts
    notes["components"]["C3_pca_weights"] = base
    # C4: correlation weighted
    Z = X - 0.5
    S = (Z[okt].T @ Z[okt]) / okt.sum()
    c4 = np.full(D.N, np.nan)
    n = len(base)
    for i in range(D.N):
        z = Z[i]
        if np.isnan(z).any():
            continue
        S = 0.97 * S + 0.03 * np.outer(z, z)
        sd = np.sqrt(np.diag(S))
        C = S / np.outer(sd, sd)
        s = np.clip(z, 0, None)
        c4[i] = 100 * np.sqrt(max(0.0, s @ C @ s)) / (0.5 * n)
    scores["C4_correlation_weighted"] = c4
    notes["components"]["C4_correlation_weighted"] = base
    # state boundaries: same share of training days at or above each state as v3_long
    v3i = ind["v3_long"]
    okv = tr & (v3i >= 0)
    shares = [float((v3i[okv] >= k).mean()) for k in range(1, 5)]
    notes["v3_long_train_share_at_or_above"] = dict(zip(["Guarded", "Watch", "Elevated", "Stress"], [r3(x) for x in shares]))
    notes["cutoffs"] = {}
    for name in scores:
        if name in ("v3_long", "C1_no_curve"):
            continue
        s = scores[name]
        st = s[tr & ~np.isnan(s)]
        cuts = [float(np.quantile(st, 1 - sh)) if sh > 0 else float("inf") for sh in shares]
        notes["cutoffs"][name] = [r3(c) if np.isfinite(c) else None for c in cuts]
        ix = np.full(D.N, -1)
        good = ~np.isnan(s)
        ix[good] = np.sum(s[good, None] >= np.array(cuts)[None, :], axis=1)
        ind[name] = ix
    return scores, ind, notes


def publish(ind_idx, rule, m):
    """Apply the v3 confirmation step over the days in mask m, starting fresh."""
    pub, hist, out = None, [], np.full(len(ind_idx), -1)
    for i in np.flatnonzero(m):
        if ind_idx[i] < 0:
            continue
        hist = (hist + [int(ind_idx[i])])[-5:]
        pub = confirm(pub, hist, rule)
        out[i] = pub
    return out


def evaluate(D, scores, ind, rule, m, base="v3_long", rng=None, names=None):
    names = names or list(scores)
    res = {"days": int(m.sum()), "first": D.days[np.flatnonzero(m)[0]], "last": D.days[np.flatnonzero(m)[-1]], "auroc": {}}
    for o in ("O1", "O2", "O3", "R1"):
        y = D.O[o]
        mm = m & ~np.isnan(y)
        entry = {"days_scored": int(mm.sum()), "share_of_days_with_outcome": r3(np.nanmean(y[mm])) if mm.any() else None,
                 "auroc": {k: r3(auroc(scores[k][mm], y[mm])) for k in names}}
        if rng is not None and mm.any():
            ci, diff, n = boot({k: scores[k][mm] for k in names}, y[mm], base, rng)
            entry["interval_90"], entry["difference_to_v3_long_interval_90"], entry["days_in_bootstrap"] = ci, diff, n
        res["auroc"][o] = entry
    res["states"] = {}
    full = D.mask("1990-01-02") if m[np.flatnonzero(m)[0]] and D.days[np.flatnonzero(m)[0]] >= "1990" else m
    for k in names:
        pub = publish(ind[k], rule, full)
        idx = np.flatnonzero(m & (pub >= 0))
        p = pub[idx]
        y = D.O["O1"][idx]
        f = D.fall63[idx]
        by = []
        for s in range(5):
            sel = (p == s) & ~np.isnan(y)
            by.append({"state": rule["states"][s]["name"], "days": int((p == s).sum()),
                       "share_O1": r3(y[sel].mean()) if sel.any() else None,
                       "fall63_median": r3(np.median(f[sel])) if sel.any() else None,
                       "fall63_5th_percentile": r3(np.percentile(f[sel], 5)) if sel.any() else None})
        # ladder with small states merged into the neighbour below (or above for the lowest)
        groups = [[s] for s in range(5) if ((p == s) & ~np.isnan(y)).sum() > 0]
        cnt = lambda g: int((np.isin(p, g) & ~np.isnan(y)).sum())
        changed = True
        while changed and len(groups) > 1:
            changed = False
            for gi, g in enumerate(groups):
                if cnt(g) < 60:
                    j = gi - 1 if gi > 0 else 1
                    groups[min(gi, j)] = sorted(groups[gi] + groups[j])
                    del groups[max(gi, j)]
                    changed = True
                    break
        ladder = [float(y[np.isin(p, g) & ~np.isnan(y)].mean()) for g in groups]
        years = len(idx) / 252
        changes = int((np.diff(p) != 0).sum())
        timing = {}
        for wname, (a, b) in WINDOWS.items():
            wi = [i for i in idx if a <= D.days[i] <= b]
            if not wi:
                continue
            fe = next((D.days[i] for i in wi if pub[i] >= 3), None)
            fs = next((D.days[i] for i in wi if pub[i] >= 4), None)
            timing[wname] = {"first_elevated_or_above": fe, "first_stress": fs}
        res["states"][k] = {"by_state": by, "ladder_groups": [[rule["states"][s]["name"] for s in g] for g in groups],
                            "ladder_share_O1": [r3(x) for x in ladder],
                            "ladder_rises": all(b > a for a, b in zip(ladder, ladder[1:])),
                            "state_changes": changes, "state_changes_per_year": r3(changes / years) if years else None,
                            "timing": timing}
    return res


def market_context(D):
    out = {}
    for wname, (a, b) in WINDOWS.items():
        i0, i1 = bisect.bisect_left(D.days, a), bisect.bisect_right(D.days, b)
        if i1 - i0 < 5:
            continue
        seg = D.P[i0:i1]
        run = np.maximum.accumulate(seg)
        dd = seg / run - 1
        t = int(dd.argmin())
        pk = int(seg[: t + 1].argmax())
        out[wname] = {"market_peak": D.days[i0 + pk], "market_trough": D.days[i0 + t], "fall_pct": r3(100 * dd[t])}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    rule = json.loads((ROOT / "rules" / "v3.json").read_text())
    D = Data(a.fixture)
    rng = np.random.default_rng(SEED)
    tr = D.mask(*TRAIN)
    last_scored = D.days[np.flatnonzero(~np.isnan(D.O["O1"]))[-1]]
    te = D.mask(TEST_FROM, last_scored)
    un = D.mask(*UNTOUCHED)

    scores, ind, notes = build(D, rule, tr)
    cands = [c for c in ORDER if c in scores]
    train = evaluate(D, scores, ind, rule, tr)
    tr_auc = train["auroc"]["O1"]["auroc"]
    best = max(tr_auc[c] for c in cands if tr_auc[c] is not None)
    chosen = next(c for c in cands if tr_auc[c] is not None and tr_auc[c] >= best - 0.005)

    test = evaluate(D, scores, ind, rule, te, rng=rng)
    untouched = evaluate(D, scores, ind, rule, un)
    # reverse split, robustness only
    rtr = D.mask(TEST_FROM, last_scored)
    rscores, rind, rnotes = build(D, rule, rtr)
    reverse = evaluate(D, rscores, rind, rule, tr, rng=np.random.default_rng(SEED))

    t1 = test["auroc"]["O1"]
    d_lo = (t1.get("difference_to_v3_long_interval_90") or {}).get(chosen, [None, None])[0]
    gap = lambda o: test["auroc"][o]["auroc"][chosen] - test["auroc"][o]["auroc"]["v3_long"]
    sc, sb = test["states"][chosen], test["states"]["v3_long"]
    bar = {
        "O1_gain_at_least_0.02": bool(gap("O1") >= 0.02), "O1_gain": r3(gap("O1")),
        "O1_gain_interval_above_zero": bool(d_lo is not None and d_lo > 0),
        "O2_not_worse_by_0.01": bool(gap("O2") >= -0.01), "O2_gain": r3(gap("O2")),
        "O3_not_worse_by_0.01": bool(gap("O3") >= -0.01), "O3_gain": r3(gap("O3")),
        "ladder_rises": bool(sc["ladder_rises"]),
        "state_changes_within_125pct": bool(sc["state_changes_per_year"] <= 1.25 * sb["state_changes_per_year"]),
    }
    bar["met"] = all(v for k, v in bar.items() if isinstance(v, bool))

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warning": "Hindsight on revised data. Past ranges, not forecasts. See preregistration.json for what was fixed in advance.",
        "data": {"market_first": D.days[0], "market_last": D.days[-1], "last_day_scored_on_O1": last_scored,
                 "ebp": "used" if "C6_ebp" in scores else f"not run ({D.ebp_note})"},
        "fitted_on_train": notes, "chosen_on_train": chosen, "train": train, "test": test, "bar": bar,
        "untouched_1986_1989": untouched, "reverse_split": {"fitted_on": "2007 onward", "scored_on": "1990-2006",
                                                             "fitted": rnotes, "result": reverse},
        "market_context": market_context(D),
    }
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    names = rule["states"]
    full = D.mask("1990-01-02")
    pubs = {k: publish(ind[k], rule, full) for k in ("v3_long", chosen)}
    with open(out / "daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "v3_long_score", "v3_long_state", f"{chosen}_score", f"{chosen}_state"])
        for i in np.flatnonzero(full):
            if pubs["v3_long"][i] < 0 or pubs[chosen][i] < 0:
                continue
            w.writerow([D.days[i], int(scores["v3_long"][i]), names[pubs["v3_long"][i]]["name"],
                        round(float(scores[chosen][i]), 1), names[pubs[chosen][i]]["name"]])
    print("chosen on train:", chosen)
    print("train AUROC O1:", tr_auc)
    print("test AUROC O1:", t1["auroc"])
    print("bar:", bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
