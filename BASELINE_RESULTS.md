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

## Table 3/4 — Loan-level regressions (re-verified in Phase 2)

**Update (Phase 2 setup, 2026-07-09):** the raw Kiva `loans.csv` was located at
`/Users/klicy/Downloads/loans.csv` (1,419,607 rows) and symlinked to `data/loans.csv`.
`analysis/build_final_panel_loan_level.py` was patched to use portable relative paths (previously
hardcoded to a Windows machine) and re-run, producing `outputs/final_panel_loan_level.csv` with
**917,955 rows across 90 countries, 2013–2017** — matching the ~918k rows referenced in the task spec.
Independently re-estimating lm6 (`log_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1
+ log_population + C(year)`, country-year clustered SE) on this rebuilt file reproduces the previously
reported coefficient almost exactly: **c_log_gdp_pc_sq = 0.2447, p = 2.4e-18** (N = 913,128), confirming
the statistically significant, positive (U-shaped) loan-level pattern reported below is not an artifact
of an unverified prior run.

Original text (retained for the record): per the user's own prior diagnosis, the loan-level quadratic
term is reported as **+0.245, p < 0.01** — a statistically significant **positive** (U-shaped)
coefficient, opposite in sign to the country-level result above.

## Confirmed bugs

1. **Map bug (`ISO_A2 == "-99"` silently drops five territories' geometry).** Cell constructing `world`
   filters `world[world["ISO_A2"] != "-99"]`. In Natural Earth 110m data, five territories are coded
   `ISO_A2 == "-99"`: France, Norway, Northern Cyprus, Somaliland, and Kosovo. This filter removes all
   five countries' geometry from the map entirely (not just their data — their outline), before any merge
   happens. **Correction (verified directly against the panel, superseding an earlier unverified guess in
   this file):** of the 84 Kiva-panel countries, only **Kosovo (XK)** is among the five `-99` codes, so it
   is the only one whose actual lending data was being lost by this bug (France, Norway, Northern Cyprus,
   and Somaliland are not Kiva-active countries in this panel at all, so they were never going to show
   lending data regardless — the bug there is purely cosmetic, leaving unexplained holes in the map where
   there should be a "no data" grey fill). Direct check: matching on `ISO_A2` (old, buggy) finds 81/84
   panel countries with unmatched = `['VC', 'WS', 'XK']`; matching on `ISO_A2_EH` (fixed) finds 82/84 with
   unmatched = `['VC', 'WS']` — i.e. the fix recovers exactly Kosovo. `VC` (Saint Vincent and the
   Grenadines) and `WS` (Samoa) remain unmatched under either approach because the low-resolution 110m
   shapefile does not include separate polygons for them at all.
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

---

# Phase 2 Results — New vs. Old

Recorded 2026-07-09 after implementing subtasks 2a–2d. All numbers below were produced by an actual
`--execute --inplace` run of `paper_publication_version.ipynb` (70 cells, 0 error outputs).

## 2a — Sample period coverage (new)

| Year | N loans | Total $ | N countries | Months covered | % of 2014 loans |
|---|---|---|---|---|---|
| 2013 | 140,034 | $133.0M | 74 | 12/12 | 80.4% |
| 2014 | 174,234 | $152.9M | 81 | 12/12 | 100.0% |
| 2015 | 181,833 | $157.6M | 77 | 12/12 | 104.4% |
| 2016 | 197,236 | $164.4M | 74 | 12/12 | 113.2% |
| 2017 | 224,618 | $175.6M | 76 | 12/12 | 128.9% |

**Decision: KEEP full 2013–2017 sample** (2013 is a complete 12-month year, above both disqualifying
thresholds). Section 6.2 re-estimates m6 and lm6 on 2014–2017 only as a direct check:

| | Full sample | 2014-2017 only |
|---|---|---|
| m6 quadratic term | −0.168 (p=0.180) | −0.176 (p=0.159) |
| lm6 quadratic term | 0.245 (p<0.001) | 0.246 (p<0.001) |

Both conclusions (insignificant at country level, significant at loan level) are unchanged.

## 2b — Extensive vs. intensive margins (new)

Global country-year panel: 1,020 country-years, 206 countries, 374 (36.7%) Kiva-active, 65 rows dropped
for missing WDI GDP/population.

| | Coefficient | p-value |
|---|---|---|
| Logit (extensive margin), quadratic term | −0.260 | **0.023** |
| Logit AME, quadratic term | −0.040 | **0.018** |
| PPML global incl. zeros, quadratic term | −0.232 | 0.242 |
| PPML Kiva-only, quadratic term | −0.070 | 0.530 |

**New finding: the extensive margin (whether Kiva operates in a country at all) is significantly
inverted-U-shaped** (turning point ≈ $893, within sample range), while total lending *volume* — whether
estimated with OLS-in-logs (Table 4, pre-existing) or PPML on either sample — is not. This was not
previously tested; Phase 0/1 only had the (insignificant) OLS-in-logs country-level result.

## 2c — Loan-level robustness (new)

| Variant | Quadratic term | p |
|---|---|---|
| (1) lm6 baseline | 0.245 | <0.001 |
| (2) Excl. US (0.9% of loans) | 0.332 | <0.001 |
| (3) Relative size (loan/GDPpc) | 0.245 (identical to (1) by FWL construction — see caveat below) | <0.001 |
| (4) Sector FE (15 sectors) | 0.234 | <0.001 |
| (3-supplementary) Relative size, no linear GDP control | 0.148 | 0.002 |

**Important honesty note (not hidden):** variant (3) as literally specified reproduces the baseline
quadratic coefficient to 4 decimal places because `log(loan/gdp_pc) = log_loan_amount - log_gdp_pc`, and
`log_gdp_pc` is already the model's own linear regressor — a Frisch-Waugh-Lovell algebraic identity, not
independent confirmation. The supplementary check (same outcome, linear GDP control removed) shows the
U-shape **attenuates from 0.245 to 0.148 but remains significant**, meaning part of the nominal-dollar
U-shape likely reflects local price-level scaling, but not all of it.

## 2d — Lind–Mehlum (2010) U-test (new)

| Model | t (low end) | t (high end) | Shape confirmed? | Turning point (Fieller 95% CI) |
|---|---|---|---|---|
| m6 (country-year, volume) | 1.08 | −1.48 | **No** (p=0.140) | unbounded |
| lm6 (loan-level, size) | −5.75 | 10.95 | **Yes** (p<0.001) | log GDP ≈7.36 [7.05, 7.59] (~\$1,150–\$1,970) |
| lm6 excl. US | −4.87 | 7.13 | Yes (p<0.001) | — |
| lm6 relative size | −12.19 | 4.75 | Yes (p<0.001) | — |
| lm6 sector FE | −5.65 | 11.07 | Yes (p<0.001) | — |

This is the formal, independent confirmation (beyond p-values on the quadratic term alone) that the
country-level "peak" fails even a test designed to be charitable to curvature, while the loan-level
U-shape passes decisively and has a turning point tightly bracketed well inside the sample range.

## Data recovered

The raw `loans.csv` (missing in Phase 0/1) was located at `/Users/klicy/Downloads/loans.csv` and used to
rebuild `outputs/final_panel_loan_level.csv` (917,955 rows) and two new derived files: an augmented
loan-level file with sector/GDP-level columns (`outputs/final_panel_loan_level_augmented_2c.csv`, 183MB,
gitignored) and a global country-year panel with zero-lending observations
(`outputs/final_panel_global_extensive.csv`, 1,020 rows, committed).
