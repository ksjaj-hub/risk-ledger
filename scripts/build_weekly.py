#!/usr/bin/env python3
"""Builds one weekly note from weekly/N.json into docs/weekly/N.html (English first, with a language switch)
and docs/weekly/N.ko.html (Korean). Usage: python3 scripts/build_weekly.py 1
The JSON holds the wording and a snapshot of the numbers on the day of writing, so a note does not drift
when the record moves on. Section order is fixed here; see weekly/README.md. Reading aid, not part of the record."""
import html, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://ksjaj-hub.github.io/risk-ledger/"
STATES = {"en": ["Calm", "Guarded", "Watch", "Elevated", "Stress"], "ko": ["평온", "관심", "주의", "경계", "위기"]}
COMP = {"en": {"equity_volatility": "Equity volatility", "credit_stress": "Credit stress", "financial_conditions": "Financial conditions",
               "equity_drawdown": "Equity drawdown", "yield_curve": "Yield curve"},
        "ko": {"equity_volatility": "주식 변동성", "credit_stress": "신용 불안", "financial_conditions": "금융 여건",
               "equity_drawdown": "주가 낙폭", "yield_curve": "금리 곡선"}}
MONTHS = "January February March April May June July August September October November December".split()
T = {"en": dict(lbl=lambda n, d: f"AFMX Weekly · No. {n} · {d}", of="out of 100",
                since=lambda d, m, s: f"Since {d} · in the past {s} typically lasted {m} trading days",
                h_score=lambda a, b: f"What a score of {a} to {b} has meant", mix=["Within 5%", "Down 5 to 10%", "Down 10 to 20%", "Down more than 20%"],
                under1="under 1%", more="Read more", less="Show less", cells=lambda n: f"{n} of 3 cells",
                h_cards="Event cards", counts=["Open", "Worse", "Eased", "Resolved"],
                met=lambda m, n: f"Resolution measures met: {m} of {n}.",
                shows=lambda k, n, names: f"Prices show the risk on {k} of the {n} cards checked" + (f": {names}." if names else "."),
                h_counter="The case against one of our cards", h_relief="Good news that left the risk in place",
                h_new="New facts this week", src="Sources", h_sectors="Sectors", strained="Strained", quiet="Quiet", normal="Normal",
                changed="Changed this week", all_sectors="All sector steps", h_dates="Dates ahead", sample="Sample briefing",
                h_about="What this is and is not", all_cards="See all 12 cards", cta="Get the next one by email", ko_note=""),
     "ko": dict(lbl=lambda n, d: f"AFMX 주간 글 · {n}호 · {d}", of="100점 중",
                since=lambda d, m, s: f"{d}부터 · 과거 {s}는 보통 {m}거래일",
                h_score=lambda a, b: f"{a}~{b}점 뒤에 과거에 있었던 일", mix=["5% 안쪽", "5~10% 조정", "10~20% 하락", "20% 넘게 하락"],
                under1="1% 미만", more="더 보기", less="접기", cells=lambda n: f"3칸 중 {n}칸",
                h_cards="사건 카드", counts=["열림", "악화", "완화", "해소"],
                met=lambda m, n: f"해소 기준 {n}개 중 {m}개 충족.",
                shows=lambda k, n, names: f"가격과 대조한 카드 {n}장 중 {k}장은 가격에 리스크가 보입니다" + (f": {names}." if names else "."),
                h_counter="저희 카드 하나에 대한 반론", h_relief="호재 뒤에 남은 것",
                h_new="이번 주 새로 확인한 사실", src="출처", h_sectors="섹터", strained="긴장", quiet="잠잠", normal="평소",
                changed="이번 주 바뀜", all_sectors="섹터 단계 전체", h_dates="다가오는 날짜", sample="브리핑 견본",
                h_about="이 글이 하는 것과 하지 않는 것", all_cards="카드 12건 모두 보기", cta="다음 글을 이메일로 받기",
                ko_note="영어 원문을 옮긴 것입니다.")}
