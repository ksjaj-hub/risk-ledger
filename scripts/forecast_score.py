#!/usr/bin/env python3
"""Score the forecasts on event cards (forecasts/README.md). Standard library only. Writes forecasts/scorecard.json.

A forecast's `outcome` is filled in by hand when a question is settled:
  {"resolved": 0 or 1, "worsened": 0 or 1, "settled_on": "YYYY-MM-DD"}   (a key may be missing while still open)
"""
import datetime as dt, glob, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    today = dt.date.today().isoformat()
    rows, problems = [], []
    for f in sorted(glob.glob(str(ROOT / "events" / "*.json"))):
        c = json.loads(pathlib.Path(f).read_text())
        seen = set()
        for fc in c.get("forecasts", []):
            first = fc["deadline"] not in seen
            seen.add(fc["deadline"])
            out = fc.get("outcome") or {}
            for q in ("resolved", "worsened"):
                p, o = fc[f"p_{q}"], out.get(q)
                if not 0 <= p <= 1:
                    problems.append(f"{c['id']} forecast {fc['n']}: p_{q} out of range")
                if o is None and fc["deadline"] < today:
                    problems.append(f"{c['id']} forecast {fc['n']}: deadline {fc['deadline']} has passed, '{q}' not settled")
                rows.append({"card": c["id"], "n": fc["n"], "question": q, "written_on": fc["written_on"], "deadline": fc["deadline"],
                             "p": p, "outcome": o, "first_for_deadline": first,
                             "brier": None if o is None else round((p - o) ** 2, 4)})
    done = [r for r in rows if r["outcome"] is not None and r["first_for_deadline"]]
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    nxt = min((r["deadline"] for r in rows if r["outcome"] is None), default=None)
    card = {"note": "Brier score, lower is better. Headline uses forecast 1 of each deadline only. Fewer than about 30 settled questions say very little.",
            "questions": len(rows), "settled": len(done), "next_deadline": nxt,
            "brier": mean([r["brier"] for r in done]),
            "yardstick_always_50pct": 0.25 if done else None,
            "yardstick_nothing_happens": mean([float(r["outcome"]) for r in done]),
            "problems": problems, "rows": rows}
    (ROOT / "forecasts" / "scorecard.json").write_text(json.dumps(card, indent=1) + "\n")
    print(f"{len(rows)} questions, {len(done)} settled, Brier {card['brier']}, next deadline {nxt}; {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
