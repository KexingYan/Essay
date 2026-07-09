# Baseline Results — Original Course Submission

Recorded from an end-to-end execution of `project_2_new_revised_fixed_loanlevel.ipynb` on 2026-07-09,
in a fresh environment at `/Users/klicy/eco225-revision/` (Python 3.14 venv; pandas 3.0.3, statsmodels
0.14.6, geopandas 1.1.4, linearmodels 7.0). This is the reference point for all Phase 1+ changes.

## Data availability caveat

Two files referenced by the notebook were **not present** in the submitted zip and could not be
regenerated on this machine (see conversation for details — the loan-level build script requires a raw
Kiva `loans.csv` that lives only on the original Windows machine):

- `outputs/final_panel_loan_level.csv` (~918k rows) — **missing**. Table 3/4 (loan-level regressions)
  could **not** be independently re-executed here. The numbers below for Table 4 are the coefficients
  already reported by the user from their own prior run, not re-verified in this session.
- Natural Earth shapefile — was missing from the zip; downloaded fresh from the official
  `naturalearthdata.com` 110m admin-0 countries release and placed at
  `data/natural_earth_countries_110m/`. Map cells run correctly with this file.

Everything else below (country-year panel, Tables 1–2, maps, figures) was executed and verified directly
in this session.

## Sample (country-year panel)

- `outputs/final_panel_country_year.csv`: **357 rows**, 84 countries, 5 years (2013–2017), 0 duplicate
  country-year keys.
- Missingness: `poverty_rate` 57.7%, `financial_access_index` 9.5%, `log_gdp_pc` 1.7%,
  `institutional_pca1`/`institutional_index` 1.4%, `log_population` 0.8%, `log_total_loan_amount` 0%.

## Table 1 — Linear and interaction specifications (m1–m4), country-clustered SE

| | m1 | m2 | m3 (+year FE) | m4 (+interaction) |
|---|---|---|---|---|
| log_gdp_pc | -0.0599 (0.1499), p=0.690 | -0.1805 (0.1580), p=0.253 | -0.1789 (0.1691), p=0.290 | -0.1304 (0.1651), p=0.430 |
| institutional_pca1 | — | 0.2512 (0.1885), p=0.183 | 0.2725 (0.2084), p=0.191 | 2.2128 (1.4749), p=0.134 |
| log_gdp_pc × institutional_pca1 | — | — | — | -0.2517 (0.1948), p=0.196 |
| log_population | 0.1121 (0.0942), p=0.234 | 0.1344 (0.0967), p=0.165 | 0.1453 (0.1099), p=0.186 | 0.1564 (0.1163), p=0.179 |
| N | 348 | 348 | 348 | 348 |
| R² | 0.010 | 0.018 | 0.279 | 0.302 |

No coefficient on `log_gdp_pc` is significant at conventional levels in any of m1–m4; the point estimate
is negative throughout.

## Table 2 — Quadratic and robustness specifications (m5–m8), country-clustered SE

| | m5 | m6 (+year FE) | m7 (institutional_index) | m8 (financial_access_index) |
|---|---|---|---|---|
| centered log_gdp_pc (linear term, at mean) | -0.1173 (0.1529), p=0.443 | -0.1106 (0.1646), p=0.502 | -0.1211 (0.1670), p=0.468 | -0.1617 (0.2369), p=0.495 |
| centered log_gdp_pc² (quadratic term) | **-0.1553** (0.1161), p=0.181 | **-0.1676** (0.1249), p=0.180 | **-0.1700** (0.1251), p=0.174 | **-0.2013** (0.1232), p=0.102 |
| N | 348 | 348 | 348 | 319 |
| R² | 0.034 | 0.298 | 0.298 | 0.304 |

**This confirms the diagnosed problem exactly**: the quadratic term ranges from -0.155 to -0.201 with SEs
of ~0.12, and is **not statistically significant in any specification** (all p > 0.10). The linear term
evaluated at the sample mean is also negative in every specification — i.e., loan volume is estimated to
be *decreasing* in GDP per capita across most of the observed income range, not rising to a peak.

Turning point audit (preferred model m5): sample range of log GDP per capita is [5.539, 10.971]; the
implied turning point is at log GDP per capita = 7.456 (≈ $1,731 in constant 2015 USD), which is
numerically inside the sample range, but this is not meaningful given the quadratic term itself is
statistically indistinguishable from zero.

## Table 3/4 — Loan-level regressions (NOT independently re-executed — data missing)

Per the user's own prior diagnosis (not re-verified in this session due to missing
`final_panel_loan_level.csv`): the loan-level quadratic term is reported as **+0.245, p < 0.01** — a
statistically significant **positive** (U-shaped) coefficient, opposite in sign to the country-level
result above. This must be re-verified once the loan-level file is available (see open item in Phase 1).

## Confirmed bugs

1. **Map bug (France/Norway silently dropped).** Cell constructing `world` filters
   `world[world["ISO_A2"] != "-99"]`. In Natural Earth 110m data, France and Norway both have
   `ISO_A2 == "-99"` (multi-territory country quirk), so this filter removes them before the merge.
   Confirmed in this run: of 82 panel country codes considered (84 minus 2 legitimately unmatched — `WS`
   Samoa, `XK` Kosovo — which are absent from the 110m shapefile), only **80 matched**, i.e. two more
   were silently lost. Those two are France and Norway.
2. **log vs log1p inconsistency.** The map cell computes
   `log_loan_per_100k = np.log1p(loan_per_100k)`, while the regression tables use plain `np.log`
   (via `log_total_loan_amount`, already log-transformed upstream) for the same underlying quantity.
   Confirmed present in cell computing `map_df["log_loan_per_100k"]`.
3. **Duplicate figure/table numbering.** "Project One" section defines Figure 1–4 (cells 8–16). "Project
   Two" section then restarts numbering and defines a second Figure 2 (cell 20), and a second Figure 3,
   4, 5 (cells 21–27) for the maps. So "Figure 2", "Figure 3", and "Figure 4" each refer to two different
   figures in the same document. Table numbering has an analogous issue (Table 1/2 appear once for
   summary stats in Project One and again for regressions in Project Two).
4. **`loan` variable undefined when loan-level file missing.** The fallback branch in the loan-level
   loading cell only prints `"TBD: final_panel_loan_level.csv not found..."` and never defines `loan`,
   so every downstream cell that references `loan`/`loan_reg`/`lm1`...`lm8` raises `NameError` instead of
   gracefully degrading (unlike the equivalent country-year fallback, which does define an empty `reg`).
   Patched locally in this session (defining `loan = pd.DataFrame()`) purely to let the rest of the
   baseline notebook execute; this should be handled properly (or the TBD scaffolding removed entirely,
   per the Phase 1 spec) in the publication version.
5. **Windows-specific paths only in `analysis/build_final_panel_loan_level.py`**, not in the notebook
   itself — the notebook already tries relative paths first. No path fix was needed to run the notebook
   on this Mac.

## Conclusion-section contradiction (verbatim, cell 45)

> "Across both levels of analysis, the evidence points to a **nonlinear development pattern**:
> microfinance appears most active in **lower-middle income settings** rather than in the poorest or
> richest countries."

This directly contradicts the notebook's own Table 2 output (quadratic term insignificant, p > 0.10 in
all four specifications) and is inconsistent with Table 4's reported sign (positive/U-shaped, the
opposite of the inverted-U claimed here). This is the passage that Phase 1b must rewrite.
