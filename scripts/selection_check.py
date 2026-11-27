#!/usr/bin/env python3
"""Card selection criteria: check every event card against selection/criteria.json. Standard library only.

  python scripts/selection_check.py           checks, then writes docs/selection.html
  python scripts/selection_check.py --check   checks only; exits 1 if the audit and the card files disagree

What a script can count, it counts (a primary source, both kinds of condition, a deadline, a listed ticker).
What needs a reader (does the title run ahead of the confirmed facts?) is written by hand in the audit, and this
script only makes sure that every card has an audit line and that the audit is not kinder than the count.
"""
import collections, glob, html, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from forecast_math import PAGE  # the same page shell as docs/odds.html

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORDER = {"met": 0, "partly": 1, "not_met": 2}
WORD = {"met": ("Meets", "충족"), "partly": ("Partly", "일부"), "not_met": ("Does not meet", "미달")}


def counted(card, tickers):
    """The part of each criterion a script can decide. True = nothing against it, False = fails."""
    rc, nc = card.get("resolution_conditions", {}), card.get("numeric_criteria", {}).get("items", [])
    res, wor = rc.get("resolved_when_all", []), rc.get("worsened_when_any", [])
    sides = collections.Counter(i["side"] for i in nc)
    written = rc.get("written_on", "")
    return {
        "S1": any(f.get("tier") == "primary" for f in card.get("sourced_facts", [])),
        "S3": bool(card.get("how_it_reaches_markets")) and bool(tickers.get(card["id"])),
        "S4": bool(res) and bool(wor) and sides["resolved"] >= len(res) and sides["worsened"] >= len(wor),
        "S5": bool(written) and any(f.get("deadline", "") > written for f in card.get("forecasts", [])),
    }


def check():
    crit = json.loads((ROOT / "selection" / "criteria.json").read_text())
    cards = {c["id"]: c for c in (json.loads(pathlib.Path(f).read_text()) for f in sorted(glob.glob(str(ROOT / "events" / "*.json"))))}
    aids = json.loads((ROOT / "aids" / "reading.json").read_text())
    ids = [c["id"] for c in crit["open_when_all"]]
    audit, problems, rows = crit["audit"]["cards"], [], []
    for cid in sorted(set(cards) | set(audit)):
        if cid not in audit:
            problems.append(f"{cid}: no audit line in selection/criteria.json"); continue
        if cid not in cards:
            problems.append(f"{cid}: audited but there is no such card"); continue
        a, c = audit[cid], cards[cid]
        if sorted(a["results"]) != sorted(ids) or any(v not in ORDER for v in a["results"].values()):
            problems.append(f"{cid}: results must give met, partly or not_met for each of {ids}")
            continue
        for k, ok in counted(c, aids.get("exposure", {})).items():
            if not ok and a["results"][k] == "met":
                problems.append(f"{cid}: {k} fails the count but the audit says met")
        blocked = [i for i in c.get("numeric_criteria", {}).get("items", []) if i.get("state") == "not_measurable_yet"]
        if blocked and a["results"]["S4"] == "met" and not a.get("not_measurable"):
            problems.append(f"{cid}: a condition cannot be counted yet; S4 needs 'partly', 'not_met' or a not_measurable note")
        worst = max(a["results"].values(), key=ORDER.get)
        if worst != "met" and not a.get("gap"):
            problems.append(f"{cid}: below the criteria but no gap is written")
        if worst == "not_met" and c["status"] != "withdrawn" and not (a.get("kept") and a.get("mark")):
            problems.append(f"{cid}: does not meet the criteria and is still shown; 'kept' and 'mark' must say why")
        rows.append({"id": cid, "title": c["title"], "status": c["status"], "verdict": worst, **a})
    watch = collections.Counter(t for cid in cards for t in aids.get("exposure", {}).get(cid, []))
    stats = {"cards": len(cards), "by_verdict": {v: sum(r["verdict"] == v for r in rows) for v in ORDER},
             "us_cards": sum("US" in c.get("markets", []) for c in cards.values()),
             "most_shared_ticker": watch.most_common(1)[0] if watch else None,
             "closed": {s: sum(c["status"] == s for c in cards.values()) for s in ("resolved", "worsened", "withdrawn")},
             "featured_below": [r["id"] for r in rows if r["verdict"] == "not_met" and r["id"] in aids.get("featured", [])]}
    return crit, rows, stats, problems


