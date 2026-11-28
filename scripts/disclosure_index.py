#!/usr/bin/env python3
"""Disclosure risk index: a hindsight study. Not part of the ledger; not a forecast.

Everything tested here, and the bar it has to clear, is fixed in research/disclosure/preregistration.json,
committed before this script read a single filing.

Source: SEC EDGAR (company list, filing lists, primary documents of 10-K and 10-Q). Only counts are stored.
SEC fair access: declared User-Agent, at most 6 requests per second in total.

  python scripts/disclosure_index.py probe            # print the shape of each endpoint, read nothing else
  python scripts/disclosure_index.py fetch            # build research/disclosure/filings.csv (resumes)
  python scripts/disclosure_index.py analyze          # tests -> research/disclosure/results.json
  python scripts/disclosure_index.py analyze --offline DIR   # smoke test: DIR/filings.csv and DIR/MKT.csv, no network
"""
import argparse, bisect, csv, datetime as dt, gzip, html, json, math, pathlib, random, re, sys, time
import urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "disclosure"
PLAN = json.loads((OUT / "preregistration.json").read_text())
UA = "AFMX risk-ledger research (github.com/ksjaj-hub/risk-ledger) 325890826+ksjaj-hub@users.noreply.github.com"
THEMES = list(PLAN["themes"])
PAT = {k: re.compile(v) for k, v in PLAN["themes"].items()}
GENERIC = re.compile(r"\brisks?\b|\buncertaint(?:y|ies)\b|\buncertain\b|\badverse(?:ly)?\b")
N_UNIVERSE, FROM, WORKERS, PER_WORKER_GAP = 150, "2006-01-01", 4, 0.70  # 4 workers x 1/0.70 = 5.7 requests a second
SEED = 20261128
FIELDS = ["cik", "ticker", "form", "filed", "acc", "doc", "words", "generic"] + THEMES
_last = [0.0]


def get(url, gap=PER_WORKER_GAP, tries=5):
    """One polite request. Returns bytes. Raises on 403 at once: that is the SEC saying stop."""
    for k in range(tries):
        wait = gap - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read()
                return gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                raise
            time.sleep(2 ** k * 2)
        except Exception:  # noqa: BLE001
            time.sleep(2 ** k * 2)
    raise RuntimeError(f"gave up: {url}")


def clean(raw):
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<ix:header>.*?</ix:header>", " ", t)
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]*>", " ", t)
    t = html.unescape(t).replace("\xa0", " ").replace("’", "'").replace("‐", "-").replace("‑", "-")
    return re.sub(r"\s+", " ", t).lower()


def doc_url(cik, acc, doc):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"


def count_one(job):
    cik, ticker, form, filed, acc, doc = job
    try:
        t = clean(get(doc_url(cik, acc, doc)))
    except urllib.error.HTTPError as e:
        return job, f"http {e.code}"
    except Exception as e:  # noqa: BLE001
        return job, str(e)[:60]
    row = {"cik": cik, "ticker": ticker, "form": form, "filed": filed, "acc": acc, "doc": doc,
           "words": t.count(" ") + 1, "generic": len(GENERIC.findall(t))}
    for k in THEMES:
        row[k] = len(PAT[k].findall(t))
    return job, row


# ------------------------------------------------------------------ probe
def probe():
    tick = json.loads(get("https://www.sec.gov/files/company_tickers.json"))
    first = [tick[str(i)] for i in range(12)]
    print("company_tickers entries:", len(tick), "| first 12:", [(x["ticker"], x["cik_str"]) for x in first])
    sub = json.loads(get("https://data.sec.gov/submissions/CIK0000320193.json"))
    rec = sub["filings"]["recent"]
    print("submissions keys:", sorted(sub)[:12], "| recent columns:", sorted(rec), "| rows:", len(rec["form"]))
    print("older files:", [(f["name"], f.get("filingFrom"), f.get("filingTo")) for f in sub["filings"]["files"]][:4])
    i = rec["form"].index("10-Q")
    raw = get(doc_url(320193, rec["accessionNumber"][i], rec["primaryDocument"][i]))
    print("one 10-Q:", rec["filingDate"][i], rec["primaryDocument"][i], "bytes", len(raw), "words", clean(raw).count(" "))
    for q in ('"government shutdown"', '"debt ceiling" OR "federal debt limit"'):
        url = ("https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode(
            {"q": q, "forms": "10-K,10-Q", "dateRange": "custom", "startdt": "2013-10-01", "enddt": "2013-12-31"}))
        try:
            fts = json.loads(get(url))
            hits = fts.get("hits", {})
            print("full-text search:", q, "| top keys", sorted(fts), "| total", hits.get("total"),
                  "| page", len(hits.get("hits", [])), "| aggregations", sorted(fts.get("aggregations", {})))
            if hits.get("hits"):
                print("  hit fields:", sorted(hits["hits"][0].get("_source", {})))
        except Exception as e:  # noqa: BLE001
            print("full-text search failed:", q, repr(e)[:200])


