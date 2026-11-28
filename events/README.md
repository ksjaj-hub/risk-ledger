# Event risk cards

One file per event. Each card says what happened, how it reaches markets, and, most importantly,
**what would have to be true for the risk to count as resolved, written down before the outcome is known**.

- `status` is one of `open`, `easing`, `resolved`, `worsened`.
- Why a risk gets a card at all, and what closes one, is in `selection/criteria.json`. It adds one way to close:
  `withdrawn`, for a card whose founding fact is taken back or never confirmed. No card has used it yet.
- The original `resolution_conditions` are never erased. If they need to change, the first wording moves to
  `conditions_as_first_written` with the date and the reason, `history` quotes what was replaced, and a new forecast
  is added for the new wording. Forecasts written earlier stay scored on the first wording.
- `relief_headlines_that_do_not_resolve_it` lists good news that does not meet the conditions.
- Every status change is a dated entry appended to `history`. Git history shows when each line was written.
- Facts are limited to what the listed sources state. Where sources disagree, the card says so.
- `numeric_criteria` says how each condition is counted in numbers (measure, threshold, latest reading, state). It is
  versioned and dated, and it never replaces `resolution_conditions`: if the two could be read differently, the
  original wording decides. A new way of counting is a new version with a history line, not an edit.
- `counter_view` is one short statement of why the card's reading may be wrong.

## When a card is added or its status changes

1. Add its Korean reading aid to `i18n/events.ko.json`.
2. Add its related tickers to `aids/reading.json` (`exposure`), and any deadline stated in its sources to `dates`.
3. Review `featured` in `aids/reading.json`: up to three cards that matter most this week.
4. Add or update the card's line in `selection/criteria.json` and run `python3 scripts/selection_check.py`
   (see `selection/README.md`). An event that was looked at and not carded gets a line under `left_out` there.
5. Run `python3 scripts/residual.py` (the residual risk index, `residual/README.md`), then `python3 scripts/build_site.py` and commit everything it changes under `docs/` (`data.json`, `ko.json`, `cards/`, `tabs/`) with the change.

For a new card also add `risk_factors` (which measured shock it resembles, may be empty) and `about` (sectors it is
literally about) in `aids/reading.json`. Evidence levels and sector scores are then computed by `build_site.py`
from `sensitivity/sectors.json`; see `sensitivity/README.md`.
