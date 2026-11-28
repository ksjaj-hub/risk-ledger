#!/usr/bin/env python3
"""Short questions on scheduled releases (questions/README.md). Standard library only.

  python scripts/questions.py              checks and scores; writes questions/scorecard.json and docs/questions.html
  python scripts/questions.py --selftest   checks the scoring on small known cases
  python scripts/questions.py --guard REF  fails if a question that exists at git REF was changed or removed

An outcome is filled in by hand from the release:
  {"value": 4.2, "answer": 1, "settled_on": "YYYY-MM-DD", "source": "https://..."}   or   {"void": "reason", "settled_on": "..."}
"""
import datetime as dt, html, json, math, pathlib, random, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from forecast_math import PAGE, murphy

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "questions" / "questions.json"
MIN_SETTLED, MIN_RELEASES, MAX_DAYS_AHEAD, VOID_AFTER_DAYS = 30, 10, 21, 30
FIXED = ("written_on", "release", "question", "reading", "unit", "threshold", "previous", "no_change_answer", "p", "basis")
D = dt.date.fromisoformat
rkey = lambda q: q["release"]["name"]


def check(qs, today):
    bad, ids = [], set()
    for q in qs:
        i = q.get("id", "?")
        miss = [k for k in FIXED + ("id",) if k not in q]
        if miss:
            bad.append(f"{i}: missing {miss}")
            continue
        if i in ids:
            bad.append(f"{i}: duplicate id")
        ids.add(i)
        ahead = (D(q["release"]["date"]) - D(q["written_on"])).days
        if not 1 <= ahead <= MAX_DAYS_AHEAD:
            bad.append(f"{i}: written {ahead} days before the release; must be 1 to {MAX_DAYS_AHEAD}")
        if not 0 < q["p"] < 1:
            bad.append(f"{i}: p must be strictly between 0 and 1")
        if q["no_change_answer"] != int(q["previous"]["value"] >= q["threshold"]):
            bad.append(f"{i}: no_change_answer does not match previous value against threshold")
        if not {"en", "ko"} <= set(q["question"]):
            bad.append(f"{i}: question needs en and ko")
        o = q.get("outcome")
        if o and "void" not in o:
            if o.get("answer") != int(o["value"] >= q["threshold"]) or not o.get("source") or not o.get("settled_on"):
                bad.append(f"{i}: outcome needs value, source, settled_on, and an answer that matches value against threshold")
            elif o["settled_on"] < q["release"]["date"]:
                bad.append(f"{i}: settled before the release date")
        if not o and (today - D(q["release"]["date"])).days > VOID_AFTER_DAYS:
            bad.append(f"{i}: more than {VOID_AFTER_DAYS} days past the release with no outcome; settle it or mark it void")
    if qs and sum(q["threshold"] != q["previous"]["value"] for q in qs if "threshold" in q and "previous" in q) * 3 < len(qs):
        bad.append("fewer than one question in three has a line different from the previous figure (rule 5)")
    return bad


def release_bootstrap(rows, draws=4000, seed=7):
    """90% range of (AFMX Brier - 'no change' Brier), resampling whole releases because their questions move together."""
    by = {}
    for r in rows:
        by.setdefault(r["release"], []).append((r["p"] - r["outcome"]) ** 2 - (r["no_change"] - r["outcome"]) ** 2)
    groups, rng, out = list(by.values()), random.Random(seed), []
    for _ in range(draws):
        s = [x for g in (rng.choice(groups) for _ in groups) for x in g]
        out.append(sum(s) / len(s))
    out.sort()
    return [round(out[int(draws * 0.05)], 4), round(out[int(draws * 0.95)], 4)]


