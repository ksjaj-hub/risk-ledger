# Backtests

Files here are **hindsight**. They show what a published rule would have said on past days.
They are kept apart from `records/` on purpose: the ledger only counts what was written down
before the outcome was known.

Read them with these limits in mind:

- The rule was written after these events. Its thresholds may fit the past better than the future.
- Inputs are today's revised figures, not what was available on the day (NFCI in particular is revised).
- A component is left out on days when its source has no data yet, and the score is scaled to the
  components that exist. `components_used` in `daily.csv` says how many were used.
- Only levels are published. Licensed raw values (S&P 500, ICE high-yield spread) are not.

Run: `python scripts/backtest.py` (needs `FRED_API_KEY`), or the `backtest` workflow.
