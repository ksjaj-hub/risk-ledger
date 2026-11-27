# Risk waves (reading aid, hindsight)

`waves.json` measures what followed past shocks that resemble an open event card: how large the move was, in what
order it spread, and how long it lasted. It is **not** part of the ledger, not a forecast and not a recommendation.
The public page shows it on event cards: a chart for the oil and tariff cards, and a short list of similar past events for the others.

## What is measured

- **Size.** Cumulative US market return and sector return minus market return at 1, 5, 21, 63 and 126 trading days,
  and the largest market fall within 126 trading days. The same market measurements are taken from every trading day
  since 1990 (`oil_rule_summary.any_day_since_1990`) so a number after a shock can be set against an ordinary period.
- **Order.** For each series, the day of its extreme within 126 trading days and the first day it reached half of
  that extreme. Listed in `order` for each named episode.
- **Duration.** Trading days from the extreme until half of the move was first given back (`half_life_days`), and the
  first day the series was back at its baseline. For oil, also whether the price was still above the pre-shock price
  after 63, 126 and 252 trading days, and whether it made a new high after giving back half.

## Episodes

- Named episodes are listed in `episodes.json` with a start date quoted from a primary source. The baseline is the
  close of the last trading day before the start date.
- Rule-based oil episodes: the first day Brent closes at least 20% above its close 20 trading days earlier and at
  its highest close in 252 trading days; no new episode for 126 trading days. The rule was written before the
  results were seen and has not been tuned. Episodes that start on or after `current_from` belong to the open card
  and are kept out of the past range.

- Since 2026-11-27 other cards also have named episodes (shutdowns, debt limit standoffs, rate rises and others). Where the
  source gives the date the event was settled, `end` records it and the page shows how many days the event lasted.
  For these only the market measures are shown; they describe the whole US market in those months, not the event alone.

## Limits

- Hindsight, and few episodes: 14 rule-based oil episodes, two wars, two tariff announcements.
- The oil rule also catches rises that came with a strong economy, not only supply shocks.
- Other things happened in the same months (for example the 2022 rate rises).
- The order in which things moved was not stable across episodes; treat it as the weakest of the three.
- A half-life marks the first time half was given back. In 6 of 14 oil episodes the price later went above the
  earlier peak.
- Sectors are simple averages of French industries, not GICS sectors or ETFs. Equity data arrive about two months late.

Sources: Kenneth R. French Data Library; FRED (Brent spot from the U.S. Energy Information Administration).
Rerun: Actions, "risk wave", Run workflow.
