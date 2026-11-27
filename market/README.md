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

Rerun: Actions, "market check", Run workflow.
