# Sector sensitivity (reading aid, hindsight)

`sectors.json` answers one narrow question: on past days when a given kind of shock was large, which US equity
sectors did worse or better than the market on the same day?

It is used to say how strong the evidence is behind each link between an event card and a sector on the public
page, and to compute the sector score there. It is **not** part of the ledger, not a forecast and not a
recommendation.

## Method

- Sector returns: Kenneth R. French Data Library, 49 industry portfolios, daily, value weighted. A sector is the
  simple average of the industries listed under `meta.sectors`. These are not GICS sectors and not ETFs.
- Market return: Fama/French daily market return (Mkt-RF plus RF).
- Shocks: daily moves in FRED series (WTI oil, 2- and 10-year Treasury yields, Moody's Baa minus 10-year spread,
  VIX, yen per dollar). A shock day is a day in the worst 5% for that series since 1990.
- For each shock and sector: mean return in excess of the market on shock days, a Welch t statistic against all
  other days, and the same mean in the first and second half of the sample.
- Evidence: `strong` when |t| >= 3 and the sign is the same in both halves, `moderate` when |t| >= 2 and the sign
  is the same, otherwise `weak`.

## How the page uses it

`mapping.json` fixes in advance, in public, which shocks each card is read against (`factors`), which past case
applies (`cases`), which sectors a card is literally about (`about`) and which cards share one cause (`group`).
Changes get a new version and a changelog line. `scripts/build_site.py` then gives each card and sector one of:

| level | meaning | points |
|---|---|---|
| direct | the card is about companies in the sector | 3 |
| strong / moderate | the sector lagged the market on such shock days | 3 / 2 |
| case | no shock series says anything, but the sector ended 3 points or more behind the market in the 126 trading days after the start of a past case in `cases.json` (one case only) | 2 |
| unconfirmed | AFMX judgment only; the data was weak or mixed | 1 |
| whole market | the card reaches the whole market and nothing more specific is known | 1 |

Sectors that historically did better than the market are shown on the card but add no points.

The page shows the score only as a band (high from 67, moderate from 34, otherwise low) with the main reasons, until the public grading supports showing a number.

Sector score (method 2): for each cause group take the highest points among its cards, keep the five largest
groups, divide by 15, times 100. Opening more cards about one cause therefore does not raise the score.

Public grading of the score is described in `sector_scores/README.md`.

## Limits

- Same-day association, not cause. Many shock days coincide with each other.
- Hindsight. The 5% cut-offs use the whole sample.
- A currency or rate shock is a stand-in, not the event on the card. A falling euro is not the same as ECB rate
  rises; a weak yuan is not the same as weak Chinese demand. Freight indices and German yields are not available
  daily from the sources this repository can use.
- Past cases are single episodes. Only start dates that could be quoted from a source are used. A 2011 euro-area
  case was left out because no start date could be verified and it is a poor match for an inflation card.
- The score measures exposure to open risks. Whether that predicts anything is what the public grading will show.

Rerun: Actions, "sector sensitivity", Run workflow. Then `python3 scripts/build_site.py`.