def if_exactly_right(pairs, draws=40000, seed=7):
    """pairs: (p, no_change_answer). If each p were the true chance: expected scores, and how often AFMX would still not beat 50%.
    Questions are drawn independently, which flatters the result: questions on one release share a surprise."""
    n = len(pairs)
    if not n:
        return None
    rng, lose = random.Random(seed), 0
    for _ in range(draws):
        lose += sum((p - (rng.random() < p)) ** 2 for p, _ in pairs) / n >= 0.25
    return {"questions": n, "expected_brier": round(sum(p * (1 - p) for p, _ in pairs) / n, 4), "always_50pct": 0.25,
            "expected_no_change": round(sum((1 - p) if a else p for p, a in pairs) / n, 4),
            "chance_no_better_than_50pct": round(lose / draws, 3)}


def score(qs):
    rows = [{"id": q["id"], "release": rkey(q), "release_date": q["release"]["date"], "written_on": q["written_on"], "p": q["p"],
             "no_change": q["no_change_answer"], "void": bool(q.get("outcome") and "void" in q["outcome"]),
             "outcome": (q.get("outcome") or {}).get("answer")} for q in qs]
    done = [r for r in rows if r["outcome"] is not None]
    for r in done:
        r["brier"] = round((r["p"] - r["outcome"]) ** 2, 4)
    live = [q for q in qs if not q.get("outcome")]
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    s = {"note": "Brier score, lower is better. One probability per question, never revised. Fewer than about 30 settled questions say very little.",
         "questions": len(rows), "settled": len(done), "void": sum(r["void"] for r in rows), "releases_settled": len({r["release"] for r in done}),
         "next_release": min((q["release"]["date"] for q in live), default=None),
         "brier": mean([r["brier"] for r in done]), "always_50pct": 0.25 if done else None,
         "no_change": mean([(r["no_change"] - r["outcome"]) ** 2 for r in done]),
         "if_exactly_right_all": if_exactly_right([(q["p"], q["no_change_answer"]) for q in qs if not (q.get("outcome") and "void" in q["outcome"])])}
    if len(done) >= MIN_SETTLED:
        s["calibration"] = murphy(done)
        if s["releases_settled"] >= MIN_RELEASES:
            s["difference_range90_by_release"] = release_bootstrap(done)
    s["rows"] = rows
    return s


# ---------- page ----------
e = html.escape


def two(en, ko, tag="p", cls=None):
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c} lang="en">{en}</{tag}><{tag}{c} lang="ko">{ko}</{tag}>'


MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
den = lambda d: f"{MON[D(d).month - 1]} {D(d).day}"
dko = lambda d: f"{D(d).month}월 {D(d).day}일"
pc = lambda p: f"{round(p * 100)}%"


def num(v, unit):
    if unit == "thousand":
        return (f"{v:+,.0f},000", f"{v * 1000:+,.0f}명")
    if unit == "pp":
        return ("no change", "동결") if v == 0 else (f"{v:+.2f} points", f"{v:+.2f}%포인트")
    return (f"{v}%", f"{v}%")


def qcard(q):
    o, r, pv = q.get("outcome"), q["release"], num(q["previous"]["value"], q["unit"])
    b = ['<section class="card">' + two(e(q["question"]["en"]), e(q["question"]["ko"]), "h3")]
    b.append(two(f'AFMX: {pc(q["p"])} yes', f'AFMX: 그렇다 {pc(q["p"])}', cls="big"))
    nc = ("yes", "그렇다") if q["no_change_answer"] else ("no", "아니다")
    b.append(two(f'Last time: {pv[0]}. If it repeats, the answer is {nc[0]}.', f'지난번: {pv[1]}. 그대로 나오면 답은 "{nc[1]}"입니다.'))
    if o and "void" in o:
        b.append(two("Void, not scored: " + e(o["void"]), "무효, 채점하지 않음: " + e(o.get("void_ko", o["void"])), cls="big2"))
    elif o:
        v, a = num(o["value"], q["unit"]), (("Yes", "그렇다") if o["answer"] else ("No", "아니다"))
        b.append(two(f'Result: {v[0]}. {a[0]}. Brier {(q["p"] - o["answer"]) ** 2:.3f}.', f'결과: {v[1]}. {a[1]}. 브라이어 점수 {(q["p"] - o["answer"]) ** 2:.3f}.', cls="big2"))
    src = (o or {}).get("source") or r["url"]
    b.append(f'<p class="su">{two(e(r["agency"]) + ", " + den(r["date"]) + " " + r["time_et"] + " ET. Written " + den(q["written_on"]) + ".", e(r["agency"]) + ", " + dko(r["date"]) + " " + r["time_et"] + " 미국 동부 시간. " + dko(q["written_on"]) + " 작성.", "span")} <a href="{e(src)}" rel="noopener">{two("source", "출처", "span")}</a></p></section>')
    return "\n".join(b)


