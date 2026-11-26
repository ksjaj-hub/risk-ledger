# Research for a possible rule v4 (2026-11-26)

**Outcome: no change. Rule v3 stays in force.** Nothing tested here cleared the bar that was written
down before the numbers were computed.

Everything in this folder is hindsight on revised data. It describes past ranges and is not a forecast.

| File | What it is |
|---|---|
| `literature.md` | What was read first (central-bank and working-paper sources) and which test each source led to |
| `preregistration.json` | Round 1: seven candidates, the outcomes, the train/test split and the bar, committed before computing |
| `results.json`, `daily.csv` | Round 1 results |
| `preregistration2.json` | Round 2, written after round 1 was read: slow indicators and a long-history replication |
| `results2.json` | Round 2 results |
| `preregistration3.json` | Round 3: a search over 9,420 scores, with the correction for the size of the search fixed in advance |
| `results3.json`, `candidates3.csv` | Round 3 results, and every candidate with its train and test figures |

Scripts: `scripts/research_v4.py`, `scripts/research_v4b.py`, `scripts/research_v4c.py` (workflow `rule research` runs the last one).

## Round 1: does a better way of combining the inputs beat v3?

Set on 1990-2006, scored once on 2007-01-03 to 2026-07-01 (4,904 days). Outcome O1: the market closes
10% or more below today's close within 63 trading days (16.2% of test days). AUROC: 0.5 is chance.

| Score | Train AUROC | Test AUROC | Test difference to v3, 90% interval |
|---|---|---|---|
| v3 on long series (baseline) | 0.835 | 0.625 | |
| C1 yield curve left out | 0.810 | 0.660 | -0.001 to 0.068 |
| C2 percentiles, equal weights | 0.836 | 0.639 | -0.027 to 0.053 |
| C3 principal-component weights | 0.828 | 0.658 | -0.014 to 0.078 |
| C4 correlation weighted (CISS style) | 0.843 | 0.600 | -0.068 to 0.014 |
| C5 plus realized volatility | 0.832 | 0.644 | -0.021 to 0.058 |
| C6 plus excess bond premium (**chosen on train**) | 0.852 | 0.637 | -0.039 to 0.059 |
| C7 without NFCI | 0.838 | 0.623 | -0.051 to 0.045 |

- The chosen candidate gained 0.012 against a bar of 0.02 with an interval above zero, and was worse on
  the two secondary outcomes. **Bar not met.**
- No way of weighting was reliably better than v3's hand-set levels. First-component weights came out
  near equal (0.18 to 0.26) except the yield curve (0.07), as the Kansas City Fed's coefficients suggest.
- Every score separated days far less well after 2007 than before. Under v3, no Calm day in 1990-2006
  was followed by a 10% fall within 63 trading days; in 2007-2026, 10.3% of Calm days were
  (2018, 2020 and 2025 began from quiet readings).
- In 1986-1989, with the VXO standing in for the VIX, no score beat chance: October 1987 came out of
  low readings.
- The yield curve: leaving it out helped after 2007 and hurt before 2007, and in both periods lowered
  the score's link to recessions six to eighteen months ahead (0.668 to 0.580, 0.813 to 0.719). Mixed
  evidence, so it stays.

What the five v3 states were followed by in the test period (largest fall over the next 63 trading days):

| State | Days | Share followed by a 10% fall | Median largest fall | Worst 5% of days, at least |
|---|---|---|---|---|
| Calm | 1,579 | 10.3% | -2.6% | -13.8% |
| Guarded | 1,346 | 14.8% | -3.3% | -15.7% |
| Watch | 821 | 16.3% | -2.2% | -14.6% |
| Elevated | 841 | 21.8% | -4.8% | -26.1% |
| Stress | 317 | 36.6% | -3.8% | -28.4% |

The ladder rises, weakly across the lower three states. The clearest difference is in the tail: the bad
end of the range roughly doubles from Watch to Elevated.

## Round 2: can a slow indicator tell calm days apart, and does the idea hold on untouched data?

Outcome O5: the market closes 20% or more below today's close within 504 trading days. Bar: AUROC of
0.60 or more in an untouched period before 1990, in 1990-2006 and after 2007.

