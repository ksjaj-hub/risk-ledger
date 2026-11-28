# Short questions: one release, one yes-or-no, scored in public

Event cards take months to close, so they cannot show for a long time whether AFMX's probabilities are any good.
Short questions can. Each one asks whether a number in a scheduled official release will be at or above a line,
gives a probability before the release, and is settled from the release itself one or two weeks later.

Beta. Target: 40 to 60 settled questions by the end of February 2027.

## What a question holds

- **release**: the agency, the release, its scheduled date and time (Eastern), and its page.
- **question**: one sentence that can only be answered yes or no.
- **reading**: exactly which figure settles it. Always the figure as first printed for that period. Revisions do not count.
- **threshold**: yes means the printed figure is at or above it.
- **previous**: the last printed figure, with the page it was read from.
- **no_change_answer**: the answer if the figure simply repeated the previous one (1 yes, 0 no).
- **p**: AFMX's probability of yes.
- **basis**: one or two sentences on why.

## Rules

1. A question is written at least one day and at most 21 days before the scheduled release. The commit that adds
   it is the proof of the time.
2. Nothing in a question is edited after that. There are no revisions: one probability per question.
3. It is settled from the primary source only (BLS, BEA, the Federal Reserve, Treasury, Census and the like), on the
   figure as printed and rounded in the release. The outcome records the figure, the date and the page.
4. If the release is postponed, the question waits for it. If the figure has not been published 30 days after the
   scheduled date, or the agency does not publish that figure at all, the question is **void**: it stays on the page
   with the reason and is not scored.
5. Thresholds are fixed with the question. At least one question in three must have a line different from "same as
   last time", so that the set cannot be filled with easy calls.
6. Every question written is listed and scored. None is dropped.

## Score

`python scripts/forecast_score.py` scores the cards and then these questions (`scripts/questions.py`), and writes
`questions/scorecard.json` and the page `docs/questions.html`.

- **Brier score**: (probability - outcome)^2, averaged. Lower is better.
- **Always 50%**: 0.25. A forecaster with no view.
- **No change**: answers every question as if the last figure repeats. This is the one to beat.
- From 30 settled questions: a table of what was said against what came true, and a 90% range of the difference
  against "no change", found by resampling whole releases, because questions on one release move together.
- Before any result, the page shows what the score would be if every probability were exactly right, and how often
  that would still lose to 50% by luck.

## Limits

- The probabilities are judgment from the facts cited, not a model and not market odds. Surveys of economists and
  prediction markets answer the same kind of question with more information. AFMX does not compare against them yet.
- 40 to 60 questions can show a large difference from 50%, not a small one.
- Questions on the same release share one surprise. Six questions are closer to three independent ones.
- A good score here says the probabilities are honest. It does not say the event cards are right.
- Not investment advice.

The append-only guard runs `python scripts/questions.py --guard REF`.
