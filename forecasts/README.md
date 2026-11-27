# Forecasts on event cards: deadline, probability, public score

Until 2026-11-27 a card said what would resolve a risk but not by when or how likely. That cannot be scored, and a
reader cannot tell a careful card from a vague one. From forecast 1 on, every open card carries:

- **a deadline**, a calendar date;
- **p_resolved**: the probability that *every* resolution condition on the card is met on or before the deadline;
- **p_worsened**: the probability that *any* worsening condition is reached between the day the forecast was
  written and the deadline;
- **basis**: one or two sentences on why.

The conditions are the card's own, counted as its `numeric_criteria` say. The two events are not opposites: both can
fail to happen, and that is the usual outcome.

## Whose numbers these are

They are **AFMX's own judgment**, written from the facts on the card. They are not market-implied odds, not a model
output and not advice. They may be badly wrong. That is why they are fixed and scored.

## Rules

1. A forecast is never edited. A new view is a new forecast (`n` + 1) with its own date; the old one stays and is
   still scored.
2. A question is settled early when its event happens before the deadline (outcome 1), otherwise on the deadline
   (outcome 0). The card's `history` records the date and the source.
3. Score: the Brier score, (probability - outcome)^2, lower is better. Each card has two questions.
4. The headline score uses **forecast 1 of each deadline only**, so a late revision cannot repair an early miss.
   Revisions are scored separately.
5. Two yardsticks are published next to it: always saying 50% (score 0.25), and always saying "nothing will happen"
   (0%). The second is hard to beat when most cards stay open, and AFMX has to beat it to claim any skill.
6. When a deadline passes and the card is still open, the next forecast gets a new deadline.
7. Fewer than about 30 settled questions say very little. The count is shown with the score.

`scorecard.json` is written by `python scripts/forecast_score.py`. First settlement: the US funding card,
2026-12-12.
