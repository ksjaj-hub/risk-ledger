# Watch share ("worry index"): design only, nothing published

What people on the AFMX waitlist, and later paying members, ask alerts for, counted per person and
shown only as totals. Written 2026-11-28, before any answer was counted.

- `design.ko.md`: the design, weaknesses first (Korean).
- `gates.json`: the numbers that must be met before anything is shown, fixed in advance.
- `../../scripts/worry_index.py`: the count. It reads the operator's private export, which holds
  addresses and must never be committed here, and prints only what the gates allow.

Short version: with no users this is a table, not an index; it measures what people watch, not what
they fear; it is not a sample of individual investors. Nothing is published below 100 people with
confirmed addresses. A series over time needs 300 paying members and has to rank sectors differently
from a plain popularity baseline. If 100 is not reached by 2027-08-31 the public version is dropped.
