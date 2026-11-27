#!/usr/bin/env python3
"""The arithmetic behind the odds on event cards (forecasts/README.md, 'The arithmetic'). Standard library only.

  python scripts/forecast_math.py              writes forecasts/math.json and docs/odds.html
  python scripts/forecast_math.py --selftest   checks the formulas on small known cases
  python scripts/forecast_math.py --guard REF  fails if a forecast that exists at git REF was changed or removed

Part A scores the forecasts: Brier score against fixed yardsticks, and how many settled questions it takes before a
difference means anything. Part B is a second opinion from history: how long past events of the same kind lasted,
read with survival methods so that events still running count as 'not ended yet' instead of being dropped.
Nothing here changes a forecast. It reads forecasts/scorecard.json, so run forecast_score.py first.
"""
import datetime as dt, glob, html, json, math, pathlib, random, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIN_SETTLED = 30      # below this, no calibration table and no claim of skill
MIN_CARDS = 10        # below this, no interval on the score difference
D = dt.date.fromisoformat


# ---------- Part A: scoring ----------
def brier(rows):
    return sum((r["p"] - r["outcome"]) ** 2 for r in rows) / len(rows)


def murphy(rows, edges=(0.1, 0.3, 0.7, 0.9)):
    """Calibration table and Murphy's split: Brier = reliability - resolution + uncertainty (exact when each bin is scored at its mean)."""
    n, base = len(rows), sum(r["outcome"] for r in rows) / len(rows)
    bins = {}
    for r in rows:
        bins.setdefault(sum(r["p"] >= e for e in edges), []).append(r)
    table, rel, res = [], 0.0, 0.0
    for k in sorted(bins):
        b = bins[k]
        said, came = sum(r["p"] for r in b) / len(b), sum(r["outcome"] for r in b) / len(b)
        rel += len(b) * (said - came) ** 2 / n
        res += len(b) * (came - base) ** 2 / n
        table.append({"from": ([0] + list(edges))[k], "to": (list(edges) + [1])[k], "questions": len(b), "said": round(said, 3), "came_true": round(came, 3)})
    return {"table": table, "reliability": round(rel, 4), "resolution": round(res, 4), "uncertainty": round(base * (1 - base), 4)}


def card_bootstrap(rows, draws=4000, seed=7):
    """90% range of (AFMX Brier - 'nothing happens' Brier), resampling whole cards because a card's two questions move together."""
    by = {}
    for r in rows:
        by.setdefault(r["card"], []).append((r["p"] - r["outcome"]) ** 2 - r["outcome"] ** 2)
    cards, rng, out = list(by.values()), random.Random(seed), []
    for _ in range(draws):
        s = [x for c in (rng.choice(cards) for _ in cards) for x in c]
        out.append(sum(s) / len(s))
    out.sort()
    return [round(out[int(draws * 0.05)], 4), round(out[int(draws * 0.95)], 4)]


def expectation(open_cards, draws=100000, seed=7):
    """If every probability were exactly right, what would this round look like against 'nothing happens'?
    Per card the outcomes are taken as: resolved, worsened, or neither (the two are close to exclusive)."""
    per = []
    for pr, pw in open_cards:
        outs = [(pr, (pr - 1) ** 2 - 1 + pw ** 2), (pw, pr ** 2 + (pw - 1) ** 2 - 1), (1 - pr - pw, pr ** 2 + pw ** 2)]
        m = sum(p * d for p, d in outs)
        per.append((m, sum(p * (d - m) ** 2 for p, d in outs), outs))
    q = 2 * len(per)
    mean, sd = sum(m for m, _, _ in per) / q, math.sqrt(sum(v for _, v, _ in per)) / q
    rng, worse = random.Random(seed), 0
    for _ in range(draws):
        tot = 0.0
        for _, _, outs in per:
            u, acc = rng.random(), 0.0
            for p, d in outs:
                acc += p
                if u < acc:
                    tot += d
                    break
        worse += tot >= 0
    return {"questions": q, "expected_brier": round(sum(pr * (1 - pr) + pw * (1 - pw) for pr, pw in open_cards) / q, 4),
            "expected_nothing_happens": round(sum(pr + pw for pr, pw in open_cards) / q, 4),
            "expected_edge": round(-mean, 4), "edge_sd": round(sd, 4),
            "edge_share_of_top_4_cards": round(sum(sorted((-m for m, _, _ in per), reverse=True)[:4]) / -sum(m for m, _, _ in per), 2),
            "chance_no_better_than_nothing_happens": round(worse / draws, 3),
            "rounds_for_95pct": math.ceil((1.645 * sd / mean) ** 2) if mean else None}


