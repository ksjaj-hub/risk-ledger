#!/usr/bin/env python3
"""Public grading of the sector score.

snapshot: once per calendar month, save the sector scores shown on the page (never overwritten).
grade:    for every snapshot whose following calendar month is fully covered by the French data, compare the
          sectors' returns in excess of the market in that following month with the scores in the snapshot.
The score describes exposure to open risks. Grading asks a harder question than the score claims to answer,
on purpose: did high-score sectors actually do worse afterwards? Misses are published as they are.
"""
import json, math, statistics, sys, pathlib, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT / "sector_scores" / "snapshots"


def snapshot():
    aids = json.loads((ROOT / "docs" / "data.json").read_text())["aids"]
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    path = SNAP / f"{today[:7]}.json"
    if path.exists():
        print("snapshot for this month already exists"); return
    SNAP.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": today, "score_version": aids["score_version"], "mapping_version": aids["mapping_version"],
                                "scores": {k: v["score"] for k, v in aids["sector_scores"].items()}}, indent=1) + "\n")
    print("wrote", path.name)


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def grade():
    sys.path.insert(0, str(ROOT / "scripts"))
    from sector_sensitivity import french, SECTORS
    ih, ind = french("49_Industry_Portfolios_daily"); fh, fac = french("F-F_Research_Data_Factors_daily")
    mkt = {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}
    last = max(d for d in ind if d in mkt)
    months = []
    for p in sorted(SNAP.glob("*.json")):
        s = json.loads(p.read_text()); y, m = int(p.stem[:4]), int(p.stem[5:])
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        nxt = f"{ny:04d}-{nm:02d}"
        after = f"{ny + (nm == 12):04d}-{(nm % 12) + 1:02d}"
        days = sorted(d for d in ind if d[:7] == nxt and d in mkt)
        if not days or last[:7] < after:
            months.append({"snapshot": p.stem, "graded_month": nxt, "status": "waiting for data"}); continue
        cm = math.prod(1 + mkt[d] / 100 for d in days); ex = {}
        for sid, names in SECTORS.items():
            idx = [ih.index(n) for n in names]
            ex[sid] = round(100 * (math.prod(1 + statistics.fmean(ind[d][i] for i in idx) / 100 for d in days) - cm), 2)
        ids = sorted(s["scores"]); sc = [s["scores"][i] for i in ids]; rx = [ex[i] for i in ids]
        ra, rb = ranks(sc), ranks(rx); ma = statistics.fmean(ra)
        den = math.sqrt(sum((a - ma) ** 2 for a in ra) * sum((b - ma) ** 2 for b in rb))
        rho = sum((a - ma) * (b - ma) for a, b in zip(ra, rb)) / den if den else 0.0
        by = sorted(ids, key=lambda i: -s["scores"][i]); hi, lo = by[:3], by[-3:]
        gap = statistics.fmean(ex[i] for i in hi) - statistics.fmean(ex[i] for i in lo)
        months.append({"snapshot": p.stem, "graded_month": nxt, "status": "graded", "score_version": s["score_version"],
                       "excess_return_pct": ex, "highest_three": hi, "lowest_three": lo,
                       "high_minus_low_pct": round(gap, 2), "rank_correlation": round(rho, 2),
                       "as_expected": gap < 0})
    g = [m for m in months if m["status"] == "graded"]
    out = {"note": "as_expected is true when the three highest-score sectors did worse than the three lowest in the following month. "
                   "One month says very little; read the running count.",
           "graded_months": len(g), "as_expected_months": sum(m["as_expected"] for m in g), "months": months}
    (ROOT / "sector_scores" / "scorecard.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out)[:600])


if __name__ == "__main__":
    {"snapshot": snapshot, "grade": grade}[sys.argv[1]]()
