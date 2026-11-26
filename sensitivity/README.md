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

`aids/reading.json` says which shock each card resembles (`risk_factors`, AFMX judgment) and which sectors a card
is literally about (`about`). `scripts/build_site.py` then gives each card and sector one of:

| level | meaning | points |
|---|---|---|
| direct | the card is about companies in the sector | 3 |
| strong / moderate | the sector lagged the market on such shock days | 3 / 2 |
| unconfirmed | AFMX judgment only; no fitting data, or the data was weak or mixed | 1 |
| whole market | the card reaches the whole market and nothing more specific is known | 1 |

Sectors that historically did better than the market on such days are shown on the card but add no points.
Sector score = points over open cards / (3 x number of open cards) x 100.

## Limits

- Same-day association, not cause. Many shock days coincide with each other.
- Hindsight. The 5% cut-offs use the whole sample.
- A past shock of a similar kind is not the event on the card. Choosing which shock a card resembles is a judgment.
- Tariff, China-demand and euro-area cards have no fitting series here; their sector links stay `unconfirmed`.
- The score counts open cards. It grows when AFMX opens more cards about a sector, so it also reflects coverage.

Rerun: Actions, "sector sensitivity", Run workflow. Then `python3 scripts/build_site.py`.