| Indicator | Untouched period | 1990-2006 | 2007 onward | Bar |
|---|---|---|---|---|
| Yield curve (10y minus 3m) | 0.367 (1982-89) | 0.658 | 0.655 | not met |
| NFCI nonfinancial leverage | 0.543 (1971-89) | 0.801 | 0.835 | not met |
| Unusually low volatility | 0.510 (1937-89) | 0.130 | 0.569 | not met |
| Excess bond premium | 0.462 (1973-89) | 0.836 | 0.495 | not met |

- **No slow-warning line is proposed.** Each indicator that looked good after 1990 failed on the years
  before 1990. With two-year outcomes each period holds only a handful of separate events, and the
  intervals are very wide.
- The yield curve does what the literature says it does: against recessions six to eighteen months
  ahead its AUROC was 0.977, 0.888 and 0.669 in the three periods. It is a recession indicator, not a
  market-fall indicator.
- Among days at Calm or Guarded since 1990, the yield curve separated days later followed by a 20% fall
  (0.873, interval 0.839 to 0.968). This was a secondary check, it has no untouched period that agrees,
  and it is recorded here only so it is not rediscovered and oversold.
- **Replication of the daily state on 1927-1985**, using prices alone (drawdown and 21-day realized
  volatility, cutpoints from 1990-2006): AUROC on O1 0.752 (interval 0.702 to 0.796; 0.781 and 0.661 in
  the two halves). The share of days followed by a 10% fall rose by fifths of the score:
  2.6%, 8.7%, 9.6%, 19.1%, 35.4%. The idea behind the state holds on 58 years that no version of the
  rule had seen.
- Prices alone did about as well as v3: 0.797 against 0.835 in 1990-2006, 0.661 against 0.625 after
  2007. The VIX and NFCI add little that the market's own fall and volatility do not already say.

## Round 3: a search over 9,420 scores

Asked for by the owner: review the score against thousands of alternatives. Every subset of one to four
of 12 components (793 subsets), two transforms, three ways of combining, with and without smoothing:
9,420 candidates, all scored on the same days. Train 1990-04 to 2006 (4,224 days), test 2007-01 to
2026-06 (4,903 days). v3 on the long series: 0.842 train, 0.625 test.

**Outcome: no change. Nothing in the search is distinguishable from luck.**

| Question | Answer |
|---|---|
| The candidate that was best on 1990-2006 (AUROC 0.892) | 0.607 on the test period, 0.018 *below* v3, ranked 7,513th of 9,420 |
| Does doing well on 1990-2006 say anything about 2007-2026? | No. Rank correlation across all candidates: -0.03 |
| The best candidate on the test period | 0.733, a gain of 0.109 over v3. It ranked 4,858th on the train period |
| What a search this size produces by luck alone | A best gain of 0.097 (median), 0.201 at the 95th percentile |
| White's Reality Check | p = 0.42 (studentized: 0.19). No evidence that any candidate is better than v3 |

- 68% of candidates were above v3 on the test period and 10% on the train period; 4.9% on both. v3 is an
  ordinary member of this family, not a tuned one: unremarkable after 2007, in the top tenth before.
  Which members did better changed completely between the two periods.
- The only patterns that held in both periods: a plain average did better than taking the maximum
  (0.797 and 0.655 against 0.767 and 0.619), and more components did slightly better than fewer. v3 is
  already a plain average of five.
- Everything else flipped. Candidates with the yield curve or the excess bond premium were better
  before 2007 and no better or worse after; candidates with momentum, the credit jump or the leverage
  subindex were the reverse.
- Prices-only family on 1927-1985 (148 candidates, 15,774 days): the best gained 0.003 over round 2's
  simple score (0.755 against 0.752), Reality Check p = 0.99. Within this family the ranking was stable
  across periods (rank correlation 0.81), and the simplest member was already at the top.
- Confirmation days (v3, test period): stepping down after 1 / 3 / 5 / 10 / 21 days gives 27.0 / 15.3 /
  12.5 / 9.9 / 6.7 state changes a year, and 19.6% / 22.0% / 23.6% / 26.6% / 31.8% of days at Elevated
  or above. A trade of flicker against lingering alarms, with no free point on it. 5 stays.

