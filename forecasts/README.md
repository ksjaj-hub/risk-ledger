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

## The arithmetic

`python scripts/forecast_math.py` (after `forecast_score.py`) writes `math.json` and the public page `docs/odds.html`.

**Scoring.** Besides the two yardsticks above it reports, once questions settle: skill against each yardstick
(1 - Brier / yardstick Brier); from 10 settled cards, a 90% range of the difference found by resampling whole cards,
because a card's two questions move together; from 30 settled questions, a table of what was said against what came
true with Murphy's split into reliability, resolution and uncertainty. Before any result it also works out what a
round would look like if every probability were exactly right, so that a result cannot be explained away afterwards.

**History as a second opinion.** `reference_classes.json` lists past events of the same kind for the cards that have
them, with dates from primary sources. Durations are read with survival methods (Kaplan-Meier, and a constant-rate
model with a 90% range), so an event still running counts as "not ended yet". Each link says which part of the card
the history answers and where it does not fit. The history never changes a forecast and is not averaged into it.
AFMX's own cards get the same treatment once 10 have resolved.

**Limits.** 2 to 20 past cases per kind, picked and read in hindsight. Cards share causes, so the count of questions
overstates the evidence. The ECB dates are not yet checked row by row against the ECB table.

**Not built yet.** Updating a probability by a stated rule as facts arrive (Bayesian updating), and measuring the
market move around each card's dates (event study). Both need more settled cards to be worth more than the judgment.

The append-only guard (`.github/workflows/guard.yml`) fails if a forecast that exists on the base branch is changed
or removed, or a recorded outcome is altered.

`scorecard.json` is written by `python scripts/forecast_score.py`. First settlement: the US funding card,
2026-12-12.

## Residual risk index

`forecast_math.py` also writes one number from the open cards: **how many of them are expected to worsen in the next
90 days**, with an 80% range, and how many to resolve (`math.json` → `residual`, shown as part 4 of `docs/odds.html`,
one line a day in `forecasts/residual.csv`).

- Each card's latest forecast covers its writing date to its deadline. A constant rate inside that span cuts it to
  90 days; nothing is assumed past a deadline. The cut probabilities are added up.
- **It counts cards, not size.** No card has a measured size, and a made-up weight would be one more opinion.
- It inherits every weakness of the odds themselves, and the range treats cards as independent, which they are not.
- Check, fixed on 2026-11-28 before any card settled: for each recorded day that is at least 90 days old, the number
  of cards whose worsening condition was reached in the following 90 days is compared with the expected number and
  its 80% range. With 12 cards this says little before about 20 non-overlapping-quarter readings; until then the index
  is a summary of AFMX's judgment, not a measurement.

