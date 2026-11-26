# Risk patterns (reading aid, hindsight)

Five measurements that resemble the risk wave were computed and scored. Only those that pass the rule fixed in
advance are shown on the public page. Nothing here is part of the ledger, a forecast or a recommendation.

- `criteria.json`: definitions, the evidence rule and the pass rule. Committed before any result existed.
- `dates.json`: hand-kept date lists, with their official sources and what could not be read.
- `patterns.json`: results, written by `scripts/patterns.py` (Actions, "risk patterns").
- `judgment.json`: the three judgment scores for each candidate, with reasons.

## Scorecard (run of 2026-11-26, US market 1990-01-02 to 2026-09-30)

| candidate | evidence | usefulness | fit | upkeep | total | result |
|---|---|---|---|---|---|---|
| aftershocks | 5 | 4 | 4 | 5 | 18 | shown |
| overlap | 3 | 4 | 5 | 4 | 16 | shown |
| reverberation | 1 | 3 | 5 | 5 | 14 | not shown (evidence below 3) |
| contagion | 5 | 2 | 2 | 4 | 13 | not shown |
| dates | 1 | 3 | 3 | 3 | 10 | not shown |

Pass rule: evidence 3 or more and a total of 14 or more out of 20.

## What the numbers were

- **Aftershocks.** After a one-day fall of 3% or more (38 since 1990), days with a move of 2% or more were 3.1
  times as frequent as usual over the next 21 trading days, 2.2 times in days 22 to 63 and 1.3 times in days 64 to
  126. In 17 of 38 another fall of 3% or more came within 21 trading days.
- **Overlap.** With two or more of four stress states active (oil, long rates, credit spread, VIX; each a 20-day
  change in its top 5%), the median largest market fall over the next 63 trading days was -8.1%, against -3.6% with
  one and -2.6% with none. That is 17 sample days in 14 separate stretches; the evidence score uses the 14.
- **Contagion.** After a US shock day the Nikkei 225 fell on its next trading day 91% of the time (129 of 141),
  against 49% of all days. The other direction was weak (57% against 45%), and a shock in one US sector did not
  lead the market (down 40% of the time over the next 21 days, against 35% ordinarily).
- **Reverberation.** At 24 recoveries from a fall of 7% or more, the credit spread was still wider than at the
  peak in 54%: no effect by the rule. The VIX was higher in 75%.
- **Dates.** On 66 scheduled FOMC days the mean absolute market move was 0.64%, against 0.72% on other days. Six
  funding gaps: the market was down over the 10 days before in three and up in three.

## Limits

- Hindsight. Thresholds such as "top 5%" use the whole sample.
- Large falls and stress states cluster in a few crises, so the episodes are less independent than their count.
- The overlap states are price moves, not the event cards. A card can be open while no state is active.
- FOMC dates for 2021 to 2023 and late 2024 could not be read verbatim from the Fed's page and were left out.
- Equity data arrive about two months late; the present overlap count is as of the last FRED day at the last run.