What a careless search would have reported: "a new score beats v3 by 0.11 AUROC out of sample". That
candidate exists in `candidates3.csv`. The correction is what says it is noise.

## What this means for the rule

1. v3 is not improved by re-weighting, nor by any of 9,420 recombinations of 12 inputs. A v4 would need a new kind of information, not new arithmetic.
2. The state is a description of how stressed the market is now. It is not an early warning, and the
   record should say so: Calm has been followed by sharp falls about one time in ten since 2007.
3. Two of v3's inputs (ICE high-yield spread, S&P 500 via FRED) cannot be tested over more than three
   and ten years. Stand-ins were used here. A future version should name inputs it can be tested on.
4. Not tested, and where new information might come from: option-implied measures beyond the VIX level,
   funding-market spreads, and firm-level measures (CoVaR, SRISK), none of which are available from the
   sources this repository can republish.

## Round 4: AFMX scored against widely used indicators

Asked by the owner: score AFMX against the indicators people use most and find where it falls short. Fixed beforehand in `preregistration4.json`; numbers in `results4.json`; script `scripts/research_v4d.py`. Hindsight, not a forecast.

Sample: 2007-12-04 to 2026-07-01, 4672 days on which all 14 have a value. A 10% fall followed 16.3% of days.

| Rank | Indicator | Overall (0-100) | M1 10% in 63d | M2 5% in 21d | M3 near highs | M5 falls after its calmest third | M6 falls after its top fifth | M7 flips/yr | Corr. with AFMX | M1 minus AFMX, 90% |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | below_200dma | 87.2 | 0.714 | 0.657 | 0.632 | 8.4% | 34.4% | 6.6 | 0.50 | +0.009 to +0.180 |
| 2 | drawdown | 82.1 | 0.667 | 0.663 | 0.587 | 8.4% | 28.0% | 5.4 | 0.74 | -0.006 to +0.103 |
| 3 | ofr_fsi | 79.5 | 0.648 | 0.644 | 0.565 | 8.3% | 27.3% | 3.9 | 0.73 | -0.045 to +0.093 |
| 4 | ciss_us | 75.6 | 0.651 | 0.636 | 0.609 | 8.3% | 26.3% | 3.6 | 0.68 | -0.039 to +0.089 |
| 5 | vix | 64.1 | 0.631 | 0.663 | 0.559 | 8.5% | 20.8% | 10.1 | 0.78 | -0.047 to +0.065 |
| 6 | realized_vol | 64.1 | 0.645 | 0.662 | 0.553 | 9.0% | 27.6% | 4.9 | 0.70 | -0.040 to +0.082 |
| 7 | afmx | 56.4 | 0.625 | 0.660 | 0.507 | 10.9% | 28.6% | 3.6 | 1.00 |  |
| 8 | vix_term | 47.4 | 0.627 | 0.648 | 0.528 | 11.4% | 26.1% | 19.7 | 0.53 | -0.073 to +0.081 |
| 9 | stlfsi | 41.0 | 0.612 | 0.590 | 0.550 | 10.5% | 26.5% | 3.1 | 0.48 | -0.110 to +0.069 |
| 10 | nfci | 41.0 | 0.611 | 0.641 | 0.525 | 11.7% | 25.7% | 0.7 | 0.80 | -0.067 to +0.032 |
| 11 | anfci | 32.1 | 0.604 | 0.630 | 0.515 | 11.6% | 26.3% | 0.9 | 0.75 | -0.082 to +0.031 |
| 12 | credit_spread | 16.7 | 0.572 | 0.552 | 0.522 | 16.3% | 25.9% | 2.6 | 0.19 | -0.171 to +0.069 |
| 13 | kcfsi | 14.1 | 0.562 | 0.584 | 0.450 | 15.4% | 23.5% | 0.9 | 0.63 | -0.141 to +0.004 |
| 14 | yield_curve | 0.0 | 0.392 | 0.447 | 0.413 | 26.1% | 7.8% | 2.7 | 0.20 | -0.404 to -0.063 |

