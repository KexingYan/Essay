## Data note
Raw data files (e.g. loans.csv, Kiva datasets) are not included due to size constraints.
All analysis scripts assume data are stored locally under the /data directory.

## Main findings

The paper tests whether Kiva microfinance activity follows an inverted-U ("middle-income peak") pattern
with economic development, at three distinct margins:

1. **Extensive margin (country level): does Kiva operate in a country at all?** Significantly
   inverted-U-shaped. A Logit model on a global country-year panel (including true zero-lending
   country-years, not just Kiva-active ones) finds a negative, statistically significant quadratic term
   (p = 0.023; average marginal effect p = 0.018): the probability Kiva is active rises from the poorest
   income decile to a peak in the second decile, then declines to near zero among the richest countries.
2. **Quantity margin (country level, conditional on Kiva being active): how much total lending does a
   country receive?** Not significantly nonlinear. The quadratic term in log GDP per capita is negative in
   every country-year OLS specification but never significant (p > 0.10), and this holds whether estimated
   in logs (dropping zeros) or with PPML on a zero-inclusive global sample (p = 0.16–0.53 across
   specifications). The linear component is negative on average — volume trends down with development.
3. **Size margin (loan level): how large is a typical individual loan?** Significantly U-shaped — the
   opposite sign from the country-level curvature. The quadratic term is positive and significant at the
   1% level, and survives excluding the US, adding sector fixed effects, and (with attenuated but still
   significant magnitude) deflating by local price levels.

These are three different empirical objects, not three tests of the same claim: a country can become less
likely to receive any Kiva lending as it develops, while — conditional on receiving some — total volume and
typical loan size follow different, and in one case opposite-signed, patterns.

## Methods

- **Country-year and loan-level OLS**, country- and country-year-clustered standard errors respectively,
  with linear, interaction, and quadratic (centered) specifications against log GDP per capita,
  institutional quality, log population, and year fixed effects.
- **Two-margin decomposition (extensive vs. intensive).** A global country-year panel merging World Bank
  GDP-per-capita and population data (all non-aggregate WDI economies, 2013–2017) with Kiva loan totals
  built from raw loan-posting data, outer-joined so that country-years with no Kiva loans appear as true
  zeros rather than being dropped. The extensive margin (whether Kiva is active) is modeled with **Logit**
  (country-clustered SE, average marginal effects via `get_margeff`); the intensive margin (total lending
  volume, now including zeros) is modeled with **PPML** (Poisson pseudo-maximum-likelihood via
  `statsmodels` GLM), estimated both on the full zero-inclusive sample and on the Kiva-only subsample.
- **Lind–Mehlum (2010) U-test.** For any quadratic specification, a significant quadratic coefficient does
  not by itself establish that the curve turns within the observed data range. Implemented from scratch:
  the slope of the fitted curve at the sample's minimum and maximum X, each with a delta-method standard
  error, tested as an intersection-union pair (the test statistic is the weaker of the two end t-statistics
  — both ends must independently clear significance with opposite signs), plus a **Fieller (1954)
  confidence interval** for the turning point that correctly accounts for it being a ratio of two
  correlated estimated coefficients. Applied to the preferred country-year and loan-level quadratic models
  and to all loan-level robustness variants.
- **Sample-period and loan-level robustness checks**: a data-driven decision rule for whether to include
  the panel's first year (2013) based on month/loan/country coverage in the raw data (year and month
  extracted directly from Kiva's `posted_time` field); re-estimation excluding the United States; a
  relative-loan-size specification (loan amount deflated by local GDP per capita, with an explicit check
  for — and correction of — a Frisch-Waugh-Lovell mechanical-identity pitfall in the naive version of this
  test); and sector fixed effects using Kiva's native sector classification.
