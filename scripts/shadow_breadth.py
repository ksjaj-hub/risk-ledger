#!/usr/bin/env python3
"""Shadow record of market breadth. Outside the rule and outside the ledger chain.

Why it exists: research/v4/README.md, rounds 5 to 7. Breadth looked useful in hindsight, but it was picked
after seeing the data. This writes its value down before the following months are known, so that it can be
judged later on days nobody had seen. It changes no state, score, record or alert.

Appends to shadow/breadth.csv, never rewrites a line:
  sector_funds   daily, from the 11 Select Sector SPDR funds' NAV history files (issuer)
  industries_49  when the Kenneth R. French Data Library publishes new days (weeks late)

  python scripts/shadow_breadth.py
  python scripts/shadow_breadth.py --fixture DIR
"""
import argparse, csv, datetime as dt, pathlib, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT  # noqa: E402

OUT = ROOT / "shadow" / "breadth.csv"
HEAD = ["recorded_at_utc", "as_of", "measure", "breadth", "level", "dispersion_63d", "members"]
CUTS = [0.245, 0.49, 0.857]  # round 5b: 50th, 75th, 95th percentile of the 49-industry measure, 1990-2006
BACKFILL_DAYS = 0            # a new measure starts at its latest day; nothing earlier is written as if it were live


def measure(series, day_index):
    """series: {name: [(day, level)] ascending}. Breadth and dispersion on each member's day_index-th latest day."""
    below, disp, n = 0, [], 0
    for obs in series.values():
        if len(obs) < 200 + day_index:
            continue
        v = [x for _, x in obs]
        end = len(v) - day_index
        w = v[end - 200: end]
        n += 1
        below += w[-1] < sum(w) / 200
        if end >= 64:
            disp.append(v[end - 1] / v[end - 64] - 1)
    if n == 0:
        return None
    return below / n, (statistics.pstdev(disp) if len(disp) > 1 else None), n


def rows_for(name, series, known, min_members):
    """New rows for days later than the last one recorded for this measure, oldest first."""
    days = sorted({d for obs in series.values() for d, _ in obs})
    last = max((r["as_of"] for r in known if r["measure"] == name), default=None)
    new = [d for d in days if last is None or d > last]
    if last is None:
        new = new[-(BACKFILL_DAYS + 1):]
    out = []
    for d in new:
        cut = {k: [o for o in obs if o[0] <= d] for k, obs in series.items()}
        cut = {k: o for k, o in cut.items() if o and o[-1][0] == d}  # only members that have this day
        m = measure(cut, 0)
        if not m or m[2] < min_members:
            continue
        b, dp, n = m
        out.append({"as_of": d, "measure": name, "breadth": f"{b:.4f}", "level": str(sum(b >= c for c in CUTS)),
                    "dispersion_63d": "" if dp is None else f"{dp:.4f}", "members": str(n)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    known = list(csv.DictReader(open(out))) if out.exists() else []
    new, problems = [], []
    try:
        from research_v4e import SPDR, spdr_nav
        funds = {}
        for tk in SPDR:
            try:
                funds[tk] = spdr_nav(tk, a.fixture)
            except Exception as e:  # noqa: BLE001
                problems.append(f"{tk}: {type(e).__name__}")
        new += rows_for("sector_funds", funds, known, 9)
    except Exception as e:  # noqa: BLE001
        problems.append(f"sector funds: {type(e).__name__}: {e}")
    try:
        if a.fixture:
            rows = list(csv.reader(open(pathlib.Path(a.fixture) / "IND.csv")))
            head, ind = rows[0][1:], {r[0]: [float(x) for x in r[1:]] for r in rows[1:]}
        else:
            from sector_sensitivity import french
            head, ind = french("49_Industry_Portfolios_daily")
        series = {h: [] for h in head}
        level = {h: 1.0 for h in head}
        for d in sorted(ind):
            for h, r in zip(head, ind[d]):
                if r <= -99:
                    series[h], level[h] = [], 1.0  # a gap restarts the member's history
                    continue
                level[h] *= 1 + r / 100
                series[h].append((d, level[h]))
        new += rows_for("industries_49", series, known, 20)
    except Exception as e:  # noqa: BLE001
        problems.append(f"industries: {type(e).__name__}: {e}")
    for p in problems:
        print("unavailable:", p)
    if not new:
        print("nothing new")
        return
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    out.parent.mkdir(parents=True, exist_ok=True)
    fresh = not out.exists()
    with open(out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEAD)
        if fresh:
            w.writeheader()
        for r in new:
            w.writerow({"recorded_at_utc": now, **r})
            print(r)


if __name__ == "__main__":
    main()