CSS = """:root{color-scheme:dark;--bg:#07080a;--line:#1c2026;--line2:#2b3139;--fg:#e9ebee;--muted:#8d959e;--link:#86b4ee;--watch:#e2a43a;--sans:"Archivo","Noto Sans KR",system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}
html,body{background:var(--bg);margin:0}
html[lang="ko"] body{word-break:keep-all;overflow-wrap:anywhere}
body{color:var(--fg);font-family:var(--sans);font-size:16px;line-height:1.65;-webkit-text-size-adjust:100%}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}p a,li a{text-decoration:underline;text-underline-offset:3px}
.wrap{max-width:680px;margin:0 auto;padding:0 16px}
.bar{border-bottom:1px solid var(--line)}
.bar .wrap{display:flex;align-items:center;justify-content:space-between;height:48px}
.brand{display:flex;align-items:center;gap:8px;font-weight:700;font-stretch:118%;letter-spacing:.09em;font-size:13px;color:var(--fg);min-height:44px}
.lang{display:flex;border:1px solid var(--line2)}
.lang button{background:none;border:0;font:inherit;cursor:pointer;padding:0 12px;min-height:44px;font-size:13px;font-weight:600;color:var(--muted)}
.lang button[aria-pressed="true"]{background:var(--fg);color:var(--bg)}
article{padding:28px 0 56px}
.lbl{font-size:13px;letter-spacing:.04em;color:var(--muted)}
.now{margin:14px 0 26px;padding:16px 0;border-top:1px solid var(--line2);border-bottom:1px solid var(--line2)}
.now .st{font-size:30px;line-height:1.1;font-weight:700;font-stretch:108%;color:var(--watch);margin:0}
.now .st span{color:var(--fg);font-weight:600;font-size:22px}.now .st small{color:var(--muted);font-weight:400;font-size:14px}
.steps{display:flex;gap:4px;margin:12px 0 6px}.steps i{flex:1;height:6px;background:var(--line2)}.steps i.on{background:var(--watch)}
.stn{display:flex;gap:4px;font-size:13px;color:var(--muted);margin:0 0 10px}.stn span{flex:1}.stn .on{color:var(--watch);font-weight:600}
.now .since{font-size:14px;color:var(--muted);margin:0}
h1{font-size:32px;line-height:1.18;font-weight:700;font-stretch:108%;letter-spacing:-.01em;margin:0 0 12px;text-wrap:balance}
.lead{font-size:18px;color:var(--muted);margin:0 0 8px}
.note{font-size:13px;color:var(--muted);margin:0 0 6px}
h2{font-size:20px;line-height:1.3;font-weight:700;margin:38px 0 12px;padding-top:20px;border-top:1px solid var(--line)}
h3{font-size:13px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:600;margin:22px 0 2px}
p{margin:0 0 14px}b{font-weight:600}
ul{margin:0;padding:0;list-style:none}
li{padding:12px 0;border-bottom:1px solid var(--line)}li:last-child{border-bottom:0}
li p{margin:0}li .h{font-weight:600}
.mixbar{display:flex;height:14px;gap:2px;margin:4px 0 10px}.mixbar i{display:block;min-width:3px}
.m0{background:#59626d}.m1{background:#a8905a}.m2{background:#e2a43a}.m3{background:#e5604d}
.mix li{display:flex;align-items:center;gap:10px;padding:7px 0;border:0}.mix li i{width:10px;height:10px;flex:none}.mix li span{flex:1}.mix li b{font-variant-numeric:tabular-nums}
.counts{display:flex;border:1px solid var(--line2);margin:0 0 6px}.counts div{flex:1;padding:10px 0;text-align:center;border-left:1px solid var(--line2);font-size:13px;color:var(--muted)}.counts div:first-child{border-left:0}.counts b{display:block;font-size:22px;line-height:1.2;color:var(--fg);font-variant-numeric:tabular-nums}
details{margin:6px 0 0}
summary{list-style:none;cursor:pointer;color:var(--link);font-size:14px;min-height:44px;display:inline-flex;align-items:center;gap:6px}
summary::-webkit-details-marker{display:none}
summary::after{content:"";width:7px;height:7px;border-right:1.5px solid;border-bottom:1.5px solid;transform:translateY(-2px) rotate(45deg)}
details[open]>summary::after{transform:translateY(2px) rotate(-135deg)}
summary .l,details[open]>summary .m{display:none}details[open]>summary .l{display:inline}
details .in{color:#c3c8ce;font-size:15px;padding:0 0 4px}details .in p{margin:0 0 10px}
.srcs{font-size:13px;color:var(--muted)}.srcs a{display:inline-block;padding:4px 0}
.cells{display:inline-flex;gap:3px;vertical-align:middle;margin-right:8px}.cells i{width:16px;height:8px;background:var(--line2)}.cells i.on{background:var(--fg)}
.comp li{display:flex;justify-content:space-between;gap:10px;padding:8px 0;font-size:15px}.comp li span:last-child{color:var(--muted);white-space:nowrap}
.sec{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--line)}.sec:last-of-type{border-bottom:0}
.sec .k{flex:none;width:76px;font-weight:600}.sec .k.hi{color:var(--watch)}.sec .k small{display:block;font-weight:400;color:var(--muted);font-size:13px}
.tag{display:inline-block;font-size:13px;color:var(--bg);background:var(--watch);font-weight:600;padding:1px 8px;margin-bottom:10px}
.dt{display:flex;gap:14px}.dt .d{flex:none;width:112px;font-size:14px;color:var(--muted)}.dt .d b{display:block;color:var(--fg);font-size:15px}
.dt .b{flex:1;min-width:0}
.cta{margin-top:32px}
.btn{display:inline-block;background:var(--fg);color:var(--bg);font-weight:600;font-size:15px;padding:12px 18px;min-height:44px}
.btn:hover{background:#fff;text-decoration:none}
[data-l]{display:none}
html[lang="en"] [data-l="en"],html[lang="ko"] [data-l="ko"]{display:block}
@media(max-width:600px){h1{font-size:26px}.dt .d{width:96px}}"""
E = html.escape