What it shows:

- AFMX is 7th of 14, in the middle. Only one indicator is ahead of it by more than chance on M1: the market's distance below its 200-day average. AFMX is ahead of only one by more than chance: the yield curve.
- **Near market highs AFMX says nothing (M3 0.507, 12th of 14).** That is the question a reader most wants answered. No indicator's lead on M3 is outside chance, but AFMX is at the coin-flip line.
- **Its Calm is less clean.** 10.9% of AFMX's calmest third of days were followed by a 10% fall; the best indicators have 8.3%.
- **It repeats what is free.** Rank correlation 0.78 with VIX and 0.80 with NFCI.
- **One of its five inputs points the wrong way in this period.** The yield curve alone scores 0.39, below a coin flip.
- **It lost the most between periods.** On 1990-2006 AFMX led everything (0.835); after 2007 it is 0.625. VIX went 0.752 to 0.638, the 200-day rule 0.744 to 0.715.
- Where AFMX is good: its top fifth is followed by a 10% fall 28.6% of the time, second best; it changes little (3.6 flips a year); on the 21-day horizon it is level with the best.

Caution, same as round 3: the 200-day rule's lead is a 2007-2026 result. On 1990-2006 it was behind AFMX (0.744 against 0.835, and 0.49 against 0.89 near highs). It is a lead worth a pre-registered test, not a reason to change the rule.

Not testable from primary sources: CNN Fear & Greed, MOVE, SKEW. The Fed-bank indexes and CISS are re-estimated over time, so their numbers here are flattered. The `episodes_trading_days_from_peak` block in the results file was an extra outside the pre-registration; its 2020 and 2025 windows pick the wrong peak and it is not used.

## Round 5: five directions for raising the score

The owner chose to follow up round 4. Fixed beforehand in `preregistration5.json` (and `preregistration5b.json` for the follow-up); numbers in `results5.json` and `results5b.json`; script `scripts/research_v4e.py`. Hindsight, not a forecast.

**Outcome: nothing clears the pre-registered bar, so there is no v4. One lead is worth recording live: industry breadth.**

### A. Trend and the yield curve

| Candidate | 1990-2006 | 2007 on | minus v3, 90% | Near highs, 2007 on | Fails on |
|---|---|---|---|---|---|
| v3 | 0.835 | 0.625 |  | 0.515 |  |
| A1 no yield curve | 0.810 | 0.660 | -0.001 to +0.068 | 0.568 | test_gain_at_least_0.02_and_interval_above_zero, train_not_more_than_0.02_below, ladder_rises |
| A2 plus trend | 0.838 | 0.636 | +0.003 to +0.019 | 0.521 | test_gain_at_least_0.02_and_interval_above_zero, clean_check_1927_1985 |
| A3 no curve, plus trend | 0.815 | 0.666 | +0.003 to +0.077 | 0.572 | ladder_rises, clean_check_1927_1985 |

- Trend fails the clean check. On 1927-1985, which no earlier round had used for a 200-day measure, adding the trend level to the drawdown level made it worse (0.709 against 0.717, difference -0.018 to -0.001). The 200-day rule's lead in round 4 was a 2007-2026 result.
- The yield curve: for a recession 6-18 months later its AUROC is 0.888 and 0.654; for a 10% fall within 63 days it is 0.619 and 0.388. Taking it out of the score helps after 2007 and hurts before, as in rounds 1 and 3. It stays in the score; showing it also as a separate recession reading is a presentation choice.

### B. Information near market highs

Days within 5% of the 252-day high; 11.1% of them were followed by a 10% fall after 2007. v3 scores 0.515 there. Thirteen candidates, each with its direction fixed beforehand.

