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

Scripts: `scripts/research_v4.py`, `scripts/research_v4b.py` (workflow `rule research`).

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

## What this means for the rule

1. v3 is not improved by re-weighting. A v4 would need a new kind of information, not new arithmetic.
2. The state is a description of how stressed the market is now. It is not an early warning, and the
   record should say so: Calm has been followed by sharp falls about one time in ten since 2007.
3. Two of v3's inputs (ICE high-yield spread, S&P 500 via FRED) cannot be tested over more than three
   and ten years. Stand-ins were used here. A future version should name inputs it can be tested on.
4. Not tested, and where new information might come from: option-implied measures beyond the VIX level,
   funding-market spreads, and firm-level measures (CoVaR, SRISK), none of which are available from the
   sources this repository can republish.