def fmt(date, lang):
    y, m, d = (int(x) for x in date.split("-"))
    return f"{MONTHS[m-1]} {d}, {y}" if lang == "en" else f"{y}.{m}.{d}"


def fold(t, paras, srcs=()):
    if not paras and not srcs:
        return ""
    body = "".join(f"<p>{E(x)}</p>" for x in paras)
    if srcs:
        body += f'<p class="srcs">{t["src"]}: ' + " · ".join(f'<a href="{E(u)}">{E(n)}</a>' for n, u in srcs) + "</p>"
    return f'<details><summary><span class="m">{t["more"]}</span><span class="l">{t["less"]}</span></summary><div class="in">{body}</div></details>'


def article(I, lang, names):
    t, c, s = T[lang], I[lang], I["snapshot"]
    st, band = STATES[lang], s["band"]
    pct = lambda v: t["under1"] if v < 1 else f"{v:g}%"
    o = [f'<article lang="{lang}" data-l="{lang}">', f'<div class="lbl">{t["lbl"](I["n"], fmt(I["date"], lang))}</div>']
    o.append('<div class="now"><p class="st">%s <span>· %d</span> <small>%s</small></p>' % (st[s["state_index"]], s["score"], t["of"]))
    o.append('<div class="steps" aria-hidden="true">' + "".join(f'<i{" class=on" if i == s["state_index"] else ""}></i>' for i in range(5)) + "</div>")
    o.append('<div class="stn" aria-hidden="true">' + "".join(f'<span{" class=on" if i == s["state_index"] else ""}>{x}</span>' for i, x in enumerate(st)) + "</div>")
    o.append(f'<p class="since">{t["since"](fmt(s["since"], lang), s["typical_days"], st[s["state_index"]])}</p></div>')
    o.append(f'<h1>{E(c["title"])}</h1><p class="lead">{E(c["lead"])}</p>')
    if t["ko_note"]:
        o.append(f'<p class="note">{t["ko_note"]}</p>')
    if c.get("revised"):
        o.append(f'<p class="note">{E(c["revised"])}</p>')
    # 1. what the score has meant
    o.append(f'<h2>{t["h_score"](band["from"], band["to"])}</h2><p>{E(c["score_p"])}</p>')
    o.append('<div class="mixbar" aria-hidden="true">' + "".join(f'<i class="m{i}" style="flex:{max(v, .5)}"></i>' for i, v in enumerate(band["mix"])) + "</div>")
    o.append('<ul class="mix">' + "".join(f'<li><i class="m{i}"></i><span>{t["mix"][i]}</span><b>{pct(v)}</b></li>' for i, v in enumerate(band["mix"])) + "</ul>")
    o.append(f'<p class="note">{E(c["score_note"])}</p>')
    comp = '<ul class="comp">' + "".join(
        f'<li><span>{COMP[lang][k]}</span><span><span class="cells" aria-hidden="true">' + "".join(f'<i{" class=on" if j < n else ""}></i>' for j in range(3)) + f'</span>{t["cells"](n)}</span></li>'
        for k, n in s["components"]) + "</ul>"
    o.append(fold(t, [c["score_more"]]).replace("</div></details>", comp + "</div></details>"))
    # 2. event cards
    o.append(f'<h2>{t["h_cards"]}</h2><div class="counts">' + "".join(f'<div><b>{s["cards"][k]}</b>{t["counts"][i]}</div>' for i, k in enumerate(["open", "worse", "eased", "resolved"])) + "</div>")
    ck = s.get("checks")  # from No. 2 on: the cards' numeric count and price check, see weekly/README.md
    ckp = f'<p>{t["met"](ck["met"], ck["measures"])} {E(t["shows"](len(ck["shows"]), ck["checked"], ", ".join(x[lang] for x in ck["shows"])))}</p>' if ck else ""
    o.append(f'<p class="note">{E(c["cards_p"])}</p>{ckp}<h3>{t["h_relief"]}</h3><ul>')
    for r in c["relief"]:
        o.append(f'<li><p class="h">{E(r["h"])}</p><p>{E(r["p"])}</p>{fold(t, r["more"], r["src"])}</li>')
    if c.get("counter"):  # one counter view of the week, quoted from a card
        o.append(f'</ul><h3>{t["h_counter"]}</h3><ul><li><p class="h">{E(c["counter"]["h"])}</p><p>{E(c["counter"]["p"])}</p></li>')
    o.append(f'</ul><h3>{t["h_new"]}</h3><ul>')
    for r in c["new"]:
        o.append(f'<li><p><b>{E(r["h"])}</b> {E(r["p"])} <a href="{E(r["src"][1])}">{E(r["src"][0])}</a></p></li>')
    home = "../" + ("?lang=ko" if lang == "ko" else "")
    o.append(f'</ul><p><a href="{home}#risks">{t["all_cards"]}</a></p>')
    # 3. sectors
    sec, nm = s["sectors"], lambda ks: ", ".join(names[k][lang] for k in ks)
    o.append(f'<h2>{t["h_sectors"]}</h2><p>{E(c["sectors_p"])}</p>')
    if sec["changed"]:
        o.append("<ul>" + "".join(f'<li><b>{names[k][lang]}</b> {t[a]} → {t[b]}</li>' for k, a, b in sec["changed"]) + "</ul>")
    o.append(f'<div class="sec"><div class="k hi">{t["strained"]}<small>{len(sec["strained"])}</small></div><div>{nm(sec["strained"])}</div></div>')
    o.append(f'<div class="sec"><div class="k">{t["quiet"]}<small>{len(sec["quiet"])}</small></div><div>{nm(sec["quiet"])}</div></div>')
    o.append(fold(t, [f'{t["normal"]} ({len(sec["normal"])}): {nm(sec["normal"])}', c["sectors_more"]]).replace(
        "</div></details>", f'<p><a href="{home}#sectors">{t["all_sectors"]}</a></p></div></details>'))
    # 4. dates ahead, with the sample briefing
    o.append(f'<h2>{t["h_dates"]}</h2><span class="tag">{t["sample"]}</span><p class="note">{E(c["dates_p"])}</p><ul>')
    for d in c["dates"]:
        o.append(f'<li class="dt"><div class="d"><b>{E(d["d"])}</b>{E(d["t"])}</div><div class="b"><p class="h">{E(d["h"])}</p>{fold(t, d["more"])}</div></li>')
    o.append('</ul><p class="srcs">%s: %s</p>' % (t["src"], " · ".join(f'<a href="{E(u)}">{E(n)}</a>' for n, u in c["dates_src"])))
    # 5. what this is
    o.append(f'<h2>{t["h_about"]}</h2><p>{c["about"]}</p>')
    o.append(f'<p class="cta"><a class="btn" href="{home}#subf">{t["cta"]}</a></p></article>')
    return "\n".join(o)


