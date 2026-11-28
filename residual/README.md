# Residual risk index

One number for how much unresolved event risk is on AFMX's open cards.

**Read the limits first.** This is a sum of AFMX's own judgment. It is not a measurement of the market, it is not a
forecast of prices, and its relation to prices has not been tested. It is published because the cards already carry
odds that are scored in public, and a reader should be able to see what those odds add up to.

## Formula (version 1, fixed on 2026-11-28)

For every card that is not resolved or withdrawn:

- **stage** = 1 - p_resolved + p_worsened, from the card's newest forecast. This is the expected stage at the forecast's
  deadline when resolved counts 0, still open 1 and worsened 2. A card already marked worsened counts 2; a card with no
  forecast counts 1.
- **reach** = 1 if the card is marked market-wide in `aids/reading.json`, otherwise the number of sectors it names
  divided by 11.

**Index = sum of reach x stage.** The unit is "market-wide open risks": 5 reads as five risks that each touch the whole
market and are expected to stay open. There is no 0 to 100 scale and there are no bands, because there is no history to
set them from.

`preregistration.json` holds the full wording. It was committed before the index was computed for the first time and
is not edited (the append-only guard checks this). A different formula is version 2 in a new file.

## Limits

- Every input is AFMX's judgment. The index moves only when AFMX edits a card.
- 12 cards. Three market-wide cards carry more than half of the index.
- The number of cards is an editorial choice. Opening more cards raises the index even if the world did not change.
- Reach is a count of sectors, not a size of damage. On 2026-11-27 private credit had the second-highest stage (1.43)
  and a 2% share, because it names one sector. With every reach set equal the total is 13.24 and the order changes;
  that total is published next to the index (`equal_reach`).
- The Japan card is marked market-wide in `aids/reading.json`, which gives a risk that starts outside the US the largest
  share. That marking predates this index and was not changed for it.
- Forecast deadlines run from 2026-12-12 to 2027-06-30, so stages are not over one horizon.
- Cards share causes, so shared causes are counted more than once.
- History starts on 2026-11-26. Nothing is back-filled.

## Market test

Not run. The plan is fixed in `preregistration.json`: one look, no earlier than 2026-11-26 plus one year, asking
whether a four-week rise in the index was followed by a higher AFMX backdrop score. If it fails or cannot be run, the
page says so and the index stays labeled as a summary of open cards.

## Files

- `python3 scripts/residual.py` writes `index.json` (latest value, each card's share, history). Run it after a card
  changes status or gets a new forecast, before `build_site.py`.
- `python3 scripts/residual.py --selftest` checks the arithmetic.
- History is recomputed from the card files for each day a card was opened, changed status or got a forecast. It uses
  today's reach for every day; a change of reach is listed here with its date. None so far.