def page(qs, s, asof):
    b, x = [], s["if_exactly_right_all"]
    b.append(two("Short questions, scored", "짧은 질문, 공개 채점", "h1"))
    b.append(two("Before an official number comes out, AFMX says how likely it is to clear a line. The probability is fixed in advance and scored when the number is printed. This is how you can check whether our percentages mean anything.",
                 "공식 수치가 나오기 전에, 그 수치가 기준선을 넘을 가능성을 AFMX가 미리 말합니다. 확률은 발표 전에 고정하고, 수치가 나오면 채점합니다. 저희가 말하는 퍼센트를 믿어도 되는지 직접 확인하는 방법입니다.", cls="lead"))
    if s["settled"]:
        b.append(two(f'Settled: {s["settled"]} questions. AFMX {s["brier"]:.3f}, always 50%: 0.250, no change: {s["no_change"]:.3f}. Lower is better.',
                     f'채점된 질문 {s["settled"]}개. AFMX {s["brier"]:.3f}, 항상 50%: 0.250, 변화 없음: {s["no_change"]:.3f}. 낮을수록 좋습니다.', cls="big"))
        if s["settled"] < MIN_SETTLED:
            b.append(two(f"Under {MIN_SETTLED} questions this is mostly luck. We make no claim yet.", f"질문 {MIN_SETTLED}개가 안 되면 대부분 운입니다. 아직 아무 주장도 하지 않습니다."))
    else:
        b.append(two(f'No result yet. {s["questions"]} questions are open; the first settles on {den(s["next_release"])}.', f'아직 결과가 없습니다. 질문 {s["questions"]}개가 열려 있고, 첫 결과는 {dko(s["next_release"])}에 나옵니다.', cls="big"))
    if "difference_range90_by_release" in s:
        lo, hi = s["difference_range90_by_release"]
        b.append(two(f"AFMX minus no change: 90% range {lo:+.3f} to {hi:+.3f}. Below zero favors AFMX.", f"AFMX에서 변화 없음을 뺀 값: 90% 범위 {lo:+.3f}~{hi:+.3f}. 0보다 작으면 AFMX가 낫습니다."))
    if "calibration" in s:
        rows = "".join(f'<tr><td>{pc(t["from"])} - {pc(t["to"])}</td><td>{t["questions"]}</td><td>{pc(t["said"])}</td><td>{pc(t["came_true"])}</td></tr>' for t in s["calibration"]["table"])
        b.append(f'<table><tr>{two("Said", "말한 확률", "th")}{two("Questions", "질문", "th")}{two("Average said", "말한 평균", "th")}{two("Came true", "실제", "th")}</tr>{rows}</table>')
    live = sorted((q for q in qs if not q.get("outcome")), key=lambda q: (q["release"]["date"], q["id"]))
    past = sorted((q for q in qs if q.get("outcome")), key=lambda q: (q["release"]["date"], q["id"]), reverse=True)
    if live:
        b.append(two("Open questions", "열린 질문", "h2"))
        b += [qcard(q) for q in live]
    if past:
        b.append(two("Results", "결과", "h2"))
        b += [qcard(q) for q in past]
    b.append(two("How it is scored", "채점 방법", "h2"))
    b.append("<ul>" + "".join(two(a, k, "li") for a, k in (
        ("The Brier score: the gap between the probability and what happened, squared. Saying 80% and being right scores 0.04; being wrong scores 0.64.", "브라이어 점수: 말한 확률과 실제 결과의 차이를 제곱한 값입니다. 80%라고 말하고 맞으면 0.04, 틀리면 0.64입니다."),
        ("Two yardsticks sit next to it. Always saying 50% scores 0.25. \"No change\" answers as if the last number repeats.", "옆에 기준 두 개를 둡니다. 항상 50%라고 말하면 0.25입니다. \"변화 없음\"은 지난 수치가 그대로 나온다고 답합니다."),
        ("Settled from the agency's own release, on the number as first printed. Later revisions do not count.", "발표 기관의 자료로, 처음 발표된 수치로 판정합니다. 나중에 고쳐진 수치는 세지 않습니다."),
        ("A question is never edited or dropped. If the agency does not publish the number within 30 days of the schedule, the question is void and stays on this page.", "질문은 고치거나 빼지 않습니다. 예정일부터 30일 안에 기관이 수치를 내지 않으면 무효로 하고 이 페이지에 남깁니다."))) + "</ul>")
    b.append(two("Limits", "한계", "h2"))
    lim = [("These are judgment, not a model and not market odds. Economist surveys and prediction markets answer the same questions with more information, and we do not compare against them yet.", "판단이며, 모형도 시장 확률도 아닙니다. 경제학자 설문과 예측 시장은 같은 질문에 더 많은 정보로 답하고, 저희는 아직 그것들과 비교하지 않습니다.")]
    if x:
        lim.append((f'Many of these are close calls. Even if every probability were exactly right, the expected score is {x["expected_brier"]:.3f} against 0.250 for always 50%, and with {x["questions"]} questions we would still fail to beat 50% about {pc(x["chance_no_better_than_50pct"])} of the time by luck.',
                    f'상당수가 반반에 가까운 질문입니다. 확률이 모두 정확해도 기대 점수는 {x["expected_brier"]:.3f}이고 항상 50%는 0.250입니다. 질문 {x["questions"]}개로는 운만으로 50%를 못 이기는 경우가 약 {pc(x["chance_no_better_than_50pct"])}입니다.'))
    lim += [("Questions on one release share one surprise, so the count overstates the evidence.", "같은 발표에 건 질문들은 하나의 놀라움을 함께 겪으므로, 질문 수는 근거를 실제보다 많아 보이게 합니다."),
            ("A good score here says the percentages are honest. It does not say the event cards are right.", "여기서 점수가 좋으면 퍼센트가 정직하다는 뜻입니다. 사건 카드가 맞다는 뜻은 아닙니다."),
            ("Not investment advice.", "투자 조언이 아닙니다.")]
    b.append("<ul>" + "".join(two(a, k, "li") for a, k in lim) + "</ul>")
    b.append(f'<p class="su">{two("Computed for " + asof.isoformat() + ".", asof.isoformat() + " 기준 계산.", "span")} <a href="https://github.com/ksjaj-hub/risk-ledger/blob/main/questions/README.md" rel="noopener">{two("Rules", "규칙", "span")}</a> · <a href="https://github.com/ksjaj-hub/risk-ledger/blob/main/questions/questions.json" rel="noopener">{two("Every question with its reasoning", "모든 질문과 근거", "span")}</a> · <a href="odds.html">{two("Odds on event cards", "사건 카드의 확률", "span")}</a></p>')
    return (PAGE.replace("AFMX: the arithmetic behind the odds", "AFMX: short questions, scored")
            .replace("How the odds on AFMX event cards are scored, and what past events of the same kind say.", "Probabilities on official releases, fixed in advance and scored in public.")
            .replace("__BODY__", "\n".join(b)))