| Candidate | From | 1990-2006 | 2007 on | 90% interval | Lower end widened for 13 tries | Earlier period (to 1985) |
|---|---|---|---|---|---|---|
| breadth | 1927 | 0.784 | 0.679 | 0.535 to 0.811 | 0.464 | 0.589 |
| dispersion | 1927 | 0.720 | 0.603 | 0.489 to 0.716 | 0.430 | 0.579 |
| margin_growth | 1953 | 0.610 | 0.591 | 0.457 to 0.741 | 0.391 | 0.541 |
| rate_rise | 1976 | 0.606 | 0.564 | 0.434 to 0.701 | 0.370 | 0.821 |
| valuation | 1951 | 0.577 | 0.549 | 0.402 to 0.692 | 0.328 | 0.437 |
| run_up | 1927 | 0.516 | 0.528 | 0.373 to 0.679 | 0.286 | 0.545 |
| vix_term | 2007 |  | 0.528 | 0.437 to 0.610 | 0.387 |  |
| skew | 1990 | 0.588 | 0.510 | 0.374 to 0.647 | 0.302 |  |
| correlation | 1927 | 0.463 | 0.509 | 0.347 to 0.661 | 0.295 | 0.514 |
| oil_rise | 1986 | 0.329 | 0.478 | 0.364 to 0.608 | 0.309 |  |
| tight_credit | 1986 | 0.484 | 0.472 | 0.328 to 0.638 | 0.258 |  |
| low_vol | 1990 | 0.244 | 0.417 | 0.310 to 0.523 | 0.269 |  |
| policy_rate_rise | 1955 | 0.461 | 0.349 | 0.234 to 0.468 | 0.186 | 0.762 |

- None passes: the bar needed 0.58 on both periods and a widened lower end above 0.50.
- Breadth (share of the 49 industries below their own 200-day average), industry dispersion and margin-loan growth are above 0.58 on both periods; they fail only on the widened interval. Breadth is the strongest of the three and the only one whose plain 90% interval stays above 0.50.
- Options skew, low volatility, tight credit spreads, a strong run-up, oil and policy-rate rises do not separate the days. Rate rises worked before 1985 and not since.

### C. Verifiable inputs

| Candidate | 1990-2006 | 2007 on | minus v3, 90% | Acceptable swap |
|---|---|---|---|---|
| C1 credit from Baa spread | 0.838 | 0.627 | -0.046 to +0.050 | yes |
| C2 and NFCI replaced by CISS | 0.808 | 0.633 | -0.043 to +0.058 | no |
| C3 Baa spread, CISS as a sixth | 0.817 | 0.639 | -0.033 to +0.059 | no |

- Reading credit stress from the Baa spread (downloadable from 1986) costs nothing in accuracy and makes the rule checkable on the past. It is not an improvement, and its state ladder is not clean (Watch 18.7%, Elevated 17.8%).
- Replacing NFCI with CISS loses too much on 1990-2006.

### D. How long each state has lasted (v3, 1990 on, trading days)

| State | Spells | Median | Upper quartile | Longest | Ended by moving up | Share of days |
|---|---|---|---|---|---|---|
| Calm | 85 | 16 | 49 | 306 (from 1994-12-21) | 100% | 36% |
| Guarded | 142 | 10 | 19 | 132 (from 2006-08-16) | 39% | 27% |
| Watch | 94 | 9 | 19 | 102 (from 2001-11-19) | 47% | 15% |
| Elevated | 74 | 11 | 29 | 77 (from 2023-01-11) | 30% | 15% |
| Stress | 24 | 8 | 22 | 225 (from 2008-09-15) | 0% | 6% |

### E. Follow-up on breadth (exploratory, chosen after seeing B)

| Candidate | 1990-2006 | 2007 on | minus v3, 90% | Near highs, 2007 on | minus v3, 90% | State changes | Clears part A bar |
|---|---|---|---|---|---|---|---|
| E1 v3 plus breadth | 0.818 | 0.662 | +0.015 to +0.065 | 0.590 | +0.018 to +0.134 | 267 (v3 244) | yes |
| E2 and no yield curve | 0.798 | 0.692 | +0.023 to +0.115 | 0.644 | +0.010 to +0.235 | 293 (v3 244) | no |

- v3 plus breadth clears every item of the part A bar, and its state ladder is clean (Calm 9.4%, Guarded 14.0%, Watch 20.5%, Elevated 22.9%, Stress 38.5%).
- On 1927-1985, adding the breadth level to the drawdown level does nothing on all days (-0.016 to +0.019) and helps on near-high days (0.57 against 0.5, +0.005 to +0.137).
- By the reading fixed beforehand this is **worth recording, not a rule change**: breadth was picked after seeing the data, so these numbers are flattered. The honest next step is to record it live next to the rule and judge it on days that have not happened yet.
- Open practical point: the 49-industry file is published with a lag of weeks. A live record needs a daily source for industry or sector prices.

