# Sector score: public grading

- `snapshots/YYYY-MM.json`: the sector scores as shown on the page, saved once per calendar month by the
  collector and never overwritten.
- `scorecard.json`: for each snapshot, how the sectors did in the **following** calendar month, relative to the
  market (Kenneth R. French Data Library industry returns), and whether the three highest-score sectors did worse
  than the three lowest. Written by the monthly "sector sensitivity" workflow.

The French data is published with a delay of about two months, so the first grade (for December 2026) is expected
around February or March 2027. Misses are published as they are. One month says very little; read the running count.
The score method and card mapping in force are in `sensitivity/mapping.json`.
