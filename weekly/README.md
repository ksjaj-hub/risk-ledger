# Weekly note

One JSON file per issue (`N.json`), built into `docs/weekly/N.html` (English, with a language switch) and
`docs/weekly/N.ko.html` (Korean) by `python3 scripts/build_weekly.py N`. English is the original.
After a new issue, add it to the `ISSUES` list in `docs/index.html`.

## When it comes out

One issue a week, on Monday morning Korea time. It looks back at the week that ended and ahead at the dates of the week that starts.

- Sunday evening Korea time: the next issue is drafted from the record as it stands (`weekly/N.json`, both HTML files, the `ISSUES` line)
  and opened as a pull request. Every date and figure is read again from its primary source on that day.
- The issue is public once that pull request is merged. Nothing is published without that approval.
- A `weekly/N.json` with no `docs/weekly/N.html` is a draft. `weekly/2.json` was written on Friday, November 27, one day after
  No. 1, and was held back for Monday, November 30. It is rewritten with that day's numbers before it goes out.

The layout is fixed, in this order:

1. **One line at the top**: state, score, since when (from the latest record and `state_durations`).
2. **What the score has meant**: the four outcome groups for the current ten-point band (`score_bands` in `docs/data.json`).
   Past counts only. The "not a forecast" line appears once, here.
3. **Event cards**: counts of open, worse, eased, resolved. Then good news that left the risk in place, and new facts of the week.
   From No. 2 on, this section also carries the cards' new fields:
   - `snapshot.checks`: how many resolution measures are met and on how many cards prices show the risk. Print it with
     `python3 scripts/build_weekly.py --checks` on the day of writing and paste it into `snapshot`.
   - `counter` (`{"h": card title, "p": text}` in each language): one card's "why this reading may be wrong", quoted from the card.
   - Under "good news that left the risk in place", say which numeric measure the good news failed to move, with its number.
4. **Sectors**: only the sectors whose step changed this week (`snapshot.sectors.changed` as `[key, "quiet|normal|strained", "quiet|normal|strained"]`), then the Strained and Quiet lists.
5. **Dates ahead**: scheduled dates with a short pre-event briefing for each. Free sample of the member briefing.
   A briefing is built from the card: the numeric measures for that date (the line and where it stands), what similar
   past events did, and whether prices show the risk. No view on what to buy or sell.
6. **What this is and is not.**

Rules of writing:

- Short lines up front. Conditions, corrections and sources go inside "Read more".
- Facts link to primary sources (government, central bank, regulator, company filings). No Wikipedia.
- `snapshot` holds the numbers as of writing, so an issue does not change when the record moves on.
- Level words: five market states and three sector steps only. Measures are shown as cells out of 3.
- "Down more than 20%", not "crash". No buy or sell wording.
- Corrections stay visible in the issue with their date.

## The email

`python3 scripts/build_weekly.py --email N` writes `weekly/email/N.en.html`, `N.ko.html` and a plain-text copy of each
(first line is the subject). The email is a shorter cut of the same JSON, not the page:

- Mail apps drop style blocks, scripts, web fonts and folds, so the page cannot be mailed as it is. The email uses tables,
  inline styles and system fonts, one language per file.
- It carries the state line, the title, good news that left the risk in place, new facts, sectors and the dates,
  then one button to the full note. Conditions, sources and briefings stay on the page.
- Every email ends with why the reader gets it, how to stop, the privacy page and the contact address.
- As of 2026-11-28 nothing sends these. Signing up stores an address; no mail has gone out yet.