## Round 6: can breadth be collected every day?

Fixed beforehand in `preregistration6.json`; numbers in `results6.json` (part F of `scripts/research_v4e.py`).

The 49-industry file is published weeks late. The 11 Select Sector SPDR funds publish a NAV history every day (issuer files, reachable from GitHub Actions; history from 2003-12, nine funds with a 200-day history from 2004-09).

| Check | Needed | Got |
|---|---|---|
| Rank correlation with the 49-industry breadth | 0.80 | 0.874 |
| Near-high AUROC, 2007 on | 0.58 | 0.610 (49 industries on the same days: 0.679) |
| v3 plus the proxy, gain over v3 | 0.02 | +0.013 (-0.006 to +0.038) |

Two of three. Eleven sectors carry most of the signal but less of it: on all days the proxy scores 0.675 against 0.723. By the reading fixed beforehand the 49-industry measure is the one to record, when its file comes out, and that record is late. The sector-fund measure can be recorded daily beside it as the weaker, timely version.

## Round 7: a second look at the near misses (exploratory)

Asked by the owner. Fixed beforehand in `preregistration7.json`; numbers in `results7.json` (part G). Every candidate was picked because it came close in round 5, so these numbers are flattered.

For reference, v3 scores 0.835 / 0.625 and v3 plus breadth (E1) 0.818 / 0.662, near highs 0.590.

| Candidate | 1990-2006 | 2007 on | Near highs | minus v3, 90% | minus E1, 90% | Fails on |
|---|---|---|---|---|---|---|
| G1 v3 + dispersion | 0.837 | 0.645 | 0.553 | -0.003 to +0.046 | -0.047 to +0.014 | test_gain_at_least_0.02_and_interval_above_zero, ladder_rises |
| G2 v3 + margin-loan growth | 0.820 | 0.651 | 0.555 | -0.007 to +0.067 | -0.058 to +0.035 | test_gain_at_least_0.02_and_interval_above_zero |
| G3 v3 + 2-year yield rise | 0.816 | 0.631 | 0.506 | -0.020 to +0.032 | -0.058 to -0.005 | test_gain_at_least_0.02_and_interval_above_zero |
| G4 v3 + breadth + dispersion | 0.825 | 0.675 | 0.608 | +0.019 to +0.084 | -0.006 to +0.031 |  |
| G5 v3 + breadth + margin-loan growth | 0.805 | 0.680 | 0.620 | +0.020 to +0.096 | -0.011 to +0.049 | train_not_more_than_0.02_below, ladder_rises |
| G6 v3 + breadth, credit from Baa spread | 0.826 | 0.656 | 0.576 | -0.013 to +0.075 | -0.043 to +0.026 | test_gain_at_least_0.02_and_interval_above_zero, ladder_rises |
| G7 v3 + breadth + trend | 0.821 | 0.666 | 0.592 | +0.016 to +0.070 | -0.001 to +0.009 | ladder_rises |

- Alone, none of dispersion, margin-loan growth or the rate rise clears the bar. Each is weaker than breadth alone.
- On top of breadth, nothing is distinguishable from breadth alone. Dispersion comes nearest: -0.006 to +0.031 after 2007 and +0.000 to +0.043 on 1927-1985. It is computed from the same file as breadth, so it costs nothing to record with it.
- Trend adds nothing to breadth (-0.008 to -0.000 on 1927-1985).
- Reading credit stress from the Baa spread leaves v3 plus breadth where it was (within 0.01 on both periods), so the verifiable input can be used in whatever is recorded.
- Rank correlation with breadth since 1990: dispersion 0.33, margin-loan growth 0.089, rate rise -0.063.

**Where this leaves things:** breadth is the one lead. Record it live outside the rule (49 industries when published, sector funds daily, dispersion alongside) and judge it on days that have not happened yet.
