#!/usr/bin/env python3
"""Watch share: what people on the AFMX waitlist (later: paying members) asked alerts for.

Design and limits: research/worry/design.ko.md. Publication gates: research/worry/gates.json.

The input is the operator's private export of the form answers. It holds email addresses, so it
must never be committed to this public repository; this script refuses to read a file that sits
inside the repository unless it is under private/ (git-ignored). The output holds no address and
no row about one person: only counts that pass the gates, and "hidden" where a count is too small.

  python scripts/worry_index.py /path/outside/repo/answers.csv            # internal summary
  python scripts/worry_index.py answers.csv --publish out.json            # only what the gates allow
  python scripts/worry_index.py --selftest

Standard library only.
"""
import argparse, csv, hashlib, json, math, os, re, sys
from collections import Counter
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATES = os.path.join(ROOT, "research", "worry", "gates.json")
SECTORS = ["technology", "communication", "consumer_discretionary", "consumer_staples", "energy", "financials",
           "health_care", "industrials", "materials", "real_estate", "utilities"]
EMAIL = re.compile(r"^[^\s@|]+@[^\s@|]+\.[^\s@|]{2,}$")
TICKER = re.compile(r"^[A-Z]{1,5}([.-][A-Z]{1,2})?$")
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y. %m. %d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


def person_key(email):
    """One person, one voice: lower case, drop +tags, drop dots for gmail. Returned as a hash."""
    local, _, domain = email.strip().lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return hashlib.sha256((local + "@" + domain).encode()).hexdigest()[:16], domain


def parse_time(s):
    pm, am = re.search(r"오후|PM", s or ""), re.search(r"오전|AM", s or "")
    s = re.sub(r"\s*(오전|오후|AM|PM)\s*", " ", s or "").strip()
    for f in TIME_FORMATS:
        try:
            t = datetime.strptime(s, f)
        except ValueError:
            continue
        if pm and t.hour < 12:
            t += timedelta(hours=12)
        if am and t.hour == 12:
            t -= timedelta(hours=12)
        return t
    return None


def parse_answer(text):
    """'email | waitlist | lang=ko | weekly=no | sectors=a,b | tickers=NVDA,JPM' or 'email | remove'.
    A bare email is a weekly-note signup and is not part of this count. Returns None for anything else."""
    parts = [p.strip() for p in (text or "").split("|")]
    if len(parts) < 2 or not EMAIL.match(parts[0]):
        return None
    if parts[1] == "remove":
        return {"email": parts[0], "kind": "remove"}
    if parts[1] != "waitlist":
        return None
    kv = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
    sectors = [s for s in kv.get("sectors", "").split(",") if s]
    tickers = [t for t in kv.get("tickers", "").upper().split(",") if t]
    if any(s not in SECTORS for s in sectors) or any(not TICKER.match(t) for t in tickers) or len(tickers) > 10:
        return {"email": parts[0], "kind": "malformed"}   # the page cannot produce this; a hand-made post can
    return {"email": parts[0], "kind": "waitlist", "lang": kv.get("lang", ""), "sectors": sorted(set(sectors)),
            "tickers": sorted(set(tickers))}


