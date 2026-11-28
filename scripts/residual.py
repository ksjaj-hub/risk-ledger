#!/usr/bin/env python3
"""AFMX residual risk index, version 1 (residual/preregistration.json). Standard library only.

Writes residual/index.json. `--selftest` checks the arithmetic on made-up cards.
"""
import glob, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SECTORS = 11
CLOSED = ("resolved", "withdrawn")


def status_on(card, day):
    s = None
    for h in card.get("history", []):
        if h["date"] <= day:
            s = h["status"]
    return s


def forecast_on(card, day):
    fs = [f for f in card.get("forecasts", []) if f["written_on"] <= day]
    return max(fs, key=lambda f: (f["written_on"], f["n"])) if fs else None


def stage(card, day):
    """(stage, p_resolved, p_worsened), or None when the card is not in the sum that day."""
    if card["first_recorded"] > day:
        return None
    s = status_on(card, day) or card["status"]
    if s in CLOSED:
        return None
    if s == "worsened":
        return 2.0, None, None
    f = forecast_on(card, day)
    if not f:
        return 1.0, None, None
    return min(2.0, max(0.0, 1 - f["p_resolved"] + f["p_worsened"])), f["p_resolved"], f["p_worsened"]


def reach(sector_entry):
    if sector_entry and sector_entry.get("market_wide"):
        return 1.0
    return max(1, len((sector_entry or {}).get("direct", []))) / SECTORS


def compute(cards, sectors, day):
    rows = []
    for c in cards:
        st = stage(c, day)
        if st is None:
            continue
        r = reach(sectors.get(c["id"]))
        rows.append({"card": c["id"], "reach": round(r, 4), "stage": round(st[0], 4), "part": r * st[0],
                     "tilt": 0.0 if st[1] is None else r * (st[2] - st[1])})
    total = sum(x["part"] for x in rows)
    out = {"date": day, "index": round(total, 2), "open_cards": len(rows),
           "equal_reach": round(sum(x["stage"] for x in rows), 2), "tilt": round(sum(x["tilt"] for x in rows), 2)}
    for x in rows:
        x["share"] = round(x["part"] / total, 3) if total else 0.0
        x["part"] = round(x["part"], 3)
        del x["tilt"]
    rows.sort(key=lambda x: -x["part"])
    return out, rows


def change_days(cards, today):
    days = {today}
    for c in cards:
        days.add(c["first_recorded"])
        days.update(f["written_on"] for f in c.get("forecasts", []))
        prev = None
        for h in c.get("history", []):
            if h["status"] != prev:
                days.add(h["date"])
            prev = h["status"]
    return sorted(d for d in days if d <= today)


def selftest():
    mk = lambda i, hist, fc=(), first="2026-01-01": {"id": i, "first_recorded": first, "status": hist[-1][1],
                                                     "history": [{"date": d, "status": s} for d, s in hist],
                                                     "forecasts": [{"n": n + 1, "written_on": w, "p_resolved": a, "p_worsened": b}
                                                                   for n, (w, a, b) in enumerate(fc)]}
    cards = [mk("wide", [("2026-01-01", "open")], [("2026-01-02", 0.1, 0.3)]),
             mk("one", [("2026-01-01", "open"), ("2026-01-03", "worsened")]),
             mk("gone", [("2026-01-01", "open"), ("2026-01-03", "resolved")]),
             mk("late", [("2026-01-04", "open")], first="2026-01-04")]
    sec = {"wide": {"market_wide": True, "direct": []}, "one": {"market_wide": False, "direct": ["a"]},
           "gone": {"market_wide": False, "direct": ["a", "b"]}}
    d1, _ = compute(cards, sec, "2026-01-01")
    assert d1["index"] == round(1 + 1 / 11 + 2 / 11, 2) and d1["open_cards"] == 3, d1
    d2, _ = compute(cards, sec, "2026-01-02")
    assert d2["index"] == round(1.2 + 3 / 11, 2) and d2["tilt"] == 0.2, d2
    d3, rows = compute(cards, sec, "2026-01-03")
    assert d3["index"] == round(1.2 + 2 / 11, 2) and d3["open_cards"] == 2 and rows[0]["card"] == "wide", d3
    d4, _ = compute(cards, sec, "2026-01-04")
    assert d4["open_cards"] == 3 and d4["equal_reach"] == 4.2, d4
    assert change_days(cards, "2026-01-05") == ["2026-01-0%d" % i for i in range(1, 6)]
    assert abs(sum(r["share"] for r in rows) - 1) < 0.01
    print("residual selftest ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    import datetime as dt
    cards = [json.loads(pathlib.Path(f).read_text()) for f in sorted(glob.glob(str(ROOT / "events" / "*.json")))]
    sectors = json.loads((ROOT / "aids" / "reading.json").read_text())["sectors"]
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    days = change_days(cards, today)
    hist = [compute(cards, sectors, d)[0] for d in days]
    # today only gets its own line when something changed that day
    if len(hist) > 1 and {k: v for k, v in hist[-1].items() if k != "date"} == {k: v for k, v in hist[-2].items() if k != "date"}:
        hist.pop()
    now, rows = compute(cards, sectors, hist[-1]["date"])
    out = {"note": "AFMX residual risk index, version 1. A sum of AFMX's own judgment on its open cards, not a measurement of the "
                   "market and not a forecast. Formula, limits and the market test (not run) are in residual/preregistration.json.",
           "version": 1, "unit": "market-wide open risks", "latest": now, "max_if_all_worsened": round(2 * sum(r["reach"] for r in rows), 2),
           "cards": rows, "history": hist}
    p = ROOT / "residual" / "index.json"
    text = json.dumps(out, indent=1) + "\n"
    if "--check" in sys.argv:  # the committed file must match the cards, apart from a new line for today
        old = json.loads(p.read_text())
        same = old["history"] == hist[:len(old["history"])] and (old["latest"] == now or len(hist) > len(old["history"]))
        print("residual index matches the cards" if same else "residual/index.json is stale: run scripts/residual.py")
        sys.exit(0 if same else 1)
    if not p.exists() or p.read_text() != text:
        p.write_text(text)
    print(json.dumps(now), len(hist), "days")


if __name__ == "__main__":
    main()
