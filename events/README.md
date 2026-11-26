# Event risk cards

One file per event. Each card says what happened, how it reaches markets, and, most importantly,
**what would have to be true for the risk to count as resolved, written down before the outcome is known**.

- `status` is one of `open`, `easing`, `resolved`, `worsened`.
- The original `resolution_conditions` are not rewritten. If they need to change, the change is added to
  `history` with a date and a reason, so readers can see both versions.
- `relief_headlines_that_do_not_resolve_it` lists good news that does not meet the conditions.
- Every status change is a dated entry appended to `history`. Git history shows when each line was written.
- Facts are limited to what the listed sources state. Where sources disagree, the card says so.
