#!/usr/bin/env python3
"""Round 2 of the v4 research: slow indicators and a long-history replication. Hindsight; not a forecast.

Fixed in research/v4/preregistration2.json before this script produced any number.
"""
import argparse, bisect, json, pathlib, sys, datetime as dt

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series  # noqa: E402
import research_v4 as R  # noqa: E402

r3 = R.r3
SEED, DRAWS = 20261126, 2000


def boot1(score, y, block, rng):
    ok = ~np.isnan(score) & ~np.isnan(y)
    s, yy = score[ok], y[ok]
    n = len(s)
    if n < 2 * block:
        return None
    nb = -(-n // block)
    vals = []
    for _ in range(DRAWS):
        st = rng.integers(0, n - block + 1, nb)
        take = (st[:, None] + np.arange(block)[None, :]).ravel()[:n]
        vals.append(R.auroc_fast(s[take], yy[take]))
    return [r3(np.nanpercentile(vals, 5)), r3(np.nanpercentile(vals, 95))]


def cell(score, y, m, block, rng):
    mm = m & ~np.isnan(score) & ~np.isnan(y)
    if mm.sum() < 2 * block:
        return {"days": int(mm.sum()), "auroc": None}
    return {"days": int(mm.sum()), "share_of_days_with_outcome": r3(y[mm].mean()),
            "auroc": r3(R.auroc(score[mm], y[mm])), "interval_90": boot1(score[mm], y[mm], block, rng)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(R.OUT))
    a = ap.parse_args()
    rule = json.loads((ROOT / "rules" / "v3.json").read_text())
    loaded = R.load(a.fixture)
    mkt, fred, ebp, ebp_note = loaded
    try:
        lev = fetch_series("NFCINONFINLEVERAGE", "1970-01-01", a.fixture)
    except Exception as e:  # noqa: BLE001
        print("NFCINONFINLEVERAGE unavailable", e)
        lev = []
    days = sorted(mkt)
    N = len(days)
    ret = np.array([mkt[d] for d in days]) / 100
    P = np.exp(np.cumsum(np.log1p(ret)))
    rng = np.random.default_rng(SEED)

    def mask(a_, b_=None):
        m = np.zeros(N, bool)
        m[bisect.bisect_left(days, a_): (bisect.bisect_right(days, b_) if b_ else N)] = True
        return m

    def fwd_fall(h, thr):
        out = np.full(N, np.nan)
        for i in range(N - h - 1):
            out[i] = (P[i + 1: i + h + 1].min() / P[i] - 1) * 100 <= -thr
        return out

    O1, O2, O5 = fwd_fall(63, 10), fwd_fall(21, 5), fwd_fall(504, 20)
    rec = R.asof(fred["USRECD"], days)
    R1 = np.full(N, np.nan)
    for i in range(N - 379):
        seg = rec[i + 126: i + 379]
        if not np.isnan(seg).any():
            R1[i] = seg.max()

    dd, rv21, rv252 = (np.full(N, np.nan) for _ in range(3))
    for i in range(N):
        if i >= 251:
            dd[i] = 100 * (1 - P[i] / P[i - 251: i + 1].max())
            rv252[i] = ret[i - 251: i + 1].std() * 100
        if i >= 20:
            rv21[i] = ret[i - 20: i + 1].std() * 100
    lowvol = np.full(N, np.nan)
    for i in range(251 + 2520, N):
        lowvol[i] = -rv252[i] / np.median(rv252[i - 2520: i])
    e = np.full(N, np.nan)
    month_last = {}
    for i, d in enumerate(days):
        month_last[d[:7]] = i
    for ym, v in ebp:
        if ym in month_last and month_last[ym] + 25 < N:
            e[month_last[ym] + 25:] = v
    S = {"S1_curve": -R.asof(fred["T10Y3M"], days), "S2_nonfinancial_leverage": R.asof(lev, days, lag=5) if lev else np.full(N, np.nan),
         "S3_low_volatility": lowvol, "S4_ebp": e}
    untouched = {"S1_curve": ("1982-01-04", "1989-12-29"), "S2_nonfinancial_leverage": ("1971-01-04", "1989-12-29"),
                 "S3_low_volatility": ("1937-01-04", "1989-12-29"), "S4_ebp": ("1973-01-02", "1989-12-29")}

    # v3_long on the round-1 calendar, mapped to this one
    D = R.Data(a.fixture, loaded=loaded)
    sc, ix = R.v3_scores(D, rule)
    pub = R.publish(ix, rule, D.mask("1990-01-02"))
    pos = {d: i for i, d in enumerate(days)}
    v3s, v3p = np.full(N, np.nan), np.full(N, -1)
    for j, d in enumerate(D.days):
        if D.days[j] >= "1990-01-02":
            v3s[pos[d]], v3p[pos[d]] = sc[j], pub[j]

    last5 = days[np.flatnonzero(~np.isnan(O5))[-1]]
    periods = {"1990-2006": mask("1990-01-02", "2006-12-29"), "2007 onward": mask("2007-01-03", last5)}
    part_a = {}
    for k, s in S.items():
        per = {"untouched " + untouched[k][0][:4] + "-1989": mask(*untouched[k]), **periods}
        part_a[k] = {"O5": {p: cell(s, O5, m, 504, rng) for p, m in per.items()},
                     "R1": {p: cell(s, R1, m, 504, rng) for p, m in per.items()}}
        cells = list(part_a[k]["O5"].values())
        ok = all(c["auroc"] is not None and c["auroc"] >= 0.60 for c in cells) and \
            cells[0].get("interval_90") is not None and cells[0]["interval_90"][0] > 0.50
        part_a[k]["bar_met"] = bool(ok)
    part_a["reference_v3_long_score"] = {"O5": {p: cell(v3s, O5, m, 504, rng) for p, m in periods.items()},
                                         "R1": {p: cell(v3s, R1, m, 504, rng) for p, m in periods.items()}}
    low = (v3p >= 0) & (v3p <= 1)
    from_calm = {}
    for k, s in S.items():
        from_calm[k] = {o: {p: cell(s, y, m & low, b, rng) for p, m in {**periods, "1990 onward": mask("1990-01-02", last5)}.items()}
                        for o, y, b in (("O1", O1, 63), ("O5", O5, 504))}
    calm_base = {p: {"days": int((m & low).sum()), "share_O1": r3(np.nanmean(O1[m & low])), "share_O5": r3(np.nanmean(O5[m & low]))}
                 for p, m in periods.items()}

    # part B
    tr = mask(*R.TRAIN)
    M = 100 * (R.Pct(dd[tr])(dd) + R.Pct(rv21[tr])(rv21)) / 2
    u = mask("1927-07-01", "1985-12-31")
    ui = np.flatnonzero(u)
    half = days[ui[len(ui) // 2]]
    pb = {"score": "average of percentile(drawdown) and percentile(21-day realized volatility), cutpoints from 1990-2006",
          "untouched_1927_1985": {o: cell(M, y, u, 63, rng) for o, y in (("O1", O1), ("O2", O2))},
          "halves": {f"1927 to {half}": {"O1": cell(M, O1, mask("1927-07-01", half), 63, rng)},
                     f"{half} to 1985": {"O1": cell(M, O1, mask(half, "1985-12-31"), 63, rng)}}}
    q = np.nanquantile(M[u], [0.2, 0.4, 0.6, 0.8])
    fifth = np.sum(M[:, None] >= q[None, :], axis=1)
    pb["share_O1_by_fifth_of_M_1927_1985"] = [r3(np.nanmean(O1[u & (fifth == f) & ~np.isnan(M)])) for f in range(5)]
    last1 = days[np.flatnonzero(~np.isnan(O1))[-1]]
    pb["beside"] = {p: {"M": {o: cell(M, y, m, 63, rng) for o, y in (("O1", O1), ("O2", O2))},
                        "v3_long": {o: cell(v3s, y, m, 63, rng) for o, y in (("O1", O1), ("O2", O2))}}
                    for p, m in {"1990-2006": mask("1990-01-02", "2006-12-29"), "2007 onward": mask("2007-01-03", last1)}.items()}

    out = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "warning": "Hindsight on revised data. Past ranges, not forecasts. See preregistration2.json.",
           "data": {"market_first": days[0], "market_last": days[-1], "last_day_scored_on_O5": last5,
                    "leverage_subindex_observations": len(lev), "ebp_observations": len(ebp), "ebp_note": ebp_note},
           "part_A_slow_indicators": part_a, "from_calm_or_guarded": from_calm, "calm_or_guarded_base_rates": calm_base,
           "part_B_replication": pb}
    pathlib.Path(a.out).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(a.out) / "results2.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(part_a, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
