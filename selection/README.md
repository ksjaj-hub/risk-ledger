# Why these cards: selection criteria

`criteria.json` says what gets a risk onto an event card, what closes a card, and how every current card measures
up. The public page is `docs/selection.html`, built from this file.

- **Six criteria to open a card** (`open_when_all`): a primary source states it, it is big enough, it has a named
  route to prices, it has an ending anyone can check, it was written before the outcome, and there is one card per cause.
- **Three ways a card closes** (`closed_when`): resolved, worsened, withdrawn. A card is never deleted.
- **The audit** (`audit`): each card against each criterion: `met`, `partly` or `not_met`, with the gap and what
  would fix it. A card that does not meet the criteria and is still shown must say why (`kept`) and carries a
  one-line mark on the page (`mark`).
- **Looked at and left out** (`left_out`): from 2026-11-27, each weekday check adds the events it considered and did
  not card, with the criterion they failed. Lines are added, never removed.

The criteria were written on 2026-11-27, the day after the first 12 cards. They check those cards after the fact;
they did not choose them. `limits` in the file says what else this does not settle.

## When a card is added or changes

1. Add or update its line under `audit.cards`. Be as strict with our own card as with anyone else's.
2. Run `python3 scripts/selection_check.py`. It counts what a script can count (a primary source, both kinds of
   condition, a deadline, a listed ticker), refuses an audit that is kinder than the count, and rewrites the page.
3. Run `python3 scripts/build_site.py`, so that the mark on the main page follows the audit.

A change to the criteria themselves is a new `version` with a dated line in `history`.

## 한국어 요약

`criteria.json`에 카드를 여는 기준 여섯 가지, 닫는 기준 세 가지, 지금 카드 12장을 기준에 맞춰 본 결과가 한국어와 영어로 들어 있습니다.
공개 페이지는 `docs/selection.html`입니다. 기준은 첫 카드들을 연 다음 날(2026-11-27)에 썼으므로, 그 카드들에는 나중에 맞춰 본 점검입니다.
카드를 새로 열거나 고칠 때는 `audit.cards`에 한 줄을 넣고 `scripts/selection_check.py`와 `scripts/build_site.py`를 차례로 돌립니다.
평일 점검에서 살펴보고 넣지 않은 사건은 `left_out`에 못 미친 기준과 함께 남깁니다.
