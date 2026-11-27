# Market check (reading aid)

`check.json` sets each open event card against market prices and says whether those prices show the risk the card
describes. It is **not** part of the ledger, not a forecast and not a recommendation.

- The readings for each card and the rule for "shows" are fixed in `config.json` before the first run
  (version 1, 2026-11-27). They are not tuned afterwards; a change is a new version.
- "Shows" means one of: the latest value is in the top fifth of its own last five years; a spread is above zero;
  or the matching measure in the latest AFMX record is at 2 of 3 steps or more.
- A card whose prices do not show the risk is marked as such on the page. That is information, not a correction:
  the card may be early, or wrong.
- Five cards are not checked, because no price in our sources isolates them or because the prices are not ours to
  republish. The page says so.

## Sources and rights

- Fetched here: Brent spot (U.S. Energy Information Administration), Treasury yields, the federal funds target
  range and exchange rates (Board of Governors of the Federal Reserve System, H.15 and H.10), and the 5-year
  breakeven rate computed by the Federal Reserve Bank of St. Louis from those yields. These are works of US
  government bodies or derived from them.
- Not fetched here: series owned by third parties (Cboe, ICE Data Indices, S&P Dow Jones Indices, Nasdaq). The
  FRED API terms say such data needs the owner's permission for anything beyond personal use. For those the check
  reuses only the step already published in the AFMX record.
- This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.
  Terms: https://fred.stlouisfed.org/docs/api/terms_of_use.html

## When it runs

The workflow `market check` runs by itself three times each weekday and writes only when a reading has changed:

- 03:07 UTC (12:07 in Korea) and 15:07 UTC (00:07 in Korea), with the event checks.
- 22:10 UTC, after the Federal Reserve posts its daily interest rate release (H.15) at 4:15 p.m. Eastern.
  On the day after a jobs, inflation or Fed release this is the first run that can see the market's response.

The official sources publish a day's yields and exchange rates on the next business day or later, so a reading is
never from the same hour as a release. Each reading on the page carries the date it is for, and the note under
them gives the time the values were last read. To run it by hand: Actions, "market check", Run workflow.
