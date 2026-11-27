# Weekly note

One JSON file per issue (`N.json`), built into `docs/weekly/N.html` (English, with a language switch) and
`docs/weekly/N.ko.html` (Korean) by `python3 scripts/build_weekly.py N`. English is the original.
After a new issue, add it to the `ISSUES` list in `docs/index.html`.

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
