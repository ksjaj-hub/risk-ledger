# What was read before the tests were written (2026-11-26)

Primary sources only: central-bank publications and the working-paper versions of journal articles.
Each line says what the source states and what it changes in the tests. Where only part of a document
could be read, that is said.

## How official stress indexes are built

- **St. Louis Fed Financial Stress Index.** First principal component of 18 weekly series (7 interest
  rates, 6 yield spreads, 5 others), each de-meaned and divided by its standard deviation; in the 2010
  version it explained 44.3% of the total variation. Version 2.0 (2020) switched interest rates and stock
  prices from levels to daily changes because trending levels had "introduced a subtle but nevertheless
  important statistical bias."
  [2010 appendix](https://files.stlouisfed.org/files/htdocs/publications/net/NETJan2010Appendix.pdf),
  [2020 note](https://www.stlouisfed.org/on-the-economy/2020/march/financial-stress-index-version-2).
  *Used for:* candidate C3 (principal-component weights). The 2020 fix is a warning about fixed
  thresholds on series whose normal level drifts.
- **Kansas City Fed Financial Stress Index** (Hakkio and Keeton, Economic Review 2009 Q2). 11 variables,
  principal components, 61.4% of variation explained. The coefficients run only from 0.081 to 0.130.
  [paper](https://www.kansascityfed.org/Economic%20Review/documents/1392/2009-Financial%20Stress:%20What%20Is%20It,%20How%20Can%20It%20Be%20Measured,%20and%20Why%20Does%20It%20Matter%3F.pdf)
  (first 40% read verbatim). *Used for:* the expectation that principal-component weights will be close to
  equal weights, so C3 may not differ from C2.
- **OFR Financial Stress Index** (Monin, OFR Working Paper 17-04). 33 daily indicators in five groups
  (credit, equity valuation, funding, safe assets, volatility); one-factor dynamic model; each indicator
  standardised with its mean and standard deviation "up until that date", weights re-estimated daily and
  past values not recomputed. Evaluated by logistic regression against dates of government intervention.
  [paper](https://www.financialresearch.gov/working-papers/files/OFRwp-17-04_The-OFR-Financial-Stress-Index.pdf).
  *Used for:* never letting a day's score depend on later data; evaluating with a yes/no outcome.
- **ECB CISS** (Holló, Kremer and Lo Duca, ECB Working Paper 1426). 15 raw measures in five market
  segments; each turned into an order statistic from its empirical distribution; sub-indexes combined
  like a portfolio with time-varying cross-correlations, so stress in several segments at once counts
  more. [abstract](https://econpapers.repec.org/RePEc:ecb:ecbwps:20121426). *Used for:* C2 (percentiles
  instead of hand-set thresholds) and C4 (correlation weighting).
- **Chicago Fed NFCI** (FAQ; Brave and Butters 2011). Weighted average of 105 indicators, weekly.
  "The history of the indexes can change from week to week depending on incoming data and data revisions."
  [FAQ](https://www.chicagofed.org/-/media/publications/nfci/nfci-faqs-pdf.pdf),
  [paper](https://www.chicagofed.org/-/media/publications/economic-perspectives/2011/1qtr2011-part2-brave-butters-pdf.pdf).
  *Used for:* lagging NFCI by its publication delay, and C7 (a score that does not use it).

## What each kind of input is good for

- **Yield curve.** Estrella and Mishkin (NY Fed Current Issues 2(7), 1996): the 10-year minus 3-month
  spread beats other indicators for recessions two to six quarters ahead; one quarter ahead, leading
  indexes do better. [paper](https://www.newyorkfed.org/medialibrary/media/research/current_issues/ci2-7.html).
  Engstrom and Sharpe (FEDS Notes 2018, 2022): the near-term forward spread carries the signal and
  long-term spreads add nothing; it reflects expected policy easing; "It is not valid to interpret
  inverted term spreads as independent measures of impending recession."
  [2018](https://www.federalreserve.gov/econres/notes/feds-notes/dont-fear-the-yield-curve-20180628.html),
  [2022](https://www.federalreserve.gov/econres/notes/feds-notes/dont-fear-the-yield-curve-reprise-20220325.htm).
  *Used for:* C1. The curve answers a one-to-two-year question; the market state answers a
  weeks-to-months question.
- **Credit spreads.** Favara, Gilchrist, Lewis and Zakrajšek (FEDS Notes 2016): the predictive content
  of the corporate spread for recessions within 12 months "is due entirely to" the excess bond premium;
  a 50 basis point rise adds about 15 percentage points to the probability; 2002 was a false alarm.
  [note](https://www.federalreserve.gov/econresdata/notes/feds-notes/2016/recession-risk-and-the-excess-bond-premium-20160408.html),
  [data note](https://www.federalreserve.gov/econres/notes/feds-notes/updating-the-recession-risk-and-the-excess-bond-premium-20161006.html).
  *Used for:* C6.
- **Volatility.** Bekaert and Hoerova (ECB Working Paper 1675): of the two parts of the squared VIX, the
  expected variance has more power for financial instability than the variance premium, which instead
  predicts stock returns. [abstract](https://econpapers.repec.org/RePEc:ecb:ecbwps:20141675).
  Giglio, Kelly and Pruitt (NBER Working Paper 20963): of 19 systemic-risk measures "few ... possess
  robust power to forecast downside macroeconomic quantiles"; financial-sector equity volatility is the
  robust one; measures tell more about the lower tail than the middle.
  [paper](https://www.nber.org/papers/w20963.pdf) (first half read verbatim). *Used for:* C5.
- **Low volatility.** Danielsson, Valenzuela and Zer (FEDS 2016-093; FEDS Notes 2018), 60 countries over
  200 years: the level of volatility does not predict crises, unusually low volatility does, over years.
  [paper](https://www.federalreserve.gov/econres/feds/learning-from-history-volatility-and-financial-crises.htm),
  [note](https://www.federalreserve.gov/econres/notes/feds-notes/low-risk-as-a-predictor-of-financial-crises-20180509.htm).
  *Not tested here:* a multi-year build-up signal is a different product from a daily state. Kept as a
  caution for how "Calm" is worded.
- **Tail, not average.** Adrian, Boyarchenko and Giannone (NY Fed Staff Report 794): tight financial
  conditions move the lower quantiles of future growth; "the upper quantiles are stable over time".
  [report](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr794.pdf).
  *Used for:* reporting the bad end of the past range by state (outcome O4), not an average.

## How to judge an indicator

- Drehmann and Juselius (BIS Working Paper 421): early-warning indicators should be judged on criteria
  taken from the user's decision, including timing and stability. [page](https://www.bis.org/publ/work421.htm)
  (abstract read; the full paper was not). The area under the ROC curve is the measure used there and in
  the OFR paper. *Used for:* the separation and stability measures.

## Read about, not usable here

- CoVaR, MES and SRISK need firm-level balance-sheet and return data that this repository does not have
  and could not republish. Giglio, Kelly and Pruitt describe MES-type measures as lagging the others.
