#!/usr/bin/env python3
"""Round 9: the absorption ratio (Kritzman, Li, Page, Rigobon 2011) from the 49 French industries.

Hindsight; not part of the ledger; not a forecast. Everything here is fixed in
research/v4/preregistration9.json (first committed as preregistration8.json in 3f79396, renamed because another branch took the number), committed before this file existed.

  python scripts/research_v4g.py
  python scripts/research_v4g.py --fixture DIR --draws 50   # smoke test on made-up data
"""
import argparse, bisect, copy, csv, datetime as dt, json, pathlib, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import research_v4 as R  # noqa: E402
import research_v4d as R4  # noqa: E402
from collect import ROOT, confirm, judge, level_for  # noqa: E402

SEED, BLOCK = 20261134, 63
TRAIN, TEST_FROM, OLD = R.TRAIN, R.TEST_FROM, ("1927-01-03", "1985-12-31")
r3 = R.r3
HI = "higher_is_riskier"
NC = 3  # candidates, for the widened interval


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(R.OUT))
    ap.add_argument("--draws", type=int, default=2000)
    a = ap.parse_args()
    rule = json.loads((ROOT / "rules" / "v3.json").read_text())
    mkt, fred, _, _ = R.load(a.fixture)
    days = sorted(mkt)
    N = len(days)
    darr = np.array(days)
    pos = {d: i for i, d in enumerate(days)}
    ret = np.array([mkt[d] for d in days]) / 100
    P = np.exp(np.cumsum(np.log1p(ret)))
    nan = lambda: np.full(N, np.nan)

    def mask(a_, b_=None):
        m = darr >= a_
        return m & (darr <= b_) if b_ else m

    tr, te, old = mask(*TRAIN), mask(TEST_FROM), mask(*OLD)
    since90 = mask("1990-01-02")

    def fwd_fall(h, thr):
        out = nan()
        for i in range(N - h - 1):
            out[i] = (P[i + 1: i + h + 1].min() / P[i] - 1) * 100 <= -thr
        return out

    O1, O2 = fwd_fall(63, 10), fwd_fall(21, 5)
    dd, rv = nan(), nan()
    for i in range(N):
        if i >= 251:
            dd[i] = 100 * (1 - P[i] / P[i - 251: i + 1].max())
        if i >= 20:
            rv[i] = ret[i - 20: i + 1].std() * 100
    near = dd < 5

    def asof(obs, lag=0):
        x = R.asof(obs, days, lag=lag) if obs else nan()
        if obs:
            x[: bisect.bisect_left(days, obs[0][0])] = np.nan
        return x

    vix, hy, t10, nfci = asof(fred["VIXCLS"]), asof(fred["BAMLH0A0HYM2"]), asof(fred["T10Y3M"]), asof(fred["NFCI"], 5)
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

    def auc(s, y, m):
        ok = m & ~np.isnan(s) & ~np.isnan(y)
        if ok.sum() < 100:
            return None
        v = R.auroc_fast(s[ok], y[ok])
        return None if np.isnan(v) else float(v)

    rng = np.random.default_rng(SEED)

    def boot_diff(sa, sb, y, m):
        """Draws of AUROC(sa) - AUROC(sb) on mask m (sb None: AUROC(sa) itself)."""
        ok = m & ~np.isnan(sa) & ~np.isnan(y)
        if sb is not None:
            ok &= ~np.isnan(sb)
        idx = np.flatnonzero(ok)
        n = len(idx)
        if n < 4 * BLOCK:
            return None
        nb = -(-n // BLOCK)
        out = []
        for _ in range(a.draws):
            st = rng.integers(0, n - BLOCK + 1, nb)
            take = idx[(st[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n]]
            yy = y[take]
            out.append(R.auroc_fast(sa[take], yy) - (R.auroc_fast(sb[take], yy) if sb is not None else 0))
        return out

    q90 = lambda v: [r3(np.nanpercentile(v, 5)), r3(np.nanpercentile(v, 95))] if v else None
    wide = lambda v: r3(np.nanpercentile(v, 100 * 0.10 / NC)) if v else None

    # ---------------- industries
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
    cv = np.concatenate([np.zeros((1, K)), np.cumsum(valid, axis=0)])
    lp = np.cumsum(np.where(valid, np.log1p(np.where(valid, X, 0)), 0), axis=0)
    ip = np.exp(lp)
    c2 = np.concatenate([np.zeros((1, K)), np.cumsum(ip, axis=0)])

    W500 = 0.5 ** (np.arange(499, -1, -1) / 250.0)
    W500 = W500 / W500.sum()
    h1, h3, br, co, kk = nan(), nan(), nan(), nan(), nan()
    for i in range(62, N):
        if i >= 499:
            full = (cv[i + 1] - cv[i - 499]) == 500
            k_ = int(full.sum())
            if k_ >= 20:
                A = X[i - 499: i + 1][:, full]
                A = A - (W500[:, None] * A).sum(axis=0)
                ev = np.linalg.eigvalsh((A * W500[:, None]).T @ A)
                n_ = max(1, int(round(k_ / 5)))
                h1[i], kk[i] = float(ev[-n_:].sum() / ev.sum()), k_
        if i >= 251:
            full = (cv[i + 1] - cv[i - 251]) == 252
            k_ = int(full.sum())
            if k_ >= 20:
                A = X[i - 251: i + 1][:, full]
                sd = A.std(axis=0)
                g = sd > 0
                Z = (A[:, g] - A[:, g].mean(axis=0)) / sd[g]
                ev = np.linalg.eigvalsh(Z.T @ Z / 252)
                edge = (1 + np.sqrt(g.sum() / 252)) ** 2
                h3[i] = float(ev[ev > edge].sum() / ev.sum())
        if i >= 199:
            full = (cv[i + 1] - cv[i - 199]) == 200
            if full.sum() >= 20:
                m200 = (c2[i + 1] - c2[i - 199]) / 200
                br[i] = float((ip[i][full] < m200[full]).mean())
        f63 = (cv[i + 1] - cv[i - 62]) == 63
        if f63.sum() >= 20:
            A = X[i - 62: i + 1][:, f63]
            sd = A.std(axis=0)
            g = sd > 0
            Z = (A[:, g] - A[:, g].mean(axis=0)) / sd[g]
            n_ = g.sum()
            co[i] = float((Z.sum(axis=1).var() - n_) / (n_ * (n_ - 1)))
    h2 = nan()
    for i in range(251, N):
        w = h1[i - 251: i + 1]
        if not np.isnan(w).any():
            s_ = w.std()
            if s_ > 0:
                h2[i] = float((w[-15:].mean() - w.mean()) / s_)
    cand = {"H1_level": h1, "H2_shift": h2, "H3_filtered": h3}

    scores, idxs = {}, {}
    scores["v3"], idxs["v3"] = run(base_comps)
    pubb = publish(idxs["v3"], te)
    ch = lambda p: int((np.diff(p[te & (p >= 0)]) != 0).sum())
    lev = lambda x, t: np.where(np.isnan(x), np.nan, sum((x >= v).astype(float) for v in t))
    qc = lambda z: [float(np.nanpercentile(z[tr], p_)) for p_ in (50, 75, 95)]
    ld = lev(dd, [5, 10, 20])
    bcuts = qc(br)
    scores["E1"], idxs["E1"] = run({**base_comps, "breadth": (br, bcuts, HI)}, uncounted=["breadth"])

    def rank_in_train(x):
        ref = np.sort(x[tr & ~np.isnan(x)])
        out = np.searchsorted(ref, x, side="right") / max(len(ref), 1)
        return np.where(np.isnan(x), np.nan, out)

    base_po = (rank_in_train(dd) + rank_in_train(rv)) / 2
    b = {"train_O1": r3(auc(scores["v3"], O1, tr)), "test_O1": r3(auc(scores["v3"], O1, te)), "test_O2": r3(auc(scores["v3"], O2, te)),
         "test_state_changes": ch(pubb)}
    out = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "warning": "Hindsight. Not part of the ledger. Not a forecast.",
           "sample": {"last_day": days[-1], "industries_in_file": K,
                      "industries_in_500_day_window": {"first_day": days[int(np.flatnonzero(~np.isnan(kk))[0])],
                                                       "min": int(np.nanmin(kk)), "max": int(np.nanmax(kk)), "in_1990": int(kk[i90]), "last": int(kk[~np.isnan(kk)][-1])}},
           "v3": b, "E1_v3_plus_breadth": {"train_O1": r3(auc(scores["E1"], O1, tr)), "test_O1": r3(auc(scores["E1"], O1, te))},
           "price_only_base": {"train_O1": r3(auc(base_po, O1, tr)), "test_O1": r3(auc(base_po, O1, te)), "1927_1985_O1": r3(auc(base_po, O1, old))},
           "candidates": {}}
    others = {"vix": vix, "v3": scores["v3"], "breadth": br, "average_correlation_63d": co, "drawdown": dd, "realized_vol_21d": rv}
    for name, x in cand.items():
        e = {"first_day": days[int(np.flatnonzero(~np.isnan(x))[0])], "now": {"day": days[int(np.flatnonzero(~np.isnan(x))[-1])], "value": r3(x[~np.isnan(x)][-1])},
             "all_days_O1": {"train": r3(auc(x, O1, tr)), "test": r3(auc(x, O1, te)), "1927_1985": r3(auc(x, O1, old))},
             "near_high_O1": {"train": r3(auc(x, O1, tr & near)), "test": r3(auc(x, O1, te & near)), "1927_1985": r3(auc(x, O1, old & near))}}
        bt = boot_diff(x, None, O1, te)
        e["test_interval_90"], e["test_lower_end_widened"] = q90(bt), wide(bt)
        ad = e["all_days_O1"]
        e["bar_alone"] = bool(None not in ad.values() and ad["train"] >= 0.58 and ad["test"] >= 0.58 and ad["1927_1985"] >= 0.55
                              and (e["test_lower_end_widened"] or 0) > 0.5)
        # in the rule
        cuts = qc(x)
        k = "v3+" + name
        scores[k], idxs[k] = run({**base_comps, name: (x, cuts, HI)}, uncounted=[name])
        s = scores[k]
        pub = publish(idxs[k], te)
        ladder = []
        for j in range(5):
            mm = te & (pub == j) & ~np.isnan(O1)
            ladder.append(None if mm.sum() < 30 else float(O1[mm].mean()))
        vals = [v for v in ladder if v is not None]
        d = boot_diff(s, scores["v3"], O1, te)
        lx = lev(x, cuts)
        both = (ld + lx) / 2
        okk = old & ~np.isnan(lx)
        dold = boot_diff(both, ld, O1, old)
        rin = {"levels": [r3(c) for c in cuts], "train_O1": r3(auc(s, O1, tr)), "test_O1": r3(auc(s, O1, te)), "test_O2": r3(auc(s, O2, te)),
               "test_near_high_O1": r3(auc(s, O1, te & near)), "v3_test_near_high_O1": r3(auc(scores["v3"], O1, te & near)),
               "test_O1_minus_v3_90": q90(d), "test_O1_minus_v3_lower_end_widened": wide(d),
               "test_share_followed_by_10pct_fall_by_state": dict(zip(names, [r3(v) for v in ladder])),
               "test_state_changes": ch(pub),
               "clean_check_1927_1985": {"drawdown_level_same_days": r3(auc(ld, O1, okk)), "with_candidate": r3(auc(both, O1, old)),
                                         "difference_90": q90(dold)}}
        chk = {"test_gain_at_least_0.02_and_widened_interval_above_zero": bool(rin["test_O1"] - b["test_O1"] >= 0.02 and (rin["test_O1_minus_v3_lower_end_widened"] or -1) > 0),
               "train_not_more_than_0.02_below": bool(rin["train_O1"] >= b["train_O1"] - 0.02),
               "O2_not_more_than_0.01_below": bool(rin["test_O2"] >= b["test_O2"] - 0.01),
               "ladder_rises_allowing_one_tie": bool(sum(1 for u, v in zip(vals, vals[1:]) if v < u) == 0 and sum(1 for u, v in zip(vals, vals[1:]) if v == u) <= 1),
               "state_changes_within_25pct": bool(ch(pub) <= 1.25 * ch(pubb)),
               "clean_check": bool(dold and np.nanpercentile(dold, 5) > 0)}
        rin["bar"] = chk
        e["in_the_rule"] = rin
        # price only
        po = (rank_in_train(dd) + rank_in_train(rv) + rank_in_train(x)) / 3
        dte, dol = boot_diff(po, base_po, O1, te), boot_diff(po, base_po, O1, old)
        e["price_only"] = {"with_candidate": {"train_O1": r3(auc(po, O1, tr)), "test_O1": r3(auc(po, O1, te)), "1927_1985_O1": r3(auc(po, O1, old))},
                           "base_same_days": {"test_O1": r3(auc(base_po, O1, te & ~np.isnan(po))), "1927_1985_O1": r3(auc(base_po, O1, old & ~np.isnan(po)))},
                           "test_difference_90": q90(dte), "1927_1985_difference_90": q90(dol),
                           "bar": bool(dte and dol and np.nanpercentile(dte, 5) > 0 and np.nanpercentile(dol, 5) > 0)}
        # for information
        k2 = "E1+" + name
        scores[k2], idxs[k2] = run({**base_comps, "breadth": (br, bcuts, HI), name: (x, cuts, HI)}, uncounted=["breadth", name])
        dE = boot_diff(scores[k2], scores["E1"], O1, te)
        e["on_top_of_breadth_for_information"] = {"test_O1": r3(auc(scores[k2], O1, te)), "minus_E1_90": q90(dE)}
        e["rank_correlation_1990_on"] = {}
        for o_, y_ in others.items():
            m_ = since90 & ~np.isnan(x) & ~np.isnan(y_)
            e["rank_correlation_1990_on"][o_] = r3(R4.spearman(x[m_], y_[m_])) if m_.sum() > 500 else None
        in_rule = all(chk.values())
        in_rule_but_clean = all(v for k_, v in chk.items() if k_ != "clean_check")
        e["reading"] = ("propose" if e["bar_alone"] and in_rule else "replace_inputs" if e["price_only"]["bar"]
                        else "record_live" if (in_rule_but_clean or e["bar_alone"]) else "dropped")
        if e["price_only"]["bar"] and e["reading"] == "propose":
            e["also"] = "replace_inputs"
        out["candidates"][name] = e
        print(name, e["reading"], ad, e["near_high_O1"], rin["test_O1"], rin["test_O1_minus_v3_90"], e["price_only"]["test_difference_90"], e["price_only"]["1927_1985_difference_90"])
    out["outcome"] = {k: v["reading"] for k, v in out["candidates"].items()}
    pathlib.Path(a.out).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(a.out) / "results9.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["outcome"]))


if __name__ == "__main__":
    main()