def what_if(pr, pw):
    """Brier of the two questions on one card under each outcome, next to 'nothing happens'."""
    rows = []
    for name, r, w in (("resolved", 1, 0), ("neither", 0, 0), ("worsened", 0, 1)):
        rows.append({"outcome": name, "afmx": round(((pr - r) ** 2 + (pw - w) ** 2) / 2, 4), "nothing_happens": (r + w) / 2})
    return rows


# ---------- Part B: survival ----------
def kaplan_meier(obs):
    """obs: (days, ended). Returns [(day, share still running after that day)]. Events still running are censored, not dropped."""
    s, curve = 1.0, []
    for t in sorted({d for d, e in obs if e}):
        at_risk = sum(d >= t for d, _ in obs)
        s *= 1 - sum(d == t and e for d, e in obs) / at_risk
        curve.append((t, round(s, 4)))
    return curve


def km_at(curve, t):
    s = 1.0
    for day, v in curve:
        if day <= t:
            s = v
    return s


def erlang_cdf(x, n, total):
    z = total * x
    return 1 - math.exp(-z) * sum(z ** k / math.factorial(k) for k in range(n))


def erlang_q(q, n, total):
    lo, hi = 0.0, 1.0
    while erlang_cdf(hi, n, total) < q:
        hi *= 2
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if erlang_cdf(mid, n, total) < q else (lo, mid)
    return hi


def constant_rate(n, total_days, window):
    """Constant daily chance of ending, with the usual vague prior: rate ~ Gamma(n, total_days).
    Returns the chance of ending within `window` days and a 90% range. With few cases the range is the message."""
    mean = 1 - (total_days / (total_days + window)) ** n
    return round(mean, 3), [round(1 - math.exp(-erlang_q(q, n, total_days) * window), 3) for q in (0.05, 0.95)]


def wilson(k, n, z=1.645):
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def history(cards, asof):
    ref = json.loads((ROOT / "forecasts" / "reference_classes.json").read_text())
    out = []
    for cid, link in ref["cards"].items():
        card, cl = cards[cid], ref["classes"][link["class"]]
        if card["status"] != "open" or not card.get("forecasts"):
            continue
        fc = card["forecasts"][-1]
        row = {"card": cid, "title": card["title"], "class": link["class"], "class_en": cl["en"], "class_ko": cl["ko"], "cases": len(cl["episodes"]),
               "sources": [cl[k] for k in ("source", "source2") if k in cl], "unchecked": bool(cl.get("unchecked")), "use": link["use"],
               "question_en": link["en"], "question_ko": link["ko"], "fit_en": link["fit_en"], "fit_ko": link["fit_ko"],
               "deadline": fc["deadline"], "judgment": {"p_resolved": fc["p_resolved"], "p_worsened": fc["p_worsened"]}}
        if link["use"] == "exceed":
            th = link["threshold_days"]
            row["threshold_days"] = th
            row["cuts"] = []
            for name, eps in (("all", cl["episodes"]), ("shutdown", [e for e in cl["episodes"] if e["shutdown"]]), ("since_1990", [e for e in cl["episodes"] if e["start"] >= "1990"])):
                k = sum(e["days"] > th for e in eps)
                row["cuts"].append({"cut": name, "over": k, "of": len(eps), "share": round(k / len(eps), 3), "range90": wilson(k, len(eps))})
            row["lengths"] = sorted(e["days"] for e in cl["episodes"])
        else:
            lens = [(D(e["end"]) - D(e["start"])).days for e in cl["episodes"]]
            row["lengths"] = sorted(lens)
            if cl.get("open"):
                start = D(cl["open"]["start"])
                run, dead = (asof - start).days, (D(fc["deadline"]) - start).days
                obs = [(x, True) for x in lens] + [(run, False)]
                curve = kaplan_meier(obs)
                still = [x for x in lens if x > run]
                mean, rng = constant_rate(len(lens), sum(lens) + run, dead - run)
                row.update({"started": cl["open"]["start"], "running_days": run, "deadline_day": dead,
                            "past_cases_that_ran_this_long": len(still), "of_those_ended_by_deadline_day": sum(x <= dead for x in still),
                            "km_ends_by_deadline": round(1 - km_at(curve, dead) / km_at(curve, run), 3) if km_at(curve, run) else None,
                            "constant_rate_ends_by_deadline": mean, "range90": rng})
        out.append(row)
    return out


