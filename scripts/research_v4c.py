#!/usr/bin/env python3
"""Round 3 of the v4 research: a search over 9,420 scores, corrected for the size of the search.

Hindsight; not a forecast. The search space, the way one candidate is chosen and the correction
(White's Reality Check) are fixed in research/v4/preregistration3.json, committed before this ran.
"""
import argparse, bisect, csv, datetime as dt, itertools, json, pathlib, sys, time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series  # noqa: E402
import research_v4 as R  # noqa: E402

r3 = R.r3
SEED, BLOCK, DRAWS, CHUNK = 20261126, 63, 1000, 400
COMPS = ["vol", "credit", "nfci", "drawdown252", "curve", "realized_vol21", "ebp", "leverage", "vol_jump", "credit_jump",
         "momentum63", "drawdown63"]
PRICE = ["drawdown252", "realized_vol21", "momentum63", "drawdown63"]
TRANS, AGGS, SMOOTH = ["percentile", "zscore"], ["mean", "max", "top2"], ["none", "ema10"]


def weights(n, draws, rng):
    """Moving-block bootstrap as day multiplicities, shape (draws, n)."""
    nb = -(-n // BLOCK)
    W = np.zeros((draws, n), np.float32)
    for b in range(draws):
        st = rng.integers(0, n - BLOCK + 1, nb)
        take = (st[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n]
        W[b] = np.bincount(take, minlength=n)
    return W


class Ranker:
    """AUROC of many scores at once, for day weights. Ties count one half (two opposite tie orders, averaged)."""

    def __init__(self, S, y):
        n = S.shape[0]
        self.oa = np.argsort(S, axis=0, kind="stable")
        self.ob = (n - 1 - np.argsort(S[::-1], axis=0, kind="stable"))
        self.ya, self.yb = y[self.oa].astype(np.float32), y[self.ob].astype(np.float32)
        self.y = y.astype(np.float32)

    def auroc(self, w=None):
        n = len(self.y)
        w = np.ones(n, np.float32) if w is None else w
        tot = 0.0
        for o, yo in ((self.oa, self.ya), (self.ob, self.yb)):
            wo = w[o]
            neg = wo * (1 - yo)
            before = np.cumsum(neg, axis=0, dtype=np.float64) - neg
            tot = tot + (wo * yo * before).sum(axis=0)
        w1 = float((w * self.y).sum())
        w0 = float(w.sum()) - w1
        return tot / (2 * w1 * w0)


def ema(X, alpha=2 / 11):
    out = np.empty_like(X)
    out[0] = X[0]
    for i in range(1, len(X)):
        out[i] = alpha * X[i] + (1 - alpha) * out[i - 1]
    return out


def enumerate_candidates(names):
    out = []
    for k in (1, 2, 3, 4):
        for sub in itertools.combinations(range(len(names)), k):
            for tr in TRANS:
                for ag in (AGGS if k > 1 else ["mean"]):
                    for sm in SMOOTH:
                        out.append((sub, tr, ag, sm))
    return out


def build_scores(cands, T):
    """T: {transform: (days, n_components)}. Returns (days, len(cands)) float32."""
    S = np.empty((next(iter(T.values())).shape[0], len(cands)), np.float32)
    for j, (sub, tr, ag, sm) in enumerate(cands):
        X = T[tr][:, list(sub)]
        if ag == "mean":
            s = X.mean(axis=1)
        elif ag == "max":
            s = X.max(axis=1)
        else:
            s = np.sort(X, axis=1)[:, -2:].mean(axis=1)
        S[:, j] = s
    idx = [j for j, c in enumerate(cands) if c[3] == "ema10"]
    if idx:
        S[:, idx] = ema(S[:, idx])
    return S


def search(cands, T, y, tr, te, base, W, y2=None, label=""):
    """Train and test AUROC for every candidate and the bootstrap of test gains over `base`."""
    K = len(cands)
    a_tr, a_te, a_te2 = np.empty(K), np.empty(K), np.full(K, np.nan)
    D = np.empty((W.shape[0], K), np.float32)
    rb = Ranker(base[te][:, None], y[te])
    b_obs = float(rb.auroc()[0])
    b_boot = np.array([rb.auroc(w)[0] for w in W])
    t0 = time.time()
    for c0 in range(0, K, CHUNK):
        S = build_scores(cands[c0: c0 + CHUNK], T)
        a_tr[c0: c0 + CHUNK] = Ranker(S[tr], y[tr]).auroc()
        rk = Ranker(S[te], y[te])
        a_te[c0: c0 + CHUNK] = rk.auroc()
        if y2 is not None:
            a_te2[c0: c0 + CHUNK] = Ranker(S[te], y2[te]).auroc()
        for b, w in enumerate(W):
            D[b, c0: c0 + CHUNK] = rk.auroc(w) - b_boot[b]
        print(f"{label} {min(c0 + CHUNK, K)}/{K} candidates, {time.time() - t0:.0f}s", flush=True)
    return a_tr, a_te, a_te2, D, b_obs


def reality_check(d_obs, D):
    cen = D - d_obs[None, :]
    mx = cen.max(axis=1)
    sd = D.std(axis=0)
    sd = np.where(sd > 1e-9, sd, np.inf)
    return {"largest_gain": r3(d_obs.max()), "p_value": r3((mx >= d_obs.max()).mean()),
            "gain_luck_alone_median": r3(np.median(mx)), "gain_luck_alone_95th": r3(np.percentile(mx, 95)),
            "studentized_p_value": r3(((cen / sd).max(axis=1) >= (d_obs / sd).max()).mean())}


def describe(c, names):
    sub, tr, ag, sm = c
    return {"components": [names[i] for i in sub], "transform": tr, "aggregation": ag, "smoothing": sm}


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(R.OUT))
    ap.add_argument("--draws", type=int, default=DRAWS)
    a = ap.parse_args()
    rule = json.loads((ROOT / "rules" / "v3.json").read_text())
    loaded = R.load(a.fixture)
    mkt, fred, ebp, ebp_note = loaded
    lev = fetch_series("NFCINONFINLEVERAGE", "1970-01-01", a.fixture)
    days = sorted(mkt)
    N = len(days)
    ret = np.array([mkt[d] for d in days]) / 100
    P = np.exp(np.cumsum(np.log1p(ret)))

    def ix(d):
        return bisect.bisect_left(days, d)

    def fwd_fall(h, thr):
        out = np.full(N, np.nan)
        for i in range(N - h - 1):
            out[i] = (P[i + 1: i + h + 1].min() / P[i] - 1) * 100 <= -thr
        return out

    O1, O2 = fwd_fall(63, 10), fwd_fall(21, 5)
    nan = lambda: np.full(N, np.nan)
    dd252, dd63, rv21, mom = nan(), nan(), nan(), nan()
    for i in range(N):
        if i >= 251:
            dd252[i] = 100 * (1 - P[i] / P[i - 251: i + 1].max())
        if i >= 62:
            dd63[i] = 100 * (1 - P[i] / P[i - 62: i + 1].max())
        if i >= 63:
            mom[i] = -100 * (P[i] / P[i - 63] - 1)
        if i >= 20:
            rv21[i] = ret[i - 20: i + 1].std() * 100
    vix = R.asof(fred["VIXCLS"], days)
    baa = R.asof(fred["BAA10Y"], days)
    vj, cj = nan(), nan()
    for i in range(63, N):
        if not np.isnan(vix[i - 63: i + 1]).any():
            vj[i] = vix[i] / vix[i - 63: i].mean()
        if not np.isnan(baa[i - 63: i + 1]).any():
            cj[i] = baa[i] - baa[i - 63: i].mean()
    e = nan()
    month_last = {}
    for i, d in enumerate(days):
        month_last[d[:7]] = i
    for ym, v in ebp:
        if ym in month_last and month_last[ym] + 25 < N:
            e[month_last[ym] + 25:] = v
    raw = {"vol": vix, "credit": baa, "nfci": R.asof(fred["NFCI"], days, lag=5), "drawdown252": dd252,
           "curve": -R.asof(fred["T10Y3M"], days), "realized_vol21": rv21, "ebp": e, "leverage": R.asof(lev, days, lag=5),
           "vol_jump": vj, "credit_jump": cj, "momentum63": mom, "drawdown63": dd63}

    Dv = R.Data(a.fixture, loaded=loaded)
    sc, vix_ix = R.v3_scores(Dv, rule)
    pos = {d: i for i, d in enumerate(days)}
    v3s = nan()
    for j, d in enumerate(Dv.days):
        if d >= "1990-01-02":
            v3s[pos[d]] = sc[j]

    # ---------------- parts A and B: 1990 onward, all 12 components
    ok = ~np.isnan(v3s) & ~np.isnan(O1) & ~np.isnan(O2)
    for k in COMPS:
        ok &= ~np.isnan(raw[k])
    first = int(np.flatnonzero(ok)[0])
    span = np.arange(first, int(np.flatnonzero(ok)[-1]) + 1)
    assert ok[span].all(), "gap in the common sample"
    dl = [days[i] for i in span]
    tr = np.array([d <= R.TRAIN[1] for d in dl])
    te = np.array([d >= R.TEST_FROM for d in dl])
    X = np.column_stack([raw[k][span] for k in COMPS])
    T = {"percentile": np.column_stack([R.Pct(X[tr, j])(X[:, j]) for j in range(len(COMPS))]).astype(np.float32),
         "zscore": ((X - X[tr].mean(axis=0)) / X[tr].std(axis=0)).astype(np.float32)}
    cands = enumerate_candidates(COMPS)
    y, y2, base = O1[span], O2[span], v3s[span]
    rng = np.random.default_rng(SEED)
    W = weights(int(te.sum()), a.draws, rng)
    a_tr, a_te, a_te2, D, b_te = search(cands, T, y, tr, te, base, W, y2=y2, label="main")
    b_tr = float(Ranker(base[tr][:, None], y[tr]).auroc()[0])
    b_te2 = float(Ranker(base[te][:, None], y2[te]).auroc()[0])
    d_obs = a_te - b_te

    def row(j):
        return describe(cands[j], COMPS) | {"train_auroc": r3(a_tr[j]), "test_auroc": r3(a_te[j]), "test_gain_over_v3": r3(d_obs[j]),
                                            "test_gain_interval_90": [r3(np.percentile(D[:, j], 5)), r3(np.percentile(D[:, j], 95))],
                                            "test_auroc_O2": r3(a_te2[j]), "train_rank": int((a_tr > a_tr[j]).sum()) + 1,
                                            "test_rank": int((a_te > a_te[j]).sum()) + 1}
    best_tr = int(np.argmax(a_tr))
    lo = float(np.percentile(D[:, best_tr], 5))
    part_a = {"chosen": row(best_tr),
              "bar": {"gain_at_least_0.02": bool(d_obs[best_tr] >= 0.02), "interval_above_zero": bool(lo > 0),
                      "O2_not_worse_by_0.01": bool(a_te2[best_tr] - b_te2 >= -0.01)},
              "ten_best_by_train": [row(int(j)) for j in np.argsort(-a_tr)[:10]],
              "rank_correlation_train_test": r3(spearman(a_tr, a_te))}
    part_a["bar"]["met"] = all(part_a["bar"].values())
    part_b = {"candidates": len(cands), "reality_check": reality_check(d_obs, D),
              "best_on_test": row(int(np.argmax(a_te))), "ten_best_on_test": [row(int(j)) for j in np.argsort(-a_te)[:10]],
              "share_above_v3_on_test": r3((d_obs > 0).mean()), "share_above_v3_on_train": r3((a_tr > b_tr).mean()),
              "share_above_v3_on_both": r3(((d_obs > 0) & (a_tr > b_tr)).mean()),
              "test_auroc_percentiles": {str(p): r3(np.percentile(a_te, p)) for p in (5, 25, 50, 75, 95)},
              "train_auroc_percentiles": {str(p): r3(np.percentile(a_tr, p)) for p in (5, 25, 50, 75, 95)}}
    has = lambda name: np.array([COMPS.index(name) in c[0] for c in cands])
    marg = {"by_component": {k: {"with": r3(a_te[has(k)].mean()), "without": r3(a_te[~has(k)].mean()),
                                 "train_with": r3(a_tr[has(k)].mean()), "train_without": r3(a_tr[~has(k)].mean())} for k in COMPS}}
    for name, pos_, opts in (("by_transform", 1, TRANS), ("by_aggregation", 2, AGGS), ("by_smoothing", 3, SMOOTH)):
        marg[name] = {}
        for o in opts:
            m = np.array([c[pos_] == o and (pos_ != 2 or len(c[0]) > 1) for c in cands])
            marg[name][o] = {"test": r3(a_te[m].mean()), "train": r3(a_tr[m].mean())}
    marg["by_number_of_components"] = {str(k): {"test": r3(a_te[np.array([len(c[0]) == k for c in cands])].mean()),
                                                "train": r3(a_tr[np.array([len(c[0]) == k for c in cands])].mean())} for k in (1, 2, 3, 4)}

    # ---------------- part C: prices-only family on 1927-1985
    okp = ~np.isnan(O1)
    for k in PRICE:
        okp &= ~np.isnan(raw[k])
    sp = np.arange(int(np.flatnonzero(okp)[0]), int(np.flatnonzero(okp)[-1]) + 1)
    dlp = [days[i] for i in sp]
    trp = np.array([R.TRAIN[0] <= d <= R.TRAIN[1] for d in dlp])
    old = np.array(["1927-07-01" <= d <= "1985-12-31" for d in dlp])
    Xp = np.column_stack([raw[k][sp] for k in PRICE])
    Tp = {"percentile": np.column_stack([R.Pct(Xp[trp, j])(Xp[:, j]) for j in range(len(PRICE))]).astype(np.float32),
          "zscore": ((Xp - Xp[trp].mean(axis=0)) / Xp[trp].std(axis=0)).astype(np.float32)}
    pc = enumerate_candidates(PRICE)
    M = (Tp["percentile"][:, 0] + Tp["percentile"][:, 1]) / 2
    Wp = weights(int(old.sum()), a.draws, np.random.default_rng(SEED))
    p_tr, p_old, _, Dp, m_old = search(pc, Tp, O1[sp], trp, old, M, Wp, label="prices-only")
    dp = p_old - m_old
    prow = lambda j: describe(pc[j], PRICE) | {"auroc_1990_2006": r3(p_tr[j]), "auroc_1927_1985": r3(p_old[j]), "gain_over_M_1927_1985": r3(dp[j]),
                                               "gain_interval_90": [r3(np.percentile(Dp[:, j], 5)), r3(np.percentile(Dp[:, j], 95))]}
    part_c = {"prices_only": {"candidates": len(pc), "days_1927_1985": int(old.sum()), "baseline_M_auroc_1927_1985": r3(m_old),
                              "chosen_on_1990_2006": prow(int(np.argmax(p_tr))), "best_on_1927_1985": prow(int(np.argmax(p_old))),
                              "reality_check_against_M": reality_check(dp, Dp), "rank_correlation_1990_2006_vs_1927_1985": r3(spearman(p_tr, p_old)),
                              "share_above_M_1927_1985": r3((dp > 0).mean())},
              "what_matters": marg}
    conf = {}
    full = Dv.mask("1990-01-02")
    tem = Dv.mask(R.TEST_FROM, dl[-1])
    for de in (1, 3, 5, 10, 21):
        rr = json.loads(json.dumps(rule))
        rr["confirmation"]["deescalate_after_days"] = de
        pub, hist, out = None, [], np.full(Dv.N, -1)
        for i in np.flatnonzero(full):
            if vix_ix[i] < 0:
                continue
            hist = (hist + [int(vix_ix[i])])[-de:]
            pub = R.confirm(pub, hist, rr)
            out[i] = pub
        p = out[tem & (out >= 0)]
        conf[str(de)] = {"state_changes_per_year": r3((np.diff(p) != 0).sum() / (len(p) / 252)), "share_of_days_elevated_or_above": r3((p >= 3).mean())}
    part_c["confirmation_days"] = conf

    out = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "warning": "Hindsight on revised data. Past ranges, not forecasts. See preregistration3.json.",
           "sample": {"first_day": dl[0], "last_day": dl[-1], "train_days": int(tr.sum()), "test_days": int(te.sum()), "bootstrap_draws": a.draws,
                      "share_of_test_days_with_O1": r3(y[te].mean())},
           "baseline_v3_long": {"train_auroc": r3(b_tr), "test_auroc": r3(b_te), "test_auroc_O2": r3(b_te2)},
           "part_A": part_a, "part_B": part_b, "part_C": part_c}
    o = pathlib.Path(a.out)
    o.mkdir(parents=True, exist_ok=True)
    (o / "results3.json").write_text(json.dumps(out, indent=1) + "\n")
    with open(o / "candidates3.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["components", "transform", "aggregation", "smoothing", "train_auroc", "test_auroc", "test_gain_over_v3"])
        for j, c in enumerate(cands):
            w.writerow(["+".join(COMPS[i] for i in c[0]), c[1], c[2], c[3], f"{a_tr[j]:.4f}", f"{a_te[j]:.4f}", f"{d_obs[j]:.4f}"])
    print(json.dumps({"A": part_a["chosen"], "bar": part_a["bar"], "B": part_b["reality_check"], "corr": part_a["rank_correlation_train_test"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