# ------------------------------------------------------------------ fetch
def filing_list(cik):
    """All 10-K and 10-Q filings of one company since FROM: [(form, filed, acc, doc)], and whether a 10-K exists."""
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))
    pages = [sub["filings"]["recent"]]
    for f in sub["filings"]["files"]:
        if f.get("filingTo", "9999") >= FROM:
            pages.append(json.loads(get("https://data.sec.gov/submissions/" + f["name"])))
    out, has_10k = {}, False
    for p in pages:
        for form, filed, acc, doc in zip(p["form"], p["filingDate"], p["accessionNumber"], p["primaryDocument"]):
            if form == "10-K":
                has_10k = True
            if form in ("10-K", "10-Q") and filed >= FROM:
                out[acc] = (form, filed, acc, doc)
    return sorted(out.values(), key=lambda x: x[1]), has_10k, sub.get("name")


def fetch():
    from concurrent.futures import ProcessPoolExecutor
    uni_path, csv_path = OUT / "universe.json", OUT / "filings.csv"
    if uni_path.exists():
        uni = json.loads(uni_path.read_text())
    else:
        tick = json.loads(get("https://www.sec.gov/files/company_tickers.json"))
        uni, seen, skipped = [], set(), []
        for i in range(len(tick)):
            e = tick[str(i)]
            if e["cik_str"] in seen:
                continue
            seen.add(e["cik_str"])
            fl, has_10k, name = filing_list(e["cik_str"])
            if not has_10k:
                skipped.append(e["ticker"])
                continue
            uni.append({"cik": e["cik_str"], "ticker": e["ticker"], "name": name, "rank_in_file": i,
                        "filings": fl})
            if len(uni) == N_UNIVERSE:
                break
        uni_path.write_text(json.dumps({"read_on": dt.date.today().isoformat(), "skipped_no_10k": skipped,
                                        "companies": uni}, separators=(",", ":")))
        uni = {"companies": uni, "skipped_no_10k": skipped}
        print("universe:", len(uni["companies"]), "skipped (no 10-K):", len(skipped))
    done = set()
    if csv_path.exists():
        done = {r["acc"] for r in csv.DictReader(open(csv_path))}
    jobs, no_doc = [], 0
    for c in uni["companies"]:
        for form, filed, acc, doc in c["filings"]:
            if not doc:
                no_doc += 1
            elif acc not in done:
                jobs.append((c["cik"], c["ticker"], form, filed, acc, doc))
    print("filings to read:", len(jobs), "already read:", len(done), "without a primary document:", no_doc)
    new = not csv_path.exists()
    fails, t0, budget = [], time.time(), 150 * 60
    with open(csv_path, "a", newline="") as fh, ProcessPoolExecutor(WORKERS) as ex:
        w = csv.DictWriter(fh, FIELDS)
        if new:
            w.writeheader()
        for n, (job, res) in enumerate(ex.map(count_one, jobs, chunksize=4)):
            if isinstance(res, dict):
                w.writerow(res)
            else:
                fails.append([job[4], res])
            if n % 500 == 0:
                fh.flush()
                print(n, "of", len(jobs), "failed", len(fails), f"{time.time() - t0:.0f}s", flush=True)
            if time.time() - t0 > budget:
                print("time budget reached; run again to continue")
                ex.shutdown(cancel_futures=True)
                break
    (OUT / "fetch_log.json").write_text(json.dumps({"failed": fails, "no_primary_document": no_doc}, indent=1))
    print("done. failed:", len(fails))


# ------------------------------------------------------------------ analyze
def day(s):
    return dt.date.fromisoformat(s)


def quarter(d):
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def pct(v, p):
    import numpy as np
    return float(np.percentile(v, p)) if len(v) else float("nan")