# ---------- commands ----------
def build(asof=None):
    asof = asof or dt.date.today()
    qs = json.loads(SRC.read_text())["questions"]
    bad = check(qs, asof)
    s = score(qs)
    s["problems"] = bad
    (ROOT / "questions" / "scorecard.json").write_text(json.dumps(s, indent=1) + "\n")
    (ROOT / "docs" / "questions.html").write_text(page(qs, s, asof))
    late = [q["id"] for q in qs if not q.get("outcome") and D(q["release"]["date"]) < asof]
    print(f'short questions: {s["questions"]}, settled {s["settled"]}, Brier {s["brier"]}, next release {s["next_release"]}; {len(bad)} problems' + (f'; waiting for an outcome: {", ".join(late)}' if late else ""))
    print("\n".join(bad), end="\n" if bad else "")
    return 1 if bad else 0


def guard(ref):
    bad = []
    r = subprocess.run(["git", "show", f"{ref}:questions/questions.json"], cwd=ROOT, capture_output=True, text=True)
    old = json.loads(r.stdout)["questions"] if r.returncode == 0 else []
    new = {q["id"]: q for q in json.loads(SRC.read_text())["questions"]}
    for q in old:
        g = new.get(q["id"])
        if g is None or any(g.get(k) != q.get(k) for k in FIXED):
            bad.append(f"{q['id']}: changed or removed")
        elif q.get("outcome") and g.get("outcome") != q["outcome"]:
            bad.append(f"{q['id']}: a recorded outcome was changed")
    bad += check(list(new.values()), dt.date.today())
    print("\n".join(bad) or "questions unchanged")
    return 1 if bad else 0


