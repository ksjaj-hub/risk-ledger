# AFMX risk ledger

A public, dated record of market **risk states** and of the events behind them. The score is called AFMX. Started 2026-11-26.

Public page: https://ksjaj-hub.github.io/risk-ledger/

Every day a script reads a small set of public indicators, applies a published, versioned rule, and
commits the result here. Nothing in `records/`, `alerts/` or a published rule version is ever edited
or deleted afterwards. The point is simple: anyone can check what was said, and when.

**This is a description of risk conditions. It is not a forecast, not a recommendation to buy or sell
anything, and not investment advice.**

## What is here

| Path | Contents |
| --- | --- |
| `rules/` | The judging rules. Each version has an explanation (`v3.md`) and the file the script actually runs (`v3.json`). The newest version is in force; old versions stay, and each record names the version that judged it. `candidates/` holds proposals that are not in force. |
| `records/us/` | One file per day with new data: the state, the score, and each component's level. |
| `alerts/us/` | One file each time the state or a component level changes. |
| `events/` | Event risk cards with resolution conditions written in advance. |
| `backtest/` | Hindsight runs of each rule over past data. Kept apart from the ledger on purpose. |
| `docs/` | The public page (served by GitHub Pages). `data.json` is rebuilt from the files above. |
| `scripts/` | `collect.py` produces records. `verify.py` checks the chain. |

## How you can check that nothing was changed

1. **Git history.** Each record is its own commit, pushed by an automated job. See the commit log.
2. **Hash chain.** Each record contains the SHA-256 of the previous record file. Run `python scripts/verify.py`.
3. **Independent timestamps.** Where a `.ots` file sits next to a record, it is an
   [OpenTimestamps](https://opentimestamps.org) proof anchoring that file to the Bitcoin blockchain.
4. **Guard.** A check fails any change that modifies or removes an existing record, alert or rule version.

## Coverage

United States, whole market, to begin with. The layout (`records/<market>/`) is built to add markets
and individual stocks later.

## Data sources and limits

Inputs come from [FRED](https://fred.stlouisfed.org) (Federal Reserve Bank of St. Louis). Some series
are copyrighted by their owners (S&P Dow Jones Indices, ICE Data Indices, Cboe). Where the owner does
not allow republishing, the record shows only the level we derived, not the underlying number.
VIX data: Copyright Chicago Board Options Exchange, Inc.

Most inputs are published with a one-day lag, so a record reflects the latest available close, shown
in each component's `observation_date`.

## Rights

Public for verification, not open source. See [LICENSE.md](LICENSE.md).
