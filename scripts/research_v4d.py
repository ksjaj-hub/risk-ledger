#!/usr/bin/env python3
"""Round 4: AFMX (v3) scored against widely used indicators. Hindsight; not part of the ledger; not a forecast.

Everything here is fixed in research/v4/preregistration4.json, committed before this produced any number.

  python scripts/research_v4d.py
  python scripts/research_v4d.py --fixture DIR --draws 50   # smoke test on made-up data
"""
import argparse, bisect, csv, datetime as dt, io, json, pathlib, sys, urllib.request

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import research_v4 as R  # noqa: E402
from collect import ROOT, fetch_series  # noqa: E402

SEED, BLOCK = 20261126, 63
OFR_URL = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"
CISS_URL = "https://data-api.ecb.europa.eu/service/data/CISS/D.US.Z0Z.4F.EC.SS_CIN.IDX?format=csvdata"
r3 = R.r3


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "risk-ledger research script"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def iso(s):
    s = s.strip()
    if "/" in s:
        m, d, y = s.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return s[:10]


def table(text, date_col, val_col):
    rows = list(csv.reader(io.StringIO(text)))
    head = [h.strip() for h in rows[0]]
    di = head.index(date_col) if isinstance(date_col, str) else date_col
    vi = head.index(val_col) if isinstance(val_col, str) else val_col
    out = []
    for row in rows[1:]:
        try:
            out.append((iso(row[di]), float(row[vi])))
        except (ValueError, IndexError):
            continue
    return sorted(out)