def selftest():
    mk = lambda i, rel, p, nc, o: {"id": i, "written_on": "2026-01-01", "release": {"name": rel, "agency": "X", "date": "2026-01-08", "time_et": "08:30", "url": "u"},
                                   "question": {"en": "q", "ko": "q"}, "reading": "r", "unit": "%", "threshold": 1.0, "previous": {"value": 1.0 if nc else 0.9},
                                   "no_change_answer": nc, "p": p, "basis": "b",
                                   "outcome": None if o is None else {"value": 1.0 if o else 0.5, "answer": o, "settled_on": "2026-01-08", "source": "u"}}
    qs = [mk("a", "r1", 0.8, 1, 1), mk("b", "r1", 0.3, 0, 1), mk("c", "r2", 0.6, 1, 0), mk("d", "r2", 0.5, 0, None)]
    assert check(qs, D("2026-01-09")) == [], check(qs, D("2026-01-09"))
    s = score(qs)
    assert s["settled"] == 3 and abs(s["brier"] - round((0.04 + 0.49 + 0.36) / 3, 4)) < 1e-9 and abs(s["no_change"] - round(2 / 3, 4)) < 1e-9, s
    x = if_exactly_right([(0.5, 0)], draws=2000)
    assert x["expected_brier"] == 0.25 and x["expected_no_change"] == 0.5 and x["chance_no_better_than_50pct"] == 1.0
    x = if_exactly_right([(0.9, 1)] * 20, draws=5000)
    assert abs(x["expected_brier"] - 0.09) < 1e-9 and abs(x["expected_no_change"] - 0.1) < 1e-9 and x["chance_no_better_than_50pct"] < 0.02
    late = dict(mk("e", "r3", 0.5, 0, None), written_on="2026-01-08")
    assert any("days before" in m for m in check([late], D("2026-01-09")))
    wrong = mk("f", "r3", 0.5, 0, 1)
    wrong["outcome"]["answer"] = 0
    assert any("answer" in m for m in check([wrong], D("2026-01-09")))
    assert any("void" in m for m in check([mk("g", "r3", 0.5, 0, None)], D("2026-03-01")))
    lo, hi = release_bootstrap([{"release": "r1", "p": 0.8, "no_change": 0, "outcome": 1}, {"release": "r2", "p": 0.7, "no_change": 0, "outcome": 1}])
    assert lo <= hi < 0
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--selftest"]:
        selftest()
    elif a[:1] == ["--guard"]:
        raise SystemExit(guard(a[1]))
    else:
        raise SystemExit(build(D(a[a.index("--asof") + 1]) if "--asof" in a else None))
