# Shadow record: market breadth

**Not part of the rule. Not part of the ledger chain. Changes no state, score, record or alert.**

## Why

Research rounds 5 to 7 (`research/v4/README.md`) looked for something that says more than the v3 score on days when
the market is near its high. One measure came close: *breadth*, the share of industries trading below their own
200-day average. Added to v3 in hindsight it scored 0.662 against 0.625 for a 10% fall within 63 trading days
(2007-2026), and 0.590 against 0.515 on days near the high.

It was picked after seeing the data, so those numbers are flattered. The only clean test is the future. This folder
writes breadth down every day, before the months that follow are known.

## What is recorded

`breadth.csv`, one line per measure per day. Lines are added and never changed.

| Column | Meaning |
|---|---|
| `recorded_at_utc` | when the line was written |
| `as_of` | the market day the value is for |
| `measure` | `sector_funds`: the 11 Select Sector SPDR funds, from the issuer's NAV history files, written the next morning. `industries_49`: the 49 industries of the Kenneth R. French Data Library, written when that file is published, which is weeks after the day. |
| `breadth` | share of members below their own 200-day average |
| `level` | 0 to 3, cut at 0.245, 0.49 and 0.857 (fixed in round 5b from 1990-2006) |
| `dispersion_63d` | standard deviation across members of the 63-day return (round 7's secondary lead) |
| `members` | how many members had a 200-day history |

In hindsight the sector-fund measure carried most but not all of the 49-industry signal (round 6). It is the timely
one; the 49-industry one is the reference and is late. Its lateness is visible in the gap between the two date columns.

## How it will be judged (fixed now)

- Outcome: the market closes 10% or more below a day's close within the next 63 trading days (the research's O1).
- First look after 12 months of lines, again at 24 months. Not before: 10% falls are rare, and a few months cannot
  tell skill from luck.
- At each look: the share of days followed by the outcome at each `level`, for each measure, next to the same share
  by v3 state; and the AUROC of v3 plus the breadth level against v3 alone, on the recorded days only, with a
  block-bootstrap interval.
- Breadth is proposed for the rule only if, on recorded days, v3 plus breadth beats v3 with the 90% interval of the
  difference above zero, and the shares rise with the level. Otherwise it stays here or is stopped. Either way the
  result is published.
- With one or two falls in the window the interval will be wide and the honest answer may be "cannot tell yet".
