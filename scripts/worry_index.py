#!/usr/bin/env python3
"""Worry index: what the people on the alerts waitlist asked to be warned about. Not live until enough people join.

Plan and limits: research/worry/README.md. The input is the form's answer sheet, exported by the operator as CSV and
kept OUT of the repository (it holds email addresses). The output holds totals only.

  python scripts/worry_index.py ANSWERS.csv        # writes research/worry/index.json, or says why it will not
  python scripts/worry_index.py --selftest
"""
import csv, datetime as dt, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIN_PEOPLE, MIN_PER_ITEM = 50, 10  # MIN_PER_ITEM is the promise in docs/privacy.html; MIN_PEOPLE is ours


def people(cells):
    """cells in the order they were sent. Returns {email: {"sectors": set, "tickers": set}} after removals."""
    out = {}
    for cell in cells:
        parts = [p.strip() for p in cell.split("|")]
        email = parts[0].lower()
        if "@" not in email:
            continue
        if len(parts) > 1 and parts[1] == "remove":
            out.pop(email, None)
        elif len(parts) > 1 and parts[1] == "waitlist":
            kv = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
            pick = lambda k, f: {f(x.strip()) for x in kv.get(k, "").split(",") if x.strip()}
            out[email] = {"sectors": pick("sectors", str.lower), "tickers": pick("tickers", str.upper)}
    return out


def index(ppl, today):
    n = len(ppl)
    if n < MIN_PEOPLE:
        return {"published": False, "reason": f"{n} people on the list; nothing is published below {MIN_PEOPLE}", "as_of": today}

    def table(key):
        c = {}
        for p in ppl.values():
            for x in p[key]:
                c[x] = c.get(x, 0) + 1
        keep = {k: v for k, v in c.items() if v >= MIN_PER_ITEM}
        return [{"item": k, "share": round(v / n, 3)} for k, v in sorted(keep.items(), key=lambda kv: (-kv[1], kv[0]))], len(c) - len(keep)
    sec, sh = table("sectors")
    tic, th = table("tickers")
    return {"published": True, "as_of": today, "people": n, "sectors": sec, "tickers": tic,
            "withheld_items_under_10_people": sh + th,
            "note": "Shares of people on the AFMX alerts waitlist who picked each item. A self-selected group, not a sample of investors."}


def selftest():
    cells = [f"u{i}@x.com | waitlist | lang=ko | weekly=no | sectors=energy{',banks' if i < 12 else ''} | tickers={'NVDA' if i < 9 else ''}" for i in range(60)]
    cells += ["u0@x.com | remove", "u1@x.com | waitlist | lang=en | weekly=no | sectors=banks | tickers=", "plain@x.com"]
    p = people(cells)
    assert len(p) == 59 and p["u1@x.com"]["sectors"] == {"banks"}
    r = index(p, "2026-01-01")
    assert r["people"] == 59 and r["sectors"] == [{"item": "energy", "share": round(58 / 59, 3)}, {"item": "banks", "share": round(11 / 59, 3)}], r
    assert r["tickers"] == [] and r["withheld_items_under_10_people"] == 1 and "x.com" not in json.dumps(r)
    assert index(people(cells[:20]), "2026-01-01")["published"] is False
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        rows = list(csv.reader(open(sys.argv[1], newline="", encoding="utf-8-sig")))[1:]
        res = index(people([r[-1] for r in rows if r]), dt.date.today().isoformat())
        (ROOT / "research" / "worry" / "index.json").write_text(json.dumps(res, indent=1) + "\n")
        print(res.get("reason") or f'{res["people"]} people, {len(res["sectors"])} sectors, {len(res["tickers"])} tickers')
