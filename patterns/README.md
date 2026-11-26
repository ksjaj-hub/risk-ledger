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

## Second look (2026-11-26)

Asked to look for more evidence, a second set of tests was fixed in `criteria2.json` before any of them was
computed, and run by `scripts/patterns2.py` into `second_look.json`. The evidence rule and the pass rule were not
changed. These tests were chosen with the first results in view; each entry in `criteria2.json` says what had been
seen. A score moves only on a period or a number the first round never touched.

| candidate | second-look test | result | evidence score |
|---|---|---|---|
| aftershocks | same definition, US 1926-1989 (untouched) | 4.05 times usual in days 1-21, 61 falls; 2.4 times still in days 64-126; both halves agree | stays 5 |
| aftershocks | same definition, Nikkei 225 since 1949 | 2.27 times usual, 118 falls; both halves agree | (other market) |
| overlap | looser threshold, denser sampling, each input left out | ratio 1.72 to 2.24 in every variant (first round 2.24); 7 to 24 separate stretches | stays 3 (robustness only) |
| contagion | same definition, 1949-1989 (untouched) | Nikkei down next day 68% (102 of 149) against 45%; halves 71% and 67%; reverse direction 46% against 44% | stays 5; the earlier period alone would score 3 |
| reverberation | realized volatility at recovery against the peak, US 1926-1989 (untouched) | still higher in 55% (17 of 31): no effect | stays 1 |
| reverberation | same, Nikkei 225 | 38% (8 of 21) | (other market) |
| dates | market closed up on FOMC days against other days | 42% against 55%; mean return 0.05% against 0.06% | 2 (was 1); total 11, still not shown |

What did not hold up:

- **Reverberation.** Three measures now fail: the credit spread (first round), realized volatility over 1926-1989,
  and the Nikkei. Only the VIX since 1990 shows it (18 of 24), and the same sample with realized volatility shows
  14 of 19, which is the same 1990-onward sample and not independent. The placebo on small dips swings from 31% to
  76% depending on one restriction, so the measure is fragile.
- **Reverberation, "does it matter".** Against the idea: over 1926 to 2026, recoveries with volatility still
  higher were followed by a smaller largest fall over the next 126 days (median -0.9%, 32 recoveries) than
  recoveries with volatility already back (-5.3%, 19 recoveries), in both halves. Small numbers; recorded, not used.
- **Dates.** The direction on FOMC days ran against the published drift (below), and the rule counts it as weak.

Published research read for context (it does not change a score):

- Federal Reserve Bank of San Francisco, Economic Letter 2002-32, "Stock Market Volatility" (J. Krainer): periods
  of high and of low volatility "tend to last for months". Agrees with aftershocks.
- Bank for International Settlements, Working Paper 702 (Hattori, Shim, Sugihara, 2018), 2007-2015: significant
  spillovers from US variance risk premiums to other markets, stronger after 2008. Agrees with the direction of
  contagion (US outward).
- Federal Reserve Bank of New York, Liberty Street Economics, 26 Nov 2018 (Lucca, Moench): stock returns of about
  half a percentage point in the 24 hours before scheduled FOMC announcements in 1994-2011; after 2011 only at
  meetings with a press conference.
- Federal Reserve Bank of St. Louis, On the Economy, 29 Sep 2025 (Neely and others), 2007-2020: FOMC announcements
  were followed within 30 minutes by a price jump with probability 0.58, the highest of 52 announcement types.

The last two describe effects inside the day. Daily closes, which are all this repository has, do not show them,
so date effects stay off the page. No published source was found for reverberation as defined here.

The page gained one sentence under each shown pattern giving the replication.