def analyze(offline=None):
    import numpy as np
    sys.path.insert(0, str(ROOT / "scripts"))
    src = pathlib.Path(offline) if offline else OUT
    rows = list(csv.DictReader(open(src / "filings.csv")))
    by = {}
    for r in rows:
        r["d"] = day(r["filed"])
        r["words"] = int(r["words"]); r["generic"] = int(r["generic"])
        for k in THEMES:
            r[k] = int(r[k])
        by.setdefault(r["cik"], []).append(r)
    r4 = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)
    # ---- flags per filing
    for cik, fs in by.items():
        fs.sort(key=lambda r: r["d"])
        for i, r in enumerate(fs):
            prior = [p for p in fs[:i] if 0 < (r["d"] - p["d"]).days <= 365]
            r["eligible"] = len(prior) >= 3
            r["new"] = {k: r["eligible"] and r[k] > 0 and not any(p[k] > 0 for p in prior) for k in THEMES}
            r["drop"] = {k: r["eligible"] and r[k] == 0 and any(p[k] > 0 for p in prior) for k in THEMES}
            r["dens"] = 1e4 * r["generic"] / max(r["words"], 1)
            same = [p for p in fs[:i] if p["form"] == r["form"] and 270 <= (r["d"] - p["d"]).days <= 460]
            r["up20"] = None
            if same and r["eligible"]:
                p = min(same, key=lambda p: abs((r["d"] - p["d"]).days - 365))
                if p["dens"] > 0:
                    r["up20"] = r["dens"] >= 1.2 * p["dens"]
    elig = [r for r in rows if r["eligible"] and r["filed"] >= "2007-01-01"]
    # ---- quarterly series
    qs = sorted({quarter(r["d"]) for r in elig})
    Q = {}
    for q in qs:
        inq = [r for r in elig if quarter(r["d"]) == q]
        cos = {r["cik"] for r in inq}
        Q[q] = {"n": len(cos)}
        for k in THEMES:
            Q[q][k] = len({r["cik"] for r in inq if r["new"][k]}) / len(cos)
            Q[q]["lvl_" + k] = len({r["cik"] for r in inq if r[k] > 0}) / len(cos)
            Q[q]["drop_" + k] = len({r["cik"] for r in inq if r["drop"][k]}) / len(cos)
    good = [q for q in qs if Q[q]["n"] >= 30]
    series = {k: [Q[q][k] for q in good] for k in THEMES}

    def overlap(a, b):
        out, d = [], day(a).replace(day=1)
        while d <= day(b):
            if quarter(d) in Q and quarter(d) in good and quarter(d) not in out:
                out.append(quarter(d))
            d = (d.replace(day=28) + dt.timedelta(days=5)).replace(day=1)
        return out

    v1, v2 = [], []
    for k, a, b in PLAN["tests"]["V1_known_events_rank"]["pairs"]:
        oq = overlap(a, b)
        s = series[k]
        if not oq:
            v1.append({"theme": k, "window": [a, b], "note": "no quarter with data", "pass": False})
            v2.append({"theme": k, "window": [a, b], "pass": False})
            continue
        best = max(oq, key=lambda q: Q[q][k])
        top, p90, med = Q[best][k], pct(s, 90), pct(s, 50)
        v1.append({"theme": k, "window": [a, b], "peak_quarter": best, "peak_share": r4(top), "p90": r4(p90),
                   "rank_from_top": 1 + sum(1 for x in s if x > top), "quarters": len(s), "pass": bool(top >= p90 and top > 0)})
        v2.append({"theme": k, "window": [a, b], "peak_share": r4(top), "median": r4(med),
                   "pass": bool(top >= 0.10 and top >= 3 * med)})
    noise = {k: {"median": r4(pct(series[k], 50)), "p90": r4(pct(series[k], 90)), "max": r4(max(series[k])),
                 "max_quarter": good[int(np.argmax(series[k]))],
                 "quarters_at_zero": r4(sum(1 for x in series[k] if x == 0) / len(series[k])),
                 "latest_level": r4(Q[good[-1]]["lvl_" + k])} for k in THEMES}
    # ---- daily series
    d0, d1 = dt.date(2007, 1, 1), max(r["d"] for r in rows) + dt.timedelta(days=1)
    cal = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
    es = sorted([r for r in rows if r["eligible"]], key=lambda r: r["d"])
    ed = [r["d"] for r in es]
    daily = {k: np.full(len(cal), np.nan) for k in THEMES + ["A1", "A2", "n"]}
    for i, t in enumerate(cal):
        lo, hi = bisect.bisect_left(ed, t - dt.timedelta(days=90)), bisect.bisect_left(ed, t)
        latest = {}
        for r in es[lo:hi]:
            latest[r["cik"]] = r
        n = len(latest)
        daily["n"][i] = n
        if n < 30:
            continue
        L = list(latest.values())
        for k in THEMES:
            daily[k][i] = sum(r["new"][k] for r in L) / n
        daily["A1"][i] = sum(any(r["new"].values()) for r in L) / n
        u = [r["up20"] for r in L if r["up20"] is not None]
        if len(u) >= 30:
            daily["A2"][i] = sum(u) / len(u)
    ci = {t.isoformat(): i for i, t in enumerate(cal)}
    # ---- L1 delay
    delay = []
    for k, a, b in PLAN["tests"]["V1_known_events_rank"]["pairs"]:
        s = daily[k]
        p90 = float(np.nanpercentile(s, 90))
        i0 = ci.get(a)
        hit = None
        if i0 is not None:
            for j in range(i0, min(len(cal), i0 + 400)):
                if not np.isnan(s[j]) and s[j] >= p90 and s[j] > 0:
                    hit = j - i0
                    break
        delay.append({"theme": k, "window_start": a, "days_to_p90": hit, "p90": r4(p90)})
    dl = [x["days_to_p90"] for x in delay if x["days_to_p90"] is not None]
    # ---- M1 market
    if offline:
        mkt = {d: float(v) for d, v in list(csv.reader(open(src / "MKT.csv")))[1:]}
    else:
        from sector_sensitivity import french
        fh, fac = french("F-F_Research_Data_Factors_daily")
        mkt = {d: v[fh.index("Mkt-RF")] + v[fh.index("RF")] for d, v in fac.items()}
    import research_v4 as R
    v3 = {r["date"]: float(r["v3_long_score"]) for r in csv.DictReader(open(ROOT / "research/v4/daily.csv"))}
    days = [d for d in sorted(mkt) if "2007-01-03" <= d and d in ci]
    P = np.exp(np.cumsum(np.log1p(np.array([mkt[d] for d in days]) / 100)))
    N = len(days)
    y = np.full(N, np.nan)
    for i in range(N - 63):
        y[i] = float(100 * (P[i + 1: i + 64].min() / P[i] - 1) <= -10)
    S = {"v3": np.array([v3.get(d, np.nan) for d in days]),
         "A1": np.array([daily["A1"][ci[d]] for d in days]), "A2": np.array([daily["A2"][ci[d]] for d in days])}

    def prank(x):
        out = np.full(len(x), np.nan)
        ok = ~np.isnan(x)
        out[ok] = np.argsort(np.argsort(x[ok], kind="stable"), kind="stable") / max(ok.sum() - 1, 1)
        u, inv = np.unique(x[ok], return_inverse=True)  # ties share their mean rank
        m = np.zeros(len(u)); c = np.zeros(len(u))
        np.add.at(m, inv, out[ok]); np.add.at(c, inv, 1)
        out[ok] = (m / c)[inv]
        return out
    for a in ("A1", "A2"):
        S["v3+" + a] = (prank(S["v3"]) + prank(S[a])) / 2
    ok = ~np.isnan(y)
    for v in S.values():
        ok &= ~np.isnan(v)
    au = {k: r4(R.auroc(v[ok], y[ok])) for k, v in S.items()}
    cis, diff, nb = R.boot(S, y, "v3", np.random.default_rng(SEED))
    m1 = {"days": int(ok.sum()), "from": days[int(np.flatnonzero(ok)[0])], "to": days[int(np.flatnonzero(ok)[-1])],
          "share_of_days_with_fall": r4(y[ok].mean()), "auroc": au, "range90": cis, "difference_to_v3_range90": diff}
    for a in ("A1", "A2"):
        c = "v3+" + a
        m1[a + "_pass"] = bool(au[a] >= 0.58 and cis[a][0] > 0.5 and au[c] - au["v3"] >= 0.02 and diff[c][0] > 0)
    from research_v4d import spearman
    r1 = {"A1_v3": r4(spearman(S["A1"][ok], S["v3"][ok])), "A2_v3": r4(spearman(S["A2"][ok], S["v3"][ok])),
          "A1_A2": r4(spearman(S["A1"][ok], S["A2"][ok]))}
    # ---- V3 reading sample
    rng = random.Random(SEED)
    pools = {k: [r for r in elig if r["new"][k]] for k in THEMES}
    for k in THEMES:
        pools[k].sort(key=lambda r: r["acc"]); rng.shuffle(pools[k])
    sample, depth = [], 0
    while len(sample) < 60 and any(len(pools[k]) > depth for k in THEMES):
        for k in THEMES:
            if len(sample) < 60 and len(pools[k]) > depth:
                sample.append((k, pools[k][depth]))
        depth += 1
    sp = OUT / "reading_sample.json"
    if not offline and not sp.exists():
        items = []
        for k, r in sample:
            try:
                t = clean(get(doc_url(r["cik"], r["acc"], r["doc"]), gap=0.25))
                m = PAT[k].search(t)
                snip = t[max(0, m.start() - 220): m.end() + 220] if m else None
            except Exception as e:  # noqa: BLE001
                snip = f"(could not be read again: {e})"
            items.append({"theme": k, "ticker": r["ticker"], "form": r["form"], "filed": r["filed"],
                          "url": doc_url(r["cik"], r["acc"], r["doc"]), "snippet": snip})
        sp.write_text(json.dumps(items, indent=1, ensure_ascii=False))
    v3r = None
    mp = OUT / "reading_marks.json"
    if mp.exists():
        marks = json.loads(mp.read_text())["marks"]
        per = {}
        for it, mk in zip(json.loads(sp.read_text()), marks):
            per.setdefault(it["theme"], []).append(bool(mk))
        tot = sum(sum(v) for v in per.values())
        v3r = {"read": len(marks), "about_the_risk": tot, "share": r4(tot / len(marks)),
               "per_theme": {k: [sum(v), len(v)] for k, v in per.items()},
               "themes_removed": [k for k, v in per.items() if len(v) >= 4 and sum(v) / len(v) < 0.7],
               "pass": bool(tot / len(marks) >= 0.85)}
    n1, n2 = sum(x["pass"] for x in v1), sum(x["pass"] for x in v2)
    res = {
        "computed": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "plan": "research/disclosure/preregistration.json",
        "data": {"companies": len(by), "filings": len(rows), "eligible_filings_2007_on": len(elig),
                 "first_filed": min(r["filed"] for r in rows), "last_filed": max(r["filed"] for r in rows),
                 "companies_with_filings_before_2008": sum(1 for fs in by.values() if fs[0]["filed"] < "2008-01-01"),
                 "eligible_companies_by_year": {str(yv): len({r["cik"] for r in elig if r["d"].year == yv})
                                                for yv in range(2007, d1.year + 1)}},
        "V1_known_events_rank": {"passed_pairs": n1, "needed": 14, "pass": n1 >= 14, "pairs": v1},
        "V2_visible_size": {"passed_pairs": n2, "needed": 12, "pass": n2 >= 12, "pairs": v2},
        "V3_reading_check": v3r or "not read yet",
        "M1_market_warning": m1,
        "L1_delay": {"median_days": r4(float(np.median(dl))) if dl else None, "min": min(dl) if dl else None,
                     "max": max(dl) if dl else None, "pairs": delay},
        "R1_overlap": r1,
        "B1_noise": noise,
        "latest": {"quarter": good[-1], "companies": Q[good[-1]]["n"],
                   "new_share": {k: r4(Q[good[-1]][k]) for k in THEMES},
                   "level_share": {k: r4(Q[good[-1]]["lvl_" + k]) for k in THEMES},
                   "dropped_share": {k: r4(Q[good[-1]]["drop_" + k]) for k in THEMES}},
    }
    dst = src if offline else OUT
    (dst / "results.json").write_text(json.dumps(res, indent=1))
    with open(dst / "quarterly.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["quarter", "companies"] + ["new_" + k for k in THEMES] + ["level_" + k for k in THEMES])
        for q in qs:
            w.writerow([q, Q[q]["n"]] + [round(Q[q][k], 4) for k in THEMES] + [round(Q[q]["lvl_" + k], 4) for k in THEMES])
    print(json.dumps({k: res[k] for k in ("data", "M1_market_warning", "R1_overlap")}, indent=1))
    print("V1", n1, "/17  V2", n2, "/17  L1 median days", res["L1_delay"]["median_days"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["probe", "fetch", "analyze"])
    ap.add_argument("--offline")
    a = ap.parse_args()
    {"probe": probe, "fetch": fetch, "analyze": lambda: analyze(a.offline)}[a.stage]()