def page(crit, rows, stats):
    e = html.escape
    two = lambda en, ko, tag="p", cls="": f'<{tag}{" class=" + chr(34) + cls + chr(34) if cls else ""}><span lang="en">{e(en)}</span><span lang="ko">{e(ko)}</span></{tag}>'
    t2 = lambda d, tag="p", cls="": two(d["en"], d["ko"], tag, cls)
    ko = json.loads((ROOT / "i18n" / "events.ko.json").read_text())
    title_ko = lambda r: ko.get(r["id"], {}).get("title", r["title"])
    v, n = stats["by_verdict"], stats["cards"]
    b = [two("Why these cards", "왜 이 카드들인가", "h1"),
         two("What gets a risk onto an AFMX card, what closes a card, and how the cards we already have measure up. Several cards fall short, and the page says which and why. Beta: these criteria are version 1.",
             "어떤 리스크가 AFMX 카드가 되는지, 카드는 언제 닫히는지, 지금 있는 카드는 이 기준에 얼마나 맞는지 적습니다. 기준에 못 미치는 카드도 여럿 있고, 어느 카드가 왜 그런지 그대로 적었습니다. 지금은 베타이고 이 기준은 1판입니다.", cls="lead"),
         two(f'Of {n} cards: {v["met"]} meet every criterion, {v["partly"]} meet them partly, {v["not_met"]} does not.',
             f'카드 {n}장 가운데 {v["met"]}장은 모든 기준을 충족하고, {v["partly"]}장은 일부만 충족하며, {v["not_met"]}장은 미달입니다.', cls="big"),
         two("1. What opens a card", "1. 카드를 여는 기준", "h2"),
         two("A risk gets a card only when all six hold.", "여섯 가지를 모두 채워야 카드를 엽니다.")]
    for c in crit["open_when_all"]:
        b.append(two(f'{c["id"][1:]}. {c["name"]["en"]}', f'{c["id"][1:]}. {c["name"]["ko"]}', "h3"))
        b.append(t2(c["rule"]))
    b.append(two("2. What closes a card", "2. 카드를 닫는 기준", "h2"))
    for c in crit["closed_when"]:
        b.append(two(c["name"]["en"], c["name"]["ko"], "h3"))
        b.append(t2(c["rule"]))
    b.append(t2(crit["never"]))
    cl = stats["closed"]
    b.append(two(f'So far: {cl["resolved"]} resolved, {cl["worsened"]} worsened, {cl["withdrawn"]} withdrawn. Until a card closes, the closing rules are untested.',
                 f'지금까지 해소 {cl["resolved"]}장, 악화 {cl["worsened"]}장, 철회 {cl["withdrawn"]}장입니다. 카드가 실제로 닫히기 전까지 닫는 기준은 검증되지 않은 것입니다.', cls="su"))
    b.append(two("3. The home screen", "3. 홈 화면", "h2"))
    b.append(t2(crit["home_screen"]))
    b.append(two("4. The cards against the criteria", "4. 지금 카드를 기준에 맞춰 본 결과", "h2"))
    b.append(two(f'Checked on {crit["audit"]["checked_on"]}, using only what is on each card. "Partly" means the card stands on confirmed facts, but its title or one of its conditions runs ahead of them.',
                 f'{crit["audit"]["checked_on"]}에 카드에 적힌 내용만으로 점검했습니다. "일부"는 카드가 확인된 사실 위에 서 있지만 제목이나 조건 하나가 그보다 앞서 나갔다는 뜻입니다.'))
    for r in sorted(rows, key=lambda r: (-ORDER[r["verdict"]], r["id"])):
        w = WORD[r["verdict"]]
        short = [k[1:] for k in sorted(r["results"]) if r["results"][k] != "met"]
        b.append(f'<div class="card" id="{e(r["id"])}"><h3><a href="./#ev-{e(r["id"])}"><span lang="en">{e(r["title"])}</span><span lang="ko">{e(title_ko(r))}</span></a></h3>')
        if short:
            b.append(two(f'{w[0]}. Short on criterion {", ".join(short)}.', f'{w[1]}. {", ".join(short)}번 기준에 못 미칩니다.', cls="big2 v-" + r["verdict"]))
        else:
            b.append(two(f"{w[0]} all six.", "여섯 가지 모두 충족.", cls="big2"))
        for key, en, kr in (("gap", "What falls short: ", "못 미치는 점: "), ("fix", "What would fix it: ", "고치려면: "), ("kept", "Why it is still shown: ", "그래도 보여 드리는 이유: "), ("not_measurable", "Note: ", "참고: ")):
            if r.get(key):
                b.append(two(en + r[key]["en"], kr + r[key]["ko"], cls="q" if key != "gap" else ""))
        b.append("</div>")
    b.append(two("5. What this does not settle", "5. 이 기준으로도 풀리지 않는 것", "h2"))
    lim = list(crit["limits"])
    tk = stats["most_shared_ticker"]
    lim.insert(3, {"en": f'{stats["us_cards"]} of {n} cards are about the US market, and {tk[1]} of {n} watch the same share ({tk[0]}). The set leans one way.',
                   "ko": f'카드 {n}장 가운데 {stats["us_cards"]}장이 미국 시장에 관한 것이고, {tk[1]}장이 같은 종목({tk[0]})을 지켜봅니다. 한쪽으로 쏠려 있습니다.'})
    b.append("<ul>" + "".join(t2(x, "li") for x in lim) + "</ul>")
    b.append(two("6. Looked at and left out", "6. 살펴보고 넣지 않은 사건", "h2"))
    items = crit["left_out"]["items"]
    if items:
        b.append("<ul>" + "".join(two(f'{i["date"]}: {i["event"]["en"]} (failed {i["failed"]})', f'{i["date"]}: {i["event"]["ko"]} ({i["failed"][1:]}번 기준 미달)', "li") for i in items) + "</ul>")
    else:
        b.append(two("Nothing listed yet. The list starts on 2026-11-27; each weekday check adds the events it looked at and left out, with the criterion they failed.",
                     "아직 없습니다. 목록은 2026년 11월 27일부터 남깁니다. 평일 점검 때마다 살펴보고 넣지 않은 사건을, 못 미친 기준과 함께 한 줄씩 더합니다."))
    b.append(f'<p class="su">{two("Beta. Criteria version " + str(crit["version"]) + ", written " + crit["written_on"] + ".", "베타. 기준 " + str(crit["version"]) + "판, " + crit["written_on"] + " 작성.", "span")} <a href="https://github.com/ksjaj-hub/risk-ledger/blob/main/selection/criteria.json" rel="noopener">{two("The file behind this page", "이 페이지의 원본 파일", "span")}</a></p>')
    out = PAGE.replace("__BODY__", "\n".join(b))
    out = out.replace("<title>AFMX: the arithmetic behind the odds</title>", "<title>AFMX: why these cards</title>")
    out = out.replace('content="How the odds on AFMX event cards are scored, and what past events of the same kind say."', 'content="What gets a risk onto an AFMX card, what closes one, and which current cards fall short."')
    assert "why these cards" in out and "fall short" in out, "page shell changed; update the replacements"
    return out.replace("</style>", ".v-partly{color:#e3b341}.v-not_met{color:#ff8a7a}.card h3 a{color:var(--fg)}\n</style>")


if __name__ == "__main__":
    crit, rows, stats, problems = check()
    for p in problems:
        print("PROBLEM " + p)
    if problems:
        sys.exit(1)
    v = stats["by_verdict"]
    print(f'{stats["cards"]} cards: {v["met"]} meet, {v["partly"]} partly, {v["not_met"]} do not; shown on home below criteria: {stats["featured_below"]}')
    if "--check" not in sys.argv:
        (ROOT / "docs" / "selection.html").write_text(page(crit, rows, stats))
        print("wrote docs/selection.html")