def own_cards(cards, asof):
    """Survival on AFMX's own cards. Open cards are censored at today. Empty until cards close; that is the point of printing it."""
    obs = []
    for c in cards.values():
        closed = next((h["date"] for h in c.get("history", []) if h.get("status") == "resolved"), None)
        obs.append(((D(closed or asof.isoformat()) - D(c["first_recorded"])).days, bool(closed)))
    ended, exposure = sum(e for _, e in obs), sum(d for d, _ in obs)
    return {"cards": len(obs), "resolved": ended, "card_days": exposure,
            "curve": kaplan_meier(obs) if ended >= MIN_CARDS else None,
            "note": f"A curve is drawn from {MIN_CARDS} resolved cards on."}


# ---------- page ----------
def page(m):
    e, pc = html.escape, lambda x: f"{round(x * 100)}%"
    two = lambda en, ko, tag="p", cls="": f'<{tag}{" class=" + chr(34) + cls + chr(34) if cls else ""}><span lang="en">{en}</span><span lang="ko">{ko}</span></{tag}>'
    s, x, nd = m["scoring"], m["scoring"]["if_exactly_right"], m["scoring"]["next_deadline"]
    b = []
    b.append(two("The arithmetic behind the odds", "확률 뒤의 계산", "h1"))
    b.append(two("The odds on AFMX cards are our own judgment. This page checks that judgment with arithmetic: how it will be scored, and what past events of the same kind say. It is thin so far, and the page says where.",
                 "AFMX 카드의 확률은 저희 판단입니다. 이 페이지는 그 판단을 계산으로 점검합니다. 어떻게 채점하는지, 같은 종류의 과거 사건은 무엇을 말하는지 적습니다. 아직은 근거가 얇고, 어디가 얇은지도 함께 적습니다.", cls="lead"))
    b.append(two("1. The score", "1. 채점", "h2"))
    if s["settled"]:
        b.append(two(f'Settled questions: {s["settled"]}. AFMX {s["brier"]}, always 50%: 0.25, always "nothing happens": {s["nothing_happens"]}. Lower is better.',
                     f'결과가 나온 질문 {s["settled"]}개. AFMX {s["brier"]}, 항상 50%라고 말하면 0.25, 항상 "아무 일도 없다"고 말하면 {s["nothing_happens"]}. 낮을수록 좋습니다.', cls="big"))
        if s["settled"] < MIN_SETTLED:
            b.append(two(f"With fewer than {MIN_SETTLED} settled questions this difference can be luck. We make no claim of skill yet.", f"결과가 나온 질문이 {MIN_SETTLED}개보다 적으면 이 차이는 운일 수 있습니다. 아직 실력이라고 말하지 않습니다."))
    else:
        b.append(two("Settled questions: 0. There is no score yet.", "결과가 나온 질문 0개. 아직 점수가 없습니다.", cls="big"))
    b.append(two(f'Each card asks two questions: resolved by the deadline, worsened by the deadline. The score is the Brier score, the squared gap between the probability and what happened. We compare it with two fixed yardsticks: always saying 50%, and always saying "nothing will happen". The second is the hard one, because most risks stay open.',
                 f'카드마다 질문이 둘입니다. 기한까지 해소되는가, 기한까지 악화되는가. 점수는 브라이어 점수로, 말한 확률과 실제 결과의 차이를 제곱한 값입니다. 기준 두 가지와 비교합니다. 항상 50%라고 말하기, 그리고 항상 "아무 일도 없다"고 말하기. 어려운 쪽은 뒤의 것입니다. 리스크는 대부분 그대로 남기 때문입니다.'))
    b.append(two("How much can this round prove?", "이번 묶음으로 얼마나 증명할 수 있나", "h3"))
    top = round(x["edge_share_of_top_4_cards"] * 100)
    b.append(two(f'We can work this out before any result is in. Suppose every probability on the {x["questions"] // 2} open cards were exactly right. We would expect {x["expected_brier"]} against {x["expected_nothing_happens"]} for "nothing happens", and we would still fail to beat that yardstick in about {round(x["chance_no_better_than_nothing_happens"] * 100)} of 100 such rounds by chance alone. So this round is a real test: if we do not beat "nothing happens", that counts against us and we will say so. A win counts for less than it looks, because {top}% of the expected margin comes from four cards where we gave high odds.',
                 f'결과가 나오기 전에도 계산할 수 있습니다. 열린 카드 {x["questions"] // 2}장의 확률이 모두 정확하다고 가정하면 저희 점수는 {x["expected_brier"]}, "아무 일도 없다"는 {x["expected_nothing_happens"]}로 기대됩니다. 그래도 이런 묶음 100번 가운데 약 {round(x["chance_no_better_than_nothing_happens"] * 100)}번은 운만으로 그 기준을 이기지 못합니다. 그러니 이번 묶음은 실제 시험입니다. "아무 일도 없다"를 이기지 못하면 저희에게 불리한 증거이고, 그대로 적겠습니다. 이기더라도 보이는 것만큼의 증거는 아닙니다. 기대되는 차이의 {top}%가 높은 확률을 적은 카드 네 장에서 나오기 때문입니다.'))
    b.append(two("Cards are also not independent: several depend on the same oil price and the same central banks. The calculation above treats them as independent, so the real amount of evidence is smaller than it suggests.",
                 "카드끼리 독립도 아닙니다. 여러 장이 같은 유가와 같은 중앙은행에 달려 있습니다. 위 계산은 카드가 서로 독립이라고 보았으므로 실제 증거는 그보다 적습니다."))
    if nd:
        lab = {"resolved": ("Resolved", "해소"), "neither": ("Neither", "둘 다 아님"), "worsened": ("Worsened", "악화")}
        b.append(two(f'First settlement: {e(nd["title"])}, {nd["deadline"]}', f'첫 채점: {e(nd["title_ko"])}, {nd["deadline"]}', "h3"))
        b.append(two(f'We said {pc(nd["p_resolved"])} resolved and {pc(nd["p_worsened"])} worsened. What each outcome would score:', f'저희는 해소 {pc(nd["p_resolved"])}, 악화 {pc(nd["p_worsened"])}라고 적었습니다. 결과별 점수는 이렇습니다.'))
        b.append('<table><tr>' + two("Outcome", "결과", "th") + "<th>AFMX</th>" + two('"Nothing happens"', '"아무 일도 없다"', "th") + "</tr>" +
                 "".join(f'<tr>{two(*lab[r["outcome"]], "td")}<td>{r["afmx"]:.3f}</td><td>{r["nothing_happens"]:.3f}</td></tr>' for r in nd["what_if"]) + "</table>")
        b.append(two("One card settles nothing about skill. It is shown so the result cannot be dressed up afterwards.", "카드 한 장으로 실력은 가려지지 않습니다. 결과가 나온 뒤에 꾸밀 수 없도록 미리 적어 둡니다.", cls="su"))
    if s.get("calibration"):
        b.append(two("Said and came true", "말한 확률과 실제", "h3"))
        b.append('<table><tr>' + two("We said", "말한 확률", "th") + two("Questions", "질문", "th") + two("Came true", "실제", "th") + "</tr>" +
                 "".join(f'<tr><td>{pc(r["said"])}</td><td>{r["questions"]}</td><td>{pc(r["came_true"])}</td></tr>' for r in s["calibration"]["table"]) + "</table>")
    else:
        b.append(two(f"A table of what we said against what came true appears once {MIN_SETTLED} questions are settled. Before that it would be noise.", f"말한 확률과 실제 결과를 나란히 놓은 표는 질문 {MIN_SETTLED}개의 결과가 나온 뒤에 싣습니다. 그 전에는 잡음입니다."))
    b.append(two("2. What history says", "2. 과거는 무엇을 말하나", "h2"))
    b.append(two("For some cards there are past events of the same kind with dated starts and ends. We read them as a second opinion, kept apart from our judgment. Neither number replaces the other.",
                 "일부 카드에는 시작과 끝 날짜가 있는 같은 종류의 과거 사건이 있습니다. 저희 판단과 따로 두고 두 번째 의견으로 읽습니다. 어느 숫자도 다른 숫자를 대신하지 않습니다."))
    ko_title = m["titles_ko"]
    for r in m["history"]:
        src = " · ".join(f'<a href="{e(u)}" rel="noopener">{two("source", "출처", "span")}</a>' for u in r["sources"])
        b.append('<section class="card">' + two(e(r["title"]), e(ko_title.get(r["card"], r["title"])), "h3"))
        b.append(two(e(r["question_en"]), e(r["question_ko"]), cls="q"))
        lens = ", ".join(str(v) for v in r["lengths"])
        if r["use"] == "exceed":
            c = {x["cut"]: x for x in r["cuts"]}
            f = lambda k: f'{c[k]["over"]} of {c[k]["of"]}'
            g = lambda k: f'{c[k]["of"]}번 중 {c[k]["over"]}번'
            b.append(two(f'History: {f("all")} funding gaps since 1976 lasted more than {r["threshold_days"]} days ({pc(c["all"]["share"])}, 90% range {pc(c["all"]["range90"][0])} to {pc(c["all"]["range90"][1])}). Counting only gaps where agencies actually closed: {f("shutdown")}. Counting only gaps since 1990: {f("since_1990")}.',
                         f'과거: 1976년 이후 예산 공백 {g("all")}이 {r["threshold_days"]}일 넘게 이어졌습니다({pc(c["all"]["share"])}, 90% 범위 {pc(c["all"]["range90"][0])}~{pc(c["all"]["range90"][1])}). 기관이 실제로 문을 닫은 공백만 세면 {g("shutdown")}, 1990년 이후만 세면 {g("since_1990")}입니다.', cls="big2"))
            b.append(two("The answer moves from one in five to one in two depending on which past is counted. That choice is a judgment too.", "어느 과거를 세느냐에 따라 답이 다섯 번에 한 번에서 두 번에 한 번으로 바뀝니다. 그 선택도 판단입니다."))
            b.append(two(f'AFMX judgment: {pc(r["judgment"]["p_worsened"])} that any worsening condition is reached by {r["deadline"]}. That covers a lapse of any length, so the two numbers answer different questions.',
                         f'AFMX 판단: {r["deadline"]}까지 악화 조건 가운데 하나라도 닿을 확률 {pc(r["judgment"]["p_worsened"])}. 길이와 상관없이 예산이 끊기는 경우를 모두 포함하므로 두 숫자는 서로 다른 질문의 답입니다.'))
        elif r["use"] == "ends_by_deadline":
            b.append(two(f'History: this cycle began on {r["started"]} and has run {r["running_days"]} days. {r["past_cases_that_ran_this_long"]} of {r["cases"]} past cycles ran at least this long, and {r["of_those_ended_by_deadline_day"]} of those had ended by the point the deadline marks (day {r["deadline_day"]}). A simple constant-rate model gives {pc(r["constant_rate_ends_by_deadline"])}, with a 90% range of {pc(r["range90"][0])} to {pc(r["range90"][1])}.',
                         f'과거: 이번 인상기는 {r["started"]}에 시작해 {r["running_days"]}일째입니다. 과거 인상기 {r["cases"]}번 가운데 {r["past_cases_that_ran_this_long"]}번이 이만큼 이어졌고, 그중 기한에 해당하는 시점({r["deadline_day"]}일째)까지 끝난 것은 {r["of_those_ended_by_deadline_day"]}번입니다. 끝날 가능성이 매일 같다고 보는 단순한 모형으로는 {pc(r["constant_rate_ends_by_deadline"])}, 90% 범위는 {pc(r["range90"][0])}~{pc(r["range90"][1])}입니다.', cls="big2"))
            b.append(two(f'AFMX judgment: {pc(r["judgment"]["p_resolved"])} resolved by {r["deadline"]}.', f'AFMX 판단: {r["deadline"]}까지 해소 {pc(r["judgment"]["p_resolved"])}.'))
        else:
            b.append(two(f'History: {lens} days in the {r["cases"]} cases read so far.', f'과거: 지금까지 읽은 {r["cases"]}건은 {lens}일이었습니다.', cls="big2"))
            b.append(two(f'AFMX judgment: {pc(r["judgment"]["p_resolved"])} resolved by {r["deadline"]}.', f'AFMX 판단: {r["deadline"]}까지 해소 {pc(r["judgment"]["p_resolved"])}.'))
        b.append(two("Where it does not fit: " + e(r["fit_en"]), "맞지 않는 부분: " + e(r["fit_ko"]), cls="su"))
        b.append(f'<p class="su">{two(e(r["class_en"]) + ". Lengths in days: " + lens + ".", e(r["class_ko"]) + ". 길이(일): " + lens + ".", "span")} {src}</p></section>')
    rest = m["cards_open"] - len(m["history"])
    b.append(two(f'The other {rest} open cards have no such history yet. Their past cases have a start date but no dated end, or the event is one of a kind. For those the judgment stands alone.',
                 f'나머지 열린 카드 {rest}장에는 아직 이런 과거가 없습니다. 과거 사례에 시작일만 있고 끝난 날짜가 없거나, 비슷한 사건이 없습니다. 이 카드들은 판단만 있습니다.'))
    o = m["own_cards"]
    b.append(two("3. Our own cards", "3. AFMX의 카드", "h2"))
    b.append(two(f'The better evidence will be our own record: how long AFMX cards take to close, counted so that cards still open are included as "not closed yet". Today: {o["cards"]} cards, {o["resolved"]} resolved, {o["card_days"]} card-days of record. That is nothing yet. A curve is drawn from {MIN_CARDS} resolved cards on, which will take years at the current pace.',
                 f'더 나은 근거는 저희 기록 자체입니다. AFMX 카드가 닫히기까지 걸린 시간을, 아직 열린 카드도 "아직 닫히지 않음"으로 넣어 셉니다. 지금은 카드 {o["cards"]}장, 해소 {o["resolved"]}장, 기록은 모두 합쳐 {o["card_days"]}일입니다. 아직 아무것도 아닙니다. 곡선은 해소된 카드가 {MIN_CARDS}장이 되면 그리며, 지금 속도로는 몇 해가 걸립니다.'))
    b.append(two("Limits", "한계", "h2"))
    b.append("<ul>" + "".join(two(a, k, "li") for a, k in (
        ("The odds are judgment. The arithmetic checks them; it does not produce them.", "확률은 판단입니다. 계산은 판단을 점검할 뿐 만들어 내지 않습니다."),
        ("History here is 2 to 20 cases per kind, chosen and read by us, in hindsight.", "여기의 과거는 종류마다 2~20건이고, 저희가 고르고 읽었으며, 지나고 나서 본 것입니다."),
        ("A past event rarely matches a card's conditions exactly. Each card says where it does not.", "과거 사건이 카드의 조건과 꼭 맞는 경우는 드뭅니다. 어디가 맞지 않는지 카드마다 적었습니다."),
        ("A forecast is never edited. A change to one fails an automatic check on the repository.", "한 번 적은 예측은 고치지 않습니다. 고치면 저장소의 자동 점검에서 걸립니다."),
        ("Not investment advice.", "투자 조언이 아닙니다."))) + "</ul>")
    b.append(f'<p class="su">{two("Computed for " + m["as_of"] + ".", m["as_of"] + " 기준 계산.", "span")} <a href="https://github.com/ksjaj-hub/risk-ledger/blob/main/forecasts/README.md" rel="noopener">{two("Rules and method", "규칙과 방법", "span")}</a> · <a href="https://github.com/ksjaj-hub/risk-ledger/blob/main/forecasts/math.json" rel="noopener">{two("All numbers", "전체 숫자", "span")}</a></p>')
    return PAGE.replace("__BODY__", "\n".join(b))


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AFMX: the arithmetic behind the odds</title>
<meta name="description" content="How the odds on AFMX event cards are scored, and what past events of the same kind say.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..700&family=Noto+Sans+KR:wght@400;500;700&display=swap">
<style>
:root{color-scheme:dark;--bg:#07080a;--line:#1c2026;--line2:#2b3139;--fg:#e9ebee;--muted:#8d959e;--link:#86b4ee;--sans:"Archivo","Noto Sans KR",system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}
html,body{background:var(--bg);margin:0}
html[lang="ko"] body{word-break:keep-all;overflow-wrap:anywhere}
html[lang="ko"] [lang="en"],html[lang="en"] [lang="ko"]{display:none}
body{color:var(--fg);font-family:var(--sans);font-size:16px;line-height:1.65;-webkit-text-size-adjust:100%}
a{color:var(--link);text-decoration:underline;text-underline-offset:3px}
.wrap{max-width:680px;margin:0 auto;padding:0 16px}
.bar{border-bottom:1px solid var(--line)}
.bar .wrap{display:flex;align-items:center;justify-content:space-between;height:48px}
.brand{display:flex;align-items:center;font-weight:700;font-stretch:118%;letter-spacing:.09em;font-size:13px;color:var(--fg);min-height:44px;text-decoration:none}
.lang{display:flex;border:1px solid var(--line2)}
.lang button{background:none;border:0;font:inherit;cursor:pointer;padding:0 12px;min-height:44px;font-size:13px;font-weight:600;color:var(--muted)}
.lang button[aria-pressed="true"]{background:var(--fg);color:var(--bg)}
main{padding:28px 0 56px}
h1{font-size:30px;line-height:1.15;font-stretch:108%;margin:0 0 12px}
h2{font-size:20px;margin:40px 0 10px;padding-top:18px;border-top:1px solid var(--line2)}
h3{font-size:16px;margin:24px 0 6px}
p{margin:0 0 12px}
.lead{color:var(--muted)}
.big{font-size:19px;font-weight:600;line-height:1.4}
.big2{font-weight:600}
.q,.su{color:var(--muted);font-size:14px}
.card{border-top:1px solid var(--line);margin-top:18px}
table{border-collapse:collapse;width:100%;margin:0 0 12px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 8px 8px 0;border-bottom:1px solid var(--line);font-size:14px}
th{color:var(--muted);font-weight:500}
ul{padding-left:18px;margin:0 0 12px}li{margin-bottom:6px}
</style>
</head>
<body>
<div class="bar"><div class="wrap"><a class="brand" href="./">AFMX</a><div class="lang" role="group" aria-label="Language"><button type="button" data-lang="en">EN</button><button type="button" data-lang="ko">한국어</button></div></div></div>
<main class="wrap">
__BODY__
</main>
<script>
let lang="en";try{lang=localStorage.getItem("lang")||((navigator.language||"").startsWith("ko")?"ko":"en")}catch(e){}
const set=()=>{document.documentElement.lang=lang;document.querySelectorAll("[data-lang]").forEach(b=>b.setAttribute("aria-pressed",b.dataset.lang===lang))};
document.querySelectorAll("[data-lang]").forEach(b=>b.addEventListener("click",()=>{lang=b.dataset.lang;try{localStorage.setItem("lang",lang)}catch(e){}set()}));set();
</script>
</body>
</html>
"""


# ---------- commands ----------
def build(asof):
    cards = {c["id"]: c for c in (json.loads(pathlib.Path(f).read_text()) for f in sorted(glob.glob(str(ROOT / "events" / "*.json"))))}
    ko = json.loads((ROOT / "i18n" / "events.ko.json").read_text())
    titles_ko = {k: v["title"] for k, v in ko.items() if isinstance(v, dict) and "title" in v}
    sc = json.loads((ROOT / "forecasts" / "scorecard.json").read_text())
    done = [r for r in sc["rows"] if r["outcome"] is not None and r["first_for_deadline"]]
    scoring = {"settled": len(done), "min_settled_for_any_claim": MIN_SETTLED, "brier": None, "nothing_happens": None, "always_50pct": 0.25}
    if done:
        bs, ref, base = brier(done), sum(r["outcome"] ** 2 for r in done) / len(done), sum(r["outcome"] for r in done) / len(done)
        scoring.update({"brier": round(bs, 4), "nothing_happens": round(ref, 4),
                        "skill_vs_nothing_happens": round(1 - bs / ref, 3) if ref else None, "skill_vs_50pct": round(1 - bs / 0.25, 3),
                        "base_rate_in_hindsight": round(base, 3), "skill_vs_base_rate_in_hindsight": round(1 - bs / (base * (1 - base)), 3) if 0 < base < 1 else None})
        if len({r["card"] for r in done}) >= MIN_CARDS:
            scoring["difference_range90_by_card"] = card_bootstrap(done)
        if len(done) >= MIN_SETTLED:
            scoring["calibration"] = murphy(done)
    live = [c for c in cards.values() if c["status"] == "open" and c.get("forecasts") and not c["forecasts"][-1].get("outcome")]
    scoring["if_exactly_right"] = expectation([(c["forecasts"][-1]["p_resolved"], c["forecasts"][-1]["p_worsened"]) for c in live])
    nxt = min(live, key=lambda c: c["forecasts"][-1]["deadline"], default=None)
    scoring["next_deadline"] = nxt and {"card": nxt["id"], "title": nxt["title"], "title_ko": titles_ko.get(nxt["id"], nxt["title"]), "deadline": nxt["forecasts"][-1]["deadline"],
                                        "p_resolved": nxt["forecasts"][-1]["p_resolved"], "p_worsened": nxt["forecasts"][-1]["p_worsened"],
                                        "what_if": what_if(nxt["forecasts"][-1]["p_resolved"], nxt["forecasts"][-1]["p_worsened"])}
    m = {"note": "Arithmetic on the card forecasts. Part A scores them; part B reads past events as a second opinion. Thin evidence: see the limits on docs/odds.html.",
         "as_of": asof.isoformat(), "cards_open": sum(c["status"] == "open" for c in cards.values()),
         "scoring": scoring, "history": history(cards, asof), "own_cards": own_cards(cards, asof), "titles_ko": titles_ko}
    (ROOT / "docs" / "odds.html").write_text(page(m))
    del m["titles_ko"]
    (ROOT / "forecasts" / "math.json").write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    x = scoring["if_exactly_right"]
    print(f'{scoring["settled"]} settled; if exactly right: {x["expected_brier"]} vs {x["expected_nothing_happens"]}, loses by chance {x["chance_no_better_than_nothing_happens"]}; {len(m["history"])} cards with history')


def guard(ref):
    bad = []
    names = subprocess.run(["git", "ls-tree", "--name-only", ref, "events/"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for name in (n for n in names if n.endswith(".json")):
        old = json.loads(subprocess.run(["git", "show", f"{ref}:{name}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout).get("forecasts", [])
        p = ROOT / name
        new = {f["n"]: f for f in json.loads(p.read_text()).get("forecasts", [])} if p.exists() else {}
        for f in old:
            g = new.get(f["n"])
            if g is None or any(g.get(k) != f.get(k) for k in ("written_on", "deadline", "p_resolved", "p_worsened", "basis")):
                bad.append(f"{name} forecast {f['n']}: changed or removed")
            elif f.get("outcome") and g.get("outcome") != f["outcome"]:
                bad.append(f"{name} forecast {f['n']}: a recorded outcome was changed")
    print("\n".join(bad) or "forecasts unchanged")
    return 1 if bad else 0


def selftest():
    rows = [{"card": "a", "p": 0.7, "outcome": 1}, {"card": "a", "p": 0.1, "outcome": 0}, {"card": "b", "p": 0.2, "outcome": 0}, {"card": "b", "p": 0.2, "outcome": 1}]
    assert abs(brier(rows) - (0.09 + 0.01 + 0.04 + 0.64) / 4) < 1e-12
    mm = murphy([{"p": p, "outcome": o} for p, o in ((0.2, 0), (0.2, 0), (0.2, 1), (0.8, 1), (0.8, 1), (0.8, 0))])
    assert abs(mm["reliability"] - mm["resolution"] + mm["uncertainty"] - 0.24) < 2e-4, mm
    # worked by hand: 10 at risk, 3 end on day 6 (0.7); 6 at risk, 1 ends on day 7 (x 5/6); 4 at risk on day 10 (x 3/4); 1 on day 13
    km = kaplan_meier([(6, True), (6, True), (6, True), (6, False), (7, True), (9, False), (10, True), (10, False), (11, False), (13, True)])
    assert km == [(6, 0.7), (7, 0.5833), (10, 0.4375), (13, 0.0)], km
    assert abs(erlang_cdf(erlang_q(0.95, 5, 100.0), 5, 100.0) - 0.95) < 1e-9
    mean, rng = constant_rate(1, 100, 100)
    assert mean == 0.5 and rng[0] < mean < rng[1]
    assert wilson(0, 10)[0] == 0 and wilson(10, 10)[1] == 1
    x = expectation([(0.5, 0.0)], draws=20000)
    assert abs(x["expected_brier"] - 0.125) < 1e-9 and abs(x["expected_edge"] - 0.125) < 1e-9 and abs(x["chance_no_better_than_nothing_happens"] - 0.5) < 0.02
    w = what_if(0.7, 0.12)
    assert w[0]["afmx"] == round((0.09 + 0.0144) / 2, 4) and w[0]["nothing_happens"] == 0.5
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--selftest"]:
        selftest()
    elif a[:1] == ["--guard"]:
        raise SystemExit(guard(a[1]))
    else:
        build(D(a[a.index("--asof") + 1]) if "--asof" in a else dt.date.today())