def page(I, fixed, names):
    n, c = I["n"], I[fixed or "en"]
    url = f"{SITE}weekly/{n}{'.ko' if fixed else ''}.html"
    head_title = (f"AFMX 주간 글 {n}호: " if fixed else f"AFMX Weekly No. {n}: ") + c["title"]
    js = 'let lang="ko";' if fixed else 'let lang="en";try{lang=localStorage.getItem("lang")||((navigator.language||"").startsWith("ko")?"ko":"en")}catch(e){if((navigator.language||"").startsWith("ko"))lang="ko"}'
    return f"""<!doctype html>
<html lang="{fixed or 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(head_title)}</title>
<meta name="description" content="{E(c['desc'])}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="en" href="{SITE}weekly/{n}.html">
<link rel="alternate" hreflang="ko" href="{SITE}weekly/{n}.ko.html">
<meta property="og:type" content="article">
<meta property="og:site_name" content="AFMX">
<meta property="og:url" content="{url}">{'''
<meta property="og:locale" content="ko_KR">''' if fixed else ''}
<meta property="og:title" content="{E(c['title'])}">
<meta property="og:description" content="{E(c['desc'])}">
<meta property="og:image" content="{SITE}og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..700&family=Noto+Sans+KR:wght@400;500;700&display=swap">
<style>
{CSS}
</style>
</head>
<body>
<header class="bar"><div class="wrap">
  <a class="brand" href="../"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><rect x=".5" y=".5" width="15" height="15" fill="none" stroke="#e9ebee"/><rect x="0" y="9" width="7" height="7" fill="#e9ebee"/></svg>AFMX</a>
  <div class="lang" role="group" aria-label="Language"><button type="button" data-lang="en">EN</button><button type="button" data-lang="ko">한국어</button></div>
</div></header>
<main class="wrap">
{article(I, 'en', names)}
{article(I, 'ko', names)}
</main>
<script>
{js}
function set(){{document.documentElement.lang=lang;document.querySelectorAll("[data-lang]").forEach(b=>b.setAttribute("aria-pressed",b.dataset.lang===lang))}}
document.querySelectorAll("[data-lang]").forEach(b=>b.addEventListener("click",()=>{{lang=b.dataset.lang;try{{localStorage.setItem("lang",lang)}}catch(e){{}}set()}}));
set();
</script>
</body>
</html>
"""