def spearman(a, b):
    rk = lambda x: np.argsort(np.argsort(x, kind="mergesort"), kind="mergesort").astype(float)
    if len(a) < 3 or np.all(a == a[0]) or np.all(b == b[0]):
        return np.nan
    return float(np.corrcoef(rk(a), rk(b))[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(R.OUT))
    ap.add_argument("--draws", type=int, default=2000)
    a = ap.parse_args()
    rule = json.loads((ROOT / "rules" / "v3.json").read_text())
    D = R.Data(a.fixture)
    days, N, P = D.days, D.N, D.P
    afmx, _ = R.v3_scores(D, rule)
    notes, ind = {}, {"afmx": afmx}

    def fred(sid):
        try:
            s = fetch_series(sid, "1970-01-01", a.fixture)
            print(sid, len(s), s[0][0], s[-1][0])
            return s
        except Exception as e:  # noqa: BLE001
            notes[sid] = f"unavailable: {e}"
            print(sid, "unavailable", e)
            return []

    ind["vix"] = np.where(np.array(days) >= "1990-01-02", D.vol, np.nan)
    v3m = fred("VXVCLS")
    if v3m:
        ind["vix_term"] = ind["vix"] / R.asof(v3m, days)
        ind["vix_term"][: bisect.bisect_left(days, v3m[0][0])] = np.nan
    ind["nfci"] = D.nfci
    for name, sid in (("anfci", "ANFCI"), ("stlfsi", "STLFSI4")):
        s = fred(sid)
        if s:
            ind[name] = R.asof(s, days, lag=5)
    s = fred("KCFSI")
    if s:
        last = {}
        for i, d in enumerate(days):
            last[d[:7]] = i
        x = np.full(N, np.nan)
        for d, v in s:
            if d[:7] in last and last[d[:7]] + 10 < N:
                x[last[d[:7]] + 10:] = v
        ind["kcfsi"] = x
    for name, url, lag, cols in (("ofr_fsi", OFR_URL, 2, ("Date", "OFR FSI")), ("ciss_us", CISS_URL, 1, ("TIME_PERIOD", "OBS_VALUE"))):
        try:
            text = (pathlib.Path(a.fixture) / f"{name}.csv").read_text() if a.fixture else get(url)
            s = table(text, *cols)
            if len(s) < 500:
                raise RuntimeError(f"only {len(s)} rows")
            print(name, len(s), s[0][0], s[-1][0])
            ind[name] = R.asof(s, days, lag=lag)
        except Exception as e:  # noqa: BLE001
            notes[name] = f"unavailable: {type(e).__name__}: {e}"
            print(name, "unavailable", e)
    ind["credit_spread"] = D.baa
    ind["yield_curve"] = -D.t10y3m
    ind["drawdown"] = D.dd
    ma = np.full(N, np.nan)
    cs = np.concatenate([[0], np.cumsum(P)])
    ma[199:] = (cs[200:] - cs[:-200]) / 200
    ind["below_200dma"] = 100 * (1 - P / ma)
    ind["realized_vol"] = D.rv
    names = list(ind)

    y1, y2, fall = D.O["O1"], D.O["O2"], D.fall63
    near_high = D.dd < 5

    def measures(S, idx):
        """All measures for score array S on day indices idx (no NaN there)."""
        s, a1, a2, f, nh = S[idx], y1[idx], y2[idx], fall[idx], near_high[idx]
        lo, hi, p80 = np.percentile(s, 100 / 3), np.percentile(s, 80), np.percentile(s, 80)
        low, top = s <= lo, s >= hi
        above = s > p80
        yrs = len(idx) / 252
        return {"M1": R.auroc_fast(s, a1), "M2": R.auroc_fast(s, a2),
                "M3": R.auroc_fast(s[nh], a1[nh]) if nh.sum() > 50 else np.nan,
                "M4": spearman(s, -f), "M5": float(a1[low].mean()), "M6": float(a1[top].mean()),
                "M7": float(np.abs(np.diff(above.astype(int))).sum() / yrs)}

    def block(mask, use):
        ok = mask & ~np.isnan(y1) & ~np.isnan(y2)
        for n in use:
            ok &= ~np.isnan(ind[n])
        return np.flatnonzero(ok)

    test = D.mask(R.TEST_FROM)
    out = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "warning": "Hindsight comparison. Not part of the ledger. Not a forecast.",
           "unavailable": notes}

    # ---- ranking sample: every available indicator present
    idx = block(test, names)
    M = {n: measures(ind[n], idx) for n in names}
    better_high = {"M1": 1, "M2": 1, "M3": 1, "M4": 1, "M5": -1, "M6": 1}
    pts = {n: {} for n in names}
    for m, sign in better_high.items():
        for n in names:
            v = M[n][m]
            others = [M[o][m] for o in names if o != n]
            pts[n][m] = 100 * sum(1 for o in others if np.isnan(o) or (not np.isnan(v) and sign * v >= sign * o)) / len(others)
    overall = {n: float(np.mean(list(pts[n].values()))) for n in names}
    rng = np.random.default_rng(SEED)
    n_ = len(idx)
    nb = -(-n_ // BLOCK)
    d1 = {n: [] for n in names if n != "afmx"}
    d3 = {n: [] for n in names if n != "afmx"}
    for _ in range(a.draws):
        st = rng.integers(0, n_ - BLOCK + 1, nb)
        take = idx[(st[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n_]]
        yy, nh = y1[take], near_high[take]
        b1 = R.auroc_fast(afmx[take], yy)
        b3 = R.auroc_fast(afmx[take][nh], yy[nh])
        for n in d1:
            d1[n].append(R.auroc_fast(ind[n][take], yy) - b1)
            d3[n].append(R.auroc_fast(ind[n][take][nh], yy[nh]) - b3)
    q = lambda v: [r3(np.nanpercentile(v, 5)), r3(np.nanpercentile(v, 95))]
    out["ranking_sample"] = {"from": days[idx[0]], "to": days[idx[-1]], "days": int(n_),
                             "base_rate_10pct_fall": r3(y1[idx].mean()), "days_near_high": int(near_high[idx].sum()),
                             "base_rate_near_high": r3(y1[idx][near_high[idx]].mean())}
    order = sorted(names, key=lambda n: -overall[n])
    out["scorecard"] = [{"indicator": n, "overall": round(overall[n], 1), "rank": k + 1,
                         "measures": {m: r3(v) for m, v in M[n].items()},
                         "points": {m: round(v, 1) for m, v in pts[n].items()},
                         "spearman_with_afmx": r3(spearman(ind[n][idx], afmx[idx])),
                         **({} if n == "afmx" else {"M1_minus_afmx_90": q(d1[n]), "M3_minus_afmx_90": q(d3[n])})}
                        for k, n in enumerate(order)]
    # ---- each indicator on its own overlap with AFMX, test and 1990-2006
    tr = D.mask(*R.TRAIN)
    own = {}
    for n in names:
        e = {}
        for label, mk in (("test", test), ("1990_2006", tr)):
            ix = block(mk, ["afmx", n])
            if len(ix) < 500:
                continue
            mm, ma_ = measures(ind[n], ix), measures(afmx, ix)
            e[label] = {"from": days[ix[0]], "days": int(len(ix)), "M1": r3(mm["M1"]), "M1_afmx_same_days": r3(ma_["M1"]),
                        "M3": r3(mm["M3"]), "M3_afmx_same_days": r3(ma_["M3"])}
        own[n] = e
    out["own_sample"] = own
    # ---- AFMX by episode: how early each indicator was in its top fifth before the falls
    p80 = {n: np.percentile(ind[n][idx], 80) for n in names}
    ep = {}
    for label, (w0, w1) in R.WINDOWS.items():
        i0, i1 = bisect.bisect_left(days, w0), bisect.bisect_right(days, w1)
        if i1 - i0 < 30:
            continue
        pk = i0 + int(np.argmax(P[i0:i1]))
        tr_ = pk + int(np.argmin(P[pk:i1]))
        e = {"peak": days[pk], "trough": days[tr_], "fall_pct": r3(100 * (P[tr_] / P[pk] - 1)), "first_day_in_top_fifth_after_peak_minus_60": {}}
        for n in names:
            lead = None
            for i in range(max(pk - 60, 0), tr_ + 1):
                if not np.isnan(ind[n][i]) and ind[n][i] >= p80[n]:
                    lead = i - pk
                    break
            e["first_day_in_top_fifth_after_peak_minus_60"][n] = lead
        ep[label] = e
    out["episodes_trading_days_from_peak"] = ep
    pathlib.Path(a.out).mkdir(parents=True, exist_ok=True)
    (pathlib.Path(a.out) / "results4.json").write_text(json.dumps(out, indent=1) + "\n")
    for row in out["scorecard"]:
        print(row["rank"], row["indicator"], row["overall"], row["measures"])


if __name__ == "__main__":
    main()