def read_rows(path):
    """CSV as exported from the answer sheet: time in the first column, the answer in the last."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.reader(f):
            if len(r) >= 2:
                rows.append((parse_time(r[0]), r[-1]))
    return rows


def clean(rows, gates, confirmed=None, known_tickers=None):
    """Latest answer per person wins; a later 'remove' deletes the person. Returns (people, dropped counts)."""
    dropped, people = Counter(), {}
    for i, (t, text) in enumerate(rows):
        a = parse_answer(text)
        if a is None:
            dropped["not_a_waitlist_row"] += 1
            continue
        key, domain = person_key(a["email"])
        if a["kind"] == "remove":
            if people.pop(key, None):
                dropped["removed_on_request"] += 1
            continue
        if a["kind"] == "malformed":
            dropped["malformed"] += 1
            continue
        if confirmed is not None and key not in confirmed:
            dropped["address_not_confirmed"] += 1
            continue
        if domain in gates["disposable_domains"]:
            dropped["disposable_domain"] += 1
            continue
        if known_tickers is not None:
            a["tickers"] = [x for x in a["tickers"] if x in known_tickers]
        if key in people:
            dropped["earlier_answer_replaced"] += 1
        people[key] = {"t": t, "i": i, "domain": domain, "lang": a["lang"], "sectors": a["sectors"], "tickers": a["tickers"]}

    # Burst: many people with the very same picks inside a short window read as one script, kept as one voice.
    win, cap = timedelta(minutes=gates["burst_window_minutes"]), gates["burst_same_picks"]
    groups = {}
    for k, p in people.items():
        if p["t"] and (p["sectors"] or p["tickers"]):
            groups.setdefault((tuple(p["sectors"]), tuple(p["tickers"])), []).append((p["t"], k))
    for g in groups.values():
        g.sort()
        start = 0
        for end in range(len(g)):
            while g[end][0] - g[start][0] > win:
                start += 1
            if end - start + 1 >= cap:
                for _, k in g[start + 1:end + 1]:
                    if people.pop(k, None):
                        dropped["burst_same_picks"] += 1
    # One mail domain that is not a large public provider may not carry more than a set share of the voices.
    by_domain = Counter(p["domain"] for p in people.values())
    limit = max(gates["domain_cap_min"], int(gates["domain_cap_share"] * len(people)))
    for d, c in by_domain.items():
        if d in gates["public_mail_domains"] or c <= limit:
            continue
        extra = sorted((p["i"], k) for k, p in people.items() if p["domain"] == d)[limit:]
        for _, k in extra:
            del people[k]
            dropped["domain_cap"] += 1
    return people, dict(dropped)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def spearman(a, b):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r, i = [0.0] * len(v), 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


def summarize(people):
    n = len(people)
    picked = [p for p in people.values() if p["sectors"] or p["tickers"]]
    sec = Counter(s for p in picked for s in p["sectors"])       # one person counts once per sector
    tic = Counter(t for p in picked for t in p["tickers"])       # and once per ticker
    return {"people": n, "people_with_picks": len(picked), "sectors": {s: sec.get(s, 0) for s in SECTORS},
            "tickers": dict(tic.most_common()), "languages": dict(Counter(p["lang"] for p in people.values()))}


def publishable(summary, gates, previous=None, baseline=None, today=None):
    """Apply the gates. Returns a dict that is safe to print in public, or one that says why nothing is."""
    g, m = gates["stage_1"], summary["people_with_picks"]
    out = {"name": "AFMX watch share", "what_it_is": gates["what_it_is"], "people_counted": None, "published": False, "reasons": []}
    if m < g["min_people"]:
        out["reasons"].append("fewer than %d people with picks" % g["min_people"])
    if previous is not None and m - previous.get("people_counted_exact_private", 0) < g["min_new_people_between_snapshots"]:
        out["reasons"].append("fewer than %d new people since the last snapshot" % g["min_new_people_between_snapshots"])
    if previous is not None and previous.get("date") and (today or datetime.now(timezone.utc).date().isoformat()) < (
            datetime.fromisoformat(previous["date"]) + timedelta(days=g["min_days_between_snapshots"])).date().isoformat():
        out["reasons"].append("fewer than %d days since the last snapshot" % g["min_days_between_snapshots"])
    if out["reasons"]:
        return out
    step = g["round_to_points_below_fine"] if m < g["fine_rounding_from_people"] else 1
    rnd = lambda x: int(round(100 * x / step) * step)
    out.update(published=True, people_counted="%d+" % (m // g["people_count_step"] * g["people_count_step"]), rounded_to_points=step)
    out["sectors"] = {}
    for s, k in summary["sectors"].items():
        if k < g["min_people_per_cell"]:
            out["sectors"][s] = "hidden"
        else:
            lo, hi = wilson(k, m)
            out["sectors"][s] = {"share": rnd(k / m), "range": [rnd(lo), rnd(hi)]}
    top = [(t, k) for t, k in summary["tickers"].items() if k >= g["min_people_per_ticker"]][:g["max_tickers_listed"]]
    out["tickers"] = [{"ticker": t, "share": rnd(k / m)} for t, k in top]
    if baseline:
        keys = [s for s in SECTORS if s in baseline]
        rho = spearman([summary["sectors"][s] for s in keys], [baseline[s] for s in keys])
        out["rank_correlation_with_baseline"] = round(rho, 2)
        out["says_more_than_baseline"] = rho < gates["stage_2"]["max_rank_correlation_with_baseline"]
    return out


def margin_table():
    """Half-width of a 95% range for a share near 30%, by number of people. Used in the design note."""
    return {n: round(100 * 1.96 * math.sqrt(0.3 * 0.7 / n), 1) for n in (30, 50, 100, 200, 400, 1000, 3000)}


def selftest():
    gates = json.load(open(GATES))
    assert person_key("A.b+x@Gmail.com")[0] == person_key("ab@googlemail.com")[0]
    assert parse_answer("a@b.co") is None and parse_answer("a@b.co | remove")["kind"] == "remove"
    assert parse_answer("a@b.co | waitlist | sectors=moon | tickers=")["kind"] == "malformed"
    assert parse_answer("a@b.co | waitlist | lang=ko | weekly=no | sectors=energy | tickers=XOM,BRK.B")["tickers"] == ["BRK.B", "XOM"]
    t0 = datetime(2027, 1, 1)
    rows = []
    for i in range(140):   # 140 honest people, spread over time
        secs = ["technology"] if i % 2 == 0 else ["energy", "financials"]
        if i < 4:
            secs.append("utilities")
        rows.append((t0 + timedelta(hours=i), "p%d@gmail.com | waitlist | lang=en | weekly=no | sectors=%s | tickers=%s"
                     % (i, ",".join(secs), "NVDA" if i % 4 == 0 else "")))
    rows.append((t0 + timedelta(hours=200), "p0@gmail.com | waitlist | lang=ko | weekly=no | sectors=energy | tickers="))  # changed mind
    rows.append((t0 + timedelta(hours=201), "p1@gmail.com | remove"))
    for i in range(50):    # a script: 50 addresses, same picks, one minute
        rows.append((t0 + timedelta(hours=300, seconds=i), "bot%d@gmail.com | waitlist | lang=en | weekly=no | sectors=materials | tickers=PUMP" % i))
    for i in range(40):    # one company domain, spread out
        rows.append((t0 + timedelta(hours=400 + i), "u%d@onefirm.example | waitlist | lang=en | weekly=no | sectors=real_estate | tickers=" % i))
    rows.append((t0, "x@mailinator.com | waitlist | lang=en | weekly=no | sectors=energy | tickers="))
    rows.append((t0, "weekly-only@gmail.com"))
    people, dropped = clean(rows, gates)
    s = summarize(people)
    assert dropped["burst_same_picks"] == 49 and dropped["removed_on_request"] == 1 and dropped["disposable_domain"] == 1, dropped
    assert dropped["domain_cap"] > 0 and s["sectors"]["materials"] == 1, (dropped, s)
    pub = publishable(s, gates)
    assert pub["published"] and pub["sectors"]["utilities"] == "hidden" and pub["sectors"]["materials"] == "hidden", pub
    assert all(x["ticker"] != "PUMP" for x in pub["tickers"]) and "@" not in json.dumps(pub)
    assert not publishable(summarize(dict(list(people.items())[:60])), gates)["published"]
    assert not publishable(s, gates, previous={"people_counted_exact_private": s["people_with_picks"] - 3})["published"]
    old = {"people_counted_exact_private": 10, "date": "2027-01-01"}
    assert not publishable(s, gates, previous=old, today="2027-01-20")["published"] and publishable(s, gates, previous=old, today="2027-01-29")["published"]
    assert parse_time("2027. 1. 5 오후 3:04:05") == datetime(2027, 1, 5, 15, 4, 5) and parse_time("1/5/2027 12:00:01") is not None
    assert abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-9 and abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-9
    lo, hi = wilson(30, 100)
    assert 0.21 < lo < 0.23 and 0.39 < hi < 0.40
    print("worry_index selftest ok; 95%% margin near a 30%% share by people counted: %s" % margin_table())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("answers", nargs="?", help="private CSV export of the form answers (outside the repository, or under private/)")
    ap.add_argument("--confirmed", help="text file, one confirmed address per line; when given, only these count")
    ap.add_argument("--tickers", help="JSON list of known US tickers; picks outside it are ignored")
    ap.add_argument("--baseline", help="JSON {sector: weight} to compare ranks against (stage 2 test)")
    ap.add_argument("--previous", help="private JSON from the last run with --private-state")
    ap.add_argument("--private-state", help="where to write exact counts for the next run (keep it private)")
    ap.add_argument("--publish", help="write the public JSON here; contains only what the gates allow")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.answers:
        ap.error("give the answers file, or --selftest")
    real = os.path.realpath(a.answers)
    if real.startswith(ROOT + os.sep) and not real.startswith(os.path.join(ROOT, "private") + os.sep):
        sys.exit("Refusing: the answers file holds addresses and sits inside the public repository. Keep it outside, or under private/.")
    gates = json.load(open(GATES))
    confirmed = {person_key(l)[0] for l in open(a.confirmed) if "@" in l} if a.confirmed else None
    known = set(json.load(open(a.tickers))) if a.tickers else None
    people, dropped = clean(read_rows(real), gates, confirmed, known)
    s = summarize(people)
    pub = publishable(s, gates, json.load(open(a.previous)) if a.previous else None, json.load(open(a.baseline)) if a.baseline else None)
    print("INTERNAL, do not paste in public (exact small counts can point at one person):")
    print(json.dumps({"summary": s, "dropped": dropped}, ensure_ascii=False, indent=1))
    print("\nWhat the gates allow in public:")
    print(json.dumps(pub, ensure_ascii=False, indent=1))
    if a.private_state:
        json.dump({"people_counted_exact_private": s["people_with_picks"], "date": datetime.now(timezone.utc).date().isoformat()}, open(a.private_state, "w"))
    if a.publish:
        if confirmed is None and gates["stage_1"]["needs_confirmed_addresses"]:
            sys.exit("Not written: stage 1 counts confirmed addresses only. Pass --confirmed.")
        json.dump(pub, open(a.publish, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
