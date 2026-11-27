#!/usr/bin/env python3
"""Round 8: can the five-part rule run on US federal government inputs only? Equivalence test, not a search.

Plan fixed in research/v4/preregistration8.json before this produced any number on real data.
Hindsight; not part of the ledger; not a forecast. Needs numpy. Writes research/v4/results8.json.
  python scripts/research_v4f.py                # real data (FRED_API_KEY, network)
  python scripts/research_v4f.py --fixture DIR  # MKT.csv, FRED csvs and ofr_fsi.csv from DIR (tests)
"""
import argparse, copy, csv, io, json, pathlib, sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import research_v4 as R  # noqa: E402
import research_v4d as R4  # noqa: E402
from collect import ROOT, judge, level_for  # noqa: E402

r3 = R.r3
CAL = ("2000-01-03", "2006-12-29")
PAIRS = {"equity_volatility": ("Volatility", "vol"), "equity_drawdown": ("Equity valuation", "dd"),
         "financial_conditions": ("Funding", "nfci"), "credit_stress": ("Credit", None)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(R.OUT))
    a = ap.parse_args()
    rule = json.loads((ROOT / "rules" / "v3.json").read_text())
    D = R.Data(a.fixture)
    days, N = D.days, D.N
    text = (pathlib.Path(a.fixture) / "ofr_fsi.csv").read_text() if a.fixture else R4.get(R4.OFR_URL)
    head = [h.strip() for h in next(csv.reader(io.StringIO(text)))]
    ofr = {c: R.asof(R4.table(text, "Date", c), days, lag=2) for c in ("OFR FSI", "Volatility", "Credit", "Equity valuation", "Funding")}
    first = R4.table(text, "Date", "OFR FSI")[0][0]
    for c in ofr:
        ofr[c][np.array(days) < first] = np.nan
    cal = D.mask(*CAL) & ~np.isnan(ofr["OFR FSI"])
    test = D.mask(R.TEST_FROM)
    th = {c["id"]: c for c in rule["components"]}
    v3in = {"vol": D.vol, "dd": D.dd, "nfci": D.nfci}

    # level shares of the matching v3 inputs on calibration days
    shares = {}
    for cid, (_, key) in PAIRS.items():
        if key:
            x = v3in[key][cal & ~np.isnan(v3in[key])]
            lv = np.array([level_for(v, th[cid]["thresholds"], th[cid]["direction"]) for v in x])
            shares[cid] = [float((lv >= k).mean()) for k in (1, 2, 3)]
    shares["credit_stress"] = [float(np.mean([shares[c][k] for c in shares])) for k in range(3)]
    cuts = {}
    for cid, (col, _) in PAIRS.items():
        x = ofr[col][cal]
        cuts[cid] = [float(np.quantile(x, 1 - s)) if s > 0 else float(x.max()) + 1e-9 for s in shares[cid]]

    cand = copy.deepcopy(rule)
    for c in cand["components"]:
        if c["id"] in cuts:
            c["thresholds"], c["direction"] = [round(v, 3) for v in cuts[c["id"]]], "higher_is_riskier"
    cth = {c["id"]: c for c in cand["components"]}
    mins = [s["min_score"] for s in rule["states"]]
    src = {cid: ofr[col] for cid, (col, _) in PAIRS.items()} | {"yield_curve": D.t10y3m}
    sc5, ix5 = np.full(N, np.nan), np.full(N, -1)
    for i in range(N):
        if any(np.isnan(src[c][i]) for c in src):
            continue
        lv = {c: level_for(src[c][i], cth[c]["thresholds"], cth[c]["direction"]) for c in src}
        s, ix = judge(cand, lv)
        sc5[i], ix5[i] = max(s, mins[ix]), ix
    v3s, v3i = R.v3_scores(D, rule)
    okc = cal & (v3i >= 0)
    st_sh = [float((v3i[okc] >= k).mean()) for k in range(1, 5)]
    tot = ofr["OFR FSI"]
    tcuts = [float(np.quantile(tot[cal], 1 - s)) if s > 0 else float("inf") for s in st_sh]
    ixt = np.full(N, -1)
    g = ~np.isnan(tot)
    ixt[g] = np.sum(tot[g, None] >= np.array(tcuts)[None, :], axis=1)

    scores = {"v3_long": v3s, "open5": sc5, "ofr_total": tot}
    ind = {"v3_long": v3i, "open5": ix5, "ofr_total": ixt}
    both = test & ~np.isnan(sc5) & ~np.isnan(v3s) & ~np.isnan(tot)
    rng = np.random.default_rng(R.SEED)
    ev = R.evaluate(D, scores, ind, rule, both, rng=rng)
    full = D.mask(CAL[0])
    pub = {k: R.publish(ind[k], rule, full) for k in ind}
    agree = {}
    for k in ("open5", "ofr_total"):
        m = both & (pub[k] >= 0) & (pub["v3_long"] >= 0)
        d = np.abs(pub[k][m] - pub["v3_long"][m])
        agree[k] = {"days": int(m.sum()), "same_state": r3((d == 0).mean()), "same_or_neighbour": r3((d <= 1).mean()),
                    "higher_than_v3": r3((pub[k][m] > pub["v3_long"][m]).mean()), "lower_than_v3": r3((pub[k][m] < pub["v3_long"][m]).mean())}
    verdict = {}
    A = ev["auroc"]
    for k in ("open5", "ofr_total"):
        d = {o: (A[o]["auroc"][k] or 0) - (A[o]["auroc"]["v3_long"] or 0) for o in ("O1", "O2", "O3")}
        S, B = ev["states"][k], ev["states"]["v3_long"]
        checks = {"O1_within_0.01": d["O1"] >= -0.01, "O2_O3_within_0.02": d["O2"] >= -0.02 and d["O3"] >= -0.02,
                  "ladder_rises": bool(S["ladder_rises"]),
                  "changes_within_25pct": S["state_changes_per_year"] <= 1.25 * B["state_changes_per_year"],
                  "same_or_neighbour_90pct": agree[k]["same_or_neighbour"] >= 0.9}
        verdict[k] = {"difference_to_v3": {o: r3(v) for o, v in d.items()}, "checks": checks, "passes": all(checks.values())}
    corr = {}
    for cid, (col, key) in PAIRS.items():
        y = v3in[key] if key else D.baa
        m = both & ~np.isnan(y)
        corr[cid] = {"ofr_part": col, "against": key or "baa10y (stand-in)", "spearman": r3(R4.spearman(ofr[col][m], y[m]))}
    last = int(np.flatnonzero(~np.isnan(sc5))[-1])
    out = {"plan": "research/v4/preregistration8.json", "ofr_columns": head, "ofr_first": first,
           "calibration": {"from": CAL[0], "to": CAL[1], "days": int(cal.sum()), "v3_level_shares_at_or_above": {k: [r3(x) for x in v] for k, v in shares.items()},
                           "v3_state_shares_at_or_above": [r3(x) for x in st_sh]},
           "open5_thresholds": {k: [round(v, 3) for v in cuts[k]] for k in cuts}, "ofr_total_state_cuts": [r3(x) for x in tcuts],
           "test": ev, "agreement_with_v3_published_state": agree, "verdict": verdict, "correlation_with_v3_input": corr,
           "latest": {"date": days[last], "open5_score": r3(sc5[last]), "open5_state": rule["states"][int(pub["open5"][last])]["name"],
                      "v3_long_state": rule["states"][int(pub["v3_long"][last])]["name"] if pub["v3_long"][last] >= 0 else None},
           "warning": "Hindsight. The OFR index is re-estimated when its inputs are corrected; today's history is what is downloaded."}
    p = pathlib.Path(a.out) / "results8.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"thresholds": out["open5_thresholds"], "verdict": verdict, "agree": agree}, indent=1))


if __name__ == "__main__":
    main()
