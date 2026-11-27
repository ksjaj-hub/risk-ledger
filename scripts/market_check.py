#!/usr/bin/env python3
"""Set each open event card against market prices: do prices show the risk the card describes?

Reading aid, not part of the ledger, not a forecast and not a recommendation. The readings and rules are
fixed in market/config.json before the first run. Only series published by US government bodies are fetched
here (Energy Information Administration, Federal Reserve Board, Treasury yields); for third-party series the
check reuses the step already published in the latest AFMX record and fetches nothing new.
Standard library only. Needs FRED_API_KEY. Writes market/check.json, and only when a reading has changed:
generated_at_utc is the time the values on file were read, so a scheduled run that finds nothing new writes nothing.
"""
import bisect, datetime as dt, json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from collect import ROOT, fetch_series  # noqa: E402


def main():
    cfg = json.loads((ROOT / "market" / "config.json").read_text())
    N, TOP = cfg["window_observations"], cfg["top_share"]
    start = (dt.date.today() - dt.timedelta(days=int(N * 1.6))).isoformat()
    rec_path = sorted((ROOT / "records" / "us").glob("*/*.json"))[-1]
    rec = json.loads(rec_path.read_text())
    cache, out = {}, {}

    def get(sid):
        if sid not in cache:
            cache[sid] = fetch_series(sid, start)
        return cache[sid]

    for cid, c in cfg["cards"].items():
        if "none" in c:
            out[cid] = {"verdict": "not_checked", "none": c["none"], "readings": []}
            continue
        rs = []
        for r in c["readings"]:
            e = {k: r[k] for k in ("id", "rule", "en", "ko", "unit", "owner") if k in r}
            try:
                if "ledger" in r:
                    comp = rec["components"][r["ledger"]]
                    e |= {"steps": comp["level"], "as_of": comp["observation_date"], "shows": comp["level"] >= 2,
                          "record": rec_path.relative_to(ROOT).as_posix()}
                    if "value" in comp:
                        e["value"] = comp["value"]
                else:
                    a = get(r["series"][0])
                    if len(r["series"]) == 2:  # difference of two series on the first one's dates
                        b = get(r["series"][1]); bd, bv = [d for d, _ in b], [v for _, v in b]
                        a = [(d, round(v - bv[bisect.bisect_right(bd, d) - 1], 4)) for d, v in a if bisect.bisect_right(bd, d) > 0]
                    win = [v for _, v in a[-N:]]
                    d, v = a[-1]
                    rank = round(100 * sum(x <= v for x in win) / len(win))
                    e |= {"value": round(v, 2), "as_of": d, "percentile_5y": rank, "observations": len(win),
                          "series": r["series"]}
                    e["shows"] = v > 0 if r["rule"] == "above_zero" else rank >= round(100 * (1 - TOP))
            except Exception as ex:  # one missing series must not stop the others
                e |= {"error": str(ex)[:120]}
            rs.append(e)
        ok = [x for x in rs if "shows" in x]
        out[cid] = {"readings": rs, "verdict": "not_checked" if not ok else "shows" if any(x["shows"] for x in ok) else "does_not_show"}
        print(cid, out[cid]["verdict"], [(x["id"], x.get("value"), x.get("percentile_5y"), x.get("steps"), x.get("shows"), x.get("error")) for x in rs])
    path = ROOT / "market" / "check.json"
    if path.exists() and json.loads(path.read_text()).get("cards") == json.loads(json.dumps(out)):
        print("no reading changed; file left as it is")
        return 0
    res = {"meta": {"generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "config_version": cfg["version"], "rules": cfg["rules"],
                    "warning": "A reading aid. Whether a price is high says nothing about what it will do next. Not a forecast and not a recommendation.",
                    "sources": "FRED, Federal Reserve Bank of St. Louis. This product uses the FRED API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."},
           "cards": out}
    path.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
