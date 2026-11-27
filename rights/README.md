# Rights in the input data

Read on 2026-11-27, before anything is sold. This is the maintainer's reading of published terms. **It is not legal
advice**, and where a paid service depends on a point below, the owner of the data or a lawyer has the last word.

## Why this page exists

The ledger is free and public today. The plan is to charge for alerts later. Terms that are harmless for a free
personal project can forbid the same use in a paid one, so every input was checked against its owner's terms.

## What the terms say

| Input | Used for | Owner | What the owner's terms say | Usable in a paid service as it stands? |
| --- | --- | --- | --- | --- |
| VIX (`VIXCLS`) | score, part 1 | Cboe | FRED API terms: "Before using data series owned by third parties for anything other than your own personal use, you must contact the data owner to obtain permission." | No. Needs Cboe's permission or a licence. |
| ICE BofA high-yield spread (`BAMLH0A0HYM2`) | score, part 2 | ICE Data Indices | Same FRED clause. The value is already withheld from records; the level derived from it is still a use of the data. | No. Needs ICE's permission or a licence. |
| S&P 500 (`SP500`) | score, part 5 | S&P Dow Jones Indices | Same FRED clause. | No. Needs S&P's permission or a licence. |
| Chicago Fed NFCI (`NFCI`) | score, part 4 | Federal Reserve Bank of Chicago | The Bank's legal notice allows reproduction "provided that reproduction is not for the purpose of private and/or commercial gain" and with credit to the Bank. A regional Reserve Bank is not a federal agency, so its work is not automatically free of copyright. | Doubtful. Needs the Bank's permission. |
| 10-year minus 3-month Treasury yield (`T10Y3M`) | score, part 3 | US Treasury figures, spread computed by the St. Louis Fed | Treasury yields are a US government work. | Yes, when read from the Treasury or the Federal Reserve Board directly. |
| Moody's Baa spread (`BAA10Y`) | considered as a replacement for part 2 in research round 5 | Moody's | FRED marks it "Copyrighted: Citation Required". The series note says Moody's information "may not be copied or otherwise reproduced, repackaged, further transmitted". | No. **It is not the clean replacement it was taken for on 2026-11-27.** |
| FRED itself (the delivery route for all of the above) | every fetch | Federal Reserve Bank of St. Louis | The legal page says FRED content may not be "incorporated in any other database or compilation or sold in any form" without the Bank's permission, and its summary of prohibited uses includes selling FRED data. | Not as the route for a paid service. Government series should be read from the agency that publishes them. |
| OFR Financial Stress Index | benchmark in round 4; candidate input in round 8 | Office of Financial Research (US Treasury) | OFR legal notice: "No copyright may be claimed for any work on this website that was created by a federal employee"; "credit is requested if you reproduce or copy any such work". The notice does not say whether the 33 market variables behind the index are third-party; only the published index and its parts are used here. | Yes, with credit to OFR. Worth one email to OFR to confirm for a paid service. |
| Brent spot (EIA), Treasury yields, federal funds target, exchange rates (Federal Reserve Board H.15, H.10) | market price check | US government bodies | Government works. | Yes, when read from the agency directly, not through FRED. |
| Kenneth R. French Data Library | sector sensitivity, waves, research | Fama and French | Not read yet. | Unknown. To be read before sector scores are part of a paid product. |
| SPDR sector fund net asset values (State Street) | shadow breadth record | State Street | Not read yet. | Unknown. Used only in an unpublished-rule shadow record. |

Sources read: https://fred.stlouisfed.org/docs/api/terms_of_use.html , https://fred.stlouisfed.org/legal/ ,
https://fred.stlouisfed.org/series/BAA10Y , https://www.financialresearch.gov/legal-notices/ ,
https://www.financialresearch.gov/financial-stress-index/ , https://www.chicagofed.org/utilities/legal-notices .
The FRED API terms and the first part of the FRED legal page were read word for word; the end of the FRED legal page
and the end of the Chicago Fed notice were read in summary only.

## What follows from it

1. **Four of the five parts of the score cannot be sold as they stand**, and neither can the Baa replacement. This
   does not make today's free, credited, public ledger wrong, but it has to be settled before the first payment.
2. There are only two ways out: **permission or a licence** from Cboe, S&P, ICE and the Chicago Fed, or **a rule
   that runs on US federal government publications only**.
3. The second way is tested in research round 8 (`research/v4/preregistration8.json`, results in
   `research/v4/results8.json`): the same five-part rule with the OFR index's Volatility, Credit, Equity valuation
   and Funding parts in place of VIX, the high-yield spread, the S&P 500 fall and NFCI. It is an equivalence test,
   not an attempt at a better score. The rule in force does not change until the owner decides.
4. The cost of the second way is known in advance: the OFR index is published two business days late (today's
   inputs are one day late), and the score becomes, openly, a reading of a free government index. That is an
   honest description of what the score already is; see round 4, where the OFR index ranked above AFMX.
5. Whatever is chosen, fetching should move from the FRED API to the publishing agencies before anything is sold.