def checks():
    """Prints the snapshot.checks block for a new issue from the current docs/data.json."""
    D = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8"))
    D["ko"] = json.loads((ROOT / "docs" / "ko.json").read_text(encoding="utf-8"))
    live = [e for e in D["events"] if e["status"] != "resolved"]
    its = [x for e in live for x in e.get("numeric_criteria", {}).get("items", []) if x["side"] == "resolved"]
    mk = D["aids"].get("market", {}).get("cards", {})
    checked = [e for e in live if mk.get(e["id"], {}).get("verdict") in ("shows", "does_not_show")]
    print(json.dumps({"checks": {"as_of": D["aids"].get("market", {}).get("as_of"), "measures": len(its), "met": sum(x["state"] == "met" for x in its),
                                 "checked": len(checked),
                                 "shows": [{"en": e["title"], "ko": D["ko"][e["id"]]["title"]} for e in checked if mk[e["id"]]["verdict"] == "shows"]}},
                     indent=1, ensure_ascii=False))


def main():
    if sys.argv[1] == "--checks":
        return checks()
    n = sys.argv[1]
    I = json.loads((ROOT / "weekly" / f"{n}.json").read_text(encoding="utf-8"))
    names = json.loads((ROOT / "aids" / "reading.json").read_text(encoding="utf-8"))["sector_names"]
    (ROOT / "docs" / "weekly" / f"{n}.html").write_text(page(I, None, names), encoding="utf-8")
    (ROOT / "docs" / "weekly" / f"{n}.ko.html").write_text(page(I, "ko", names), encoding="utf-8")
    print("built", n)


if __name__ == "__main__":
    main()
