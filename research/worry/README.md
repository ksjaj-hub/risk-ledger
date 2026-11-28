# Worry index: plan only

Written 2026-11-28. **Nothing is published yet and nothing here is a result.**

## What it would be

The share of people on the AFMX alerts waitlist (later: paying members) who asked to be warned about each sector and
each stock. It is the one number here that no one else can compute, because the input is AFMX's own.

## Why it is not live

- **There are no users.** On the day this was written the waitlist page was not merged. An index of nobody is nothing.
- **It measures AFMX's audience, not investors.** People who find a risk site are already worried. The number can be
  shown as "what people here watch", never as "what retail investors fear".
- **It is easy to game** while the list is small: one person with ten addresses moves it. There is no double opt-in
  and no bot check on the form yet.
- **It does not sell the product on its own.** Its use is as a reason to come back and as a line in the weekly note.

## Rules, fixed before any data

1. Nothing is published below **50 people** on the list.
2. An item picked by **fewer than 10 people** is never published. This is the promise in `docs/privacy.html`.
3. Only totals leave the answer sheet. The sheet is exported by the operator and never committed.
   `scripts/worry_index.py` reads it and writes `research/worry/index.json` with shares only.
4. A removal request takes the person out of the next count.
5. Before it is called an index, two things are checked on at least 26 weekly readings: that week-to-week change is
   not mostly noise from new sign-ups (the share among people who were already on the list is reported next to the
   total), and whether a rise in a sector's share came before or after the sector's AFMX score rose. If it only ever
   follows, it is described as an echo of the news.
6. No sentence may suggest that a high share means a sector will fall.

## What has to exist first

The waitlist page merged and working, a way to confirm addresses (double opt-in), and 50 people.
