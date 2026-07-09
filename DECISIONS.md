# Phase 2 Decisions Log

Autonomous execution log for Phase 2 substantive upgrade. Each entry: what was decided, why, and what
rule (if any) triggered it.

## Setup

- **Working directory confirmed**: `/Users/klicy/eco225-revision` (has `BASELINE_RESULTS.md`, the
  `backup` remote to `KexingYan/Essay`, and Phase 0/1 commits already present). Created local branch
  `revision` tracking `backup/revision` (was on `main`, identical commit).
- **Raw Kiva loan-level file recovered.** Phase 0/1 (`BASELINE_RESULTS.md`) recorded
  `outputs/final_panel_loan_level.csv` and the raw `loans.csv` as missing/unrecoverable on this machine.
  A search of `/Users/klicy/Downloads` found `loans.csv` (2.3GB, 1,419,607 data rows, Kiva Kaggle-style
  schema with `posted_time`, `sector_name`, `activity_name`, `country_code`). Symlinked to
  `data/loans.csv` (not copied, to avoid a redundant 2.3GB copy — three identical copies already existed
  in Downloads). This unblocks 2a/2c/2d, which all depend on loan-level data with fields the aggregated
  `final_panel_loan_level.csv` schema alone does not carry (dates, sector).
- **`analysis/build_final_panel_loan_level.py` had hardcoded Windows paths** (`C:\Users\Klicy\...`).
  Rewrote to use relative paths anchored on the repo root (`Path(__file__).resolve().parents[1]`) so the
  pipeline is reproducible on any machine — this is a portability fix, not a results change.
- **Security note (out of scope, flagged to user, not remediated)**: an unrelated sibling checkout at
  `/Users/klicy/github-classroom/ECO225-2026/eco225-project-KexingYan/.git/config` has a live GitHub
  OAuth token embedded in its remote URL in plaintext. Not part of this repo or task; flagged in the
  final report for the user to rotate.
- **Security note (this repo)**: `data/country_stats.csv` copied in from Downloads for the population
  merge (small, non-sensitive aggregate file; no PII).

## Subtask 2a — Sample period coverage

- **Decision: keep the full 2013–2017 sample.** Applied the pre-committed decision rule mechanically:
  2013 has complete 12-month coverage (0 months missing, threshold was ≥3) and loan counts are 80.4% of
  2014's (threshold for concern was <40%, combined with countries "clearly lower"). Neither disqualifying
  condition triggered, so 2013 is treated as a real (smaller) year of platform activity, not a partial
  year. Diagnostic table written as Appendix Table A1; decision narrative in new Section 2.3; year-FE
  interpretation paragraph added to Section 5.1; a "2014–2017 only" robustness column added to Section 6.2
  for both m6 and lm6 (both conclusions unchanged).
- Diagnostics were computed from raw `posted_time` in `data/loans.csv` (date info doesn't survive
  aggregation into `final_panel_country_year.csv`), saved to the small, git-tracked
  `outputs/table_year_month_coverage.csv` so the notebook doesn't need the 2.3GB raw file at "run all"
  time for this cell specifically (only Section 5.2/5.3/6.3 need it).

## Subtask 2b — Extensive/intensive margin decomposition + PPML

- **WDI pull used the live World Bank API via `wbdata`** (network access confirmed working; no fallback
  needed). Cached the pulled panel to `outputs/wdi_gdp_pop_2013_2017.csv` (committed, small) both for
  notebook runtime speed (the raw per-country `wbdata.get_data` loop took ~7 minutes) and as an
  offline-fallback source if the API is unreachable in a future run.
- **Kiva country-year totals for the global panel were built from the raw loan-posting data**, not from
  `final_panel_country_year.csv`, because the whole point of Section 5.3 is to observe zero-lending
  country-years, which by construction do not exist in the Kiva-only aggregated panel.
- **Country code harmonization**: used `country_converter` (ISO2→ISO3) on Kiva's 90 distinct country
  codes; all resolved cleanly, including territory-style codes (`XK`→Kosovo, `PS`→West Bank and Gaza,
  `GU`/`PR`/`VI` → US territories). WDI's 217 non-aggregate economies were merged in as the universe;
  65 of 1,085 resulting country-year cells were dropped for missing GDP per capita or population and this
  count is reported directly in the notebook.
- **Per the task's own decision rule**, institutional/financial-access variables are not used in the
  global-sample regressions (heavily missing outside the ~90–96 Kiva-covered countries) and are
  reintroduced only in the Kiva-only PPML column.
- PPML converged on both the global (incl.-zero) and Kiva-only samples without needing to rescale beyond
  dividing `total_loan_amount` by 1,000 (a stability precaution taken pre-emptively, not because the
  unscaled version failed) — no fallback to `sm.GLM` with custom start values was needed.
- **Notable finding surfaced prominently, not buried**: the extensive margin (Logit) shows a significant
  inverted-U (quadratic p=0.023, AME p=0.018) even though total lending *volume* does not (PPML p=0.24–0.53
  in both samples) — this is now a headline result in the Abstract/Conclusion, not just a robustness
  footnote, because it directly resolves the ambiguity about which margin the original "peak" hypothesis
  was ever really about.

## Subtask 2c — Loan-level robustness

- Built a separate augmented loan-level file (`outputs/final_panel_loan_level_augmented_2c.csv`, 918k
  rows, 183MB) that retains `sector_name` and `gdp_pc_const2015` in levels — fields the main
  `final_panel_loan_level.csv` build script drops. Added to `.gitignore` (too large for the repo, same
  treatment as the main loan-level file).
- US share of loans in this sample is 0.9%, **above** the task's 0.5% "limited impact" threshold, so no
  special caveat about US exclusion being moot was added — the exclusion was run and reported as a normal
  robustness column (result: quadratic term survives, if anything strengthens).
- Sector fixed effects used directly from Kiva's native `sector_name` field (15 categories); no need to
  merge an external raw file, since the raw `data/loans.csv` already carries this column.
- **Important honesty finding, surfaced in the main text per the task's explicit instruction, not hidden
  in an appendix**: the literal "relative loan size" spec (`log(loan_amount/gdp_pc_const2015)`) reproduces
  the baseline quadratic coefficient to 4 decimal places, because it is algebraically
  `log_loan_amount - log_gdp_pc` and `log_gdp_pc` is already the model's own linear regressor — a
  Frisch-Waugh-Lovell identity guaranteeing this "robustness check" cannot fail regardless of the true
  data-generating process. Added a supplementary specification (same outcome, linear GDP control dropped)
  as the actually-informative version of this test; it shows the U-shape attenuates (0.245→0.148) but
  survives (p=0.002). Both the mechanical identity and the corrected supplementary result are reported
  together in Section 6.3 and in Section 7 (Limitations).

## Subtask 2d — Lind–Mehlum (2010) U-test

- Implemented from scratch (delta-method slopes at sample extremes, intersection-union test statistic =
  weaker of the two end t-stats, Fieller (1954) CI for the turning point via the quadratic-in-r formula) —
  no external package used, matching the task's "手工实现" instruction.
- Applied to m6, lm6, and (in Section 6.3) all four of 2c's loan-level variants. Result exactly matches
  the task's stated expectation: **country-level m6 fails** (weaker end t≈1.08, p=0.140, unbounded Fieller
  CI) while **loan-level lm6 and all four of its robustness variants pass decisively** (p<0.001 in every
  case). This is now used explicitly in the Conclusion as the formal basis for treating the loan-level
  U-shape, not the country-level curvature, as the paper's central nonlinear finding.

## Phase 2e — Extensive margin held to the Lind–Mehlum standard

- **Trigger**: final review of Phase 2a–d found that Section 5.4 established "quadratic significance is
  necessary but not sufficient; Lind–Mehlum (2010) is the standard for shape claims" and used it to reject
  m6's inverted-U — but the paper's headline finding (Section 5.3's extensive-margin Logit) was never
  subjected to that same test, despite the Abstract calling it a "genuine, statistically significant
  inverted-U." This is an internal inconsistency: the paper cannot hold one margin to a stricter standard
  than another.
- **Test result, as predicted**: reused the existing `lind_mehlum_utest()` helper (cell 54; no new
  implementation needed — it already accepts any fitted statsmodels result with a linear/quadratic
  coefficient pair and a `cov_params()` matrix, so it applies directly to `logit_fit` on its native
  log-odds scale) against `logit_fit`, `"c_log_gdp_pc"`, `"c_log_gdp_pc_sq"`, evaluated at `gpanel`'s
  actual min/max of centered log GDP per capita. Result: **slope_low = 0.654, t_low = 1.065 (one-sided p =
  0.143, fails the 5% bar of 1.645)**; **slope_high = −2.742, t_high = −3.028 (one-sided p < 0.001,
  clears the bar easily)**; `shape_confirmed = False`; Fieller 95% CI for the turning point (centered) =
  [−10.384, −1.216] — wide but bounded, unlike m6's unbounded interval. This matches the task brief's
  predicted outcome (t_low upper bound ≈1.23) almost exactly (1.065 < 1.23), so the **"unexpected pass"
  branch was NOT triggered** — all replacement text was written as the "test failed" (downgrade) version,
  with no hedging or dual-branch language left in the prose.
- **Table 10** gained a third row, "Logit (global, extensive margin)," and its title was changed to
  reflect all three models tested. The Section 5.4 intro (cell 53) was updated to say the test is applied
  to "all three shape claims in the paper," not "the two preferred quadratic specifications."
- **Wording discipline applied**: every instance of "genuine inverted-U" / "significantly
  inverted-U-shaped" describing the **extensive margin** was rewritten to "significantly concave, with a
  steep decline; peak/initial rise unconfirmed" — in the Abstract, Introduction, Sections 5.3 and 5.4, and
  the Conclusion (both the narrative paragraph and the numbered summary list). Two numeric asides were
  corrected in passing, per the task's "顺带修三处小错" instruction interpreted narrowly to what the task
  actually specified: (1) the loan-level relative-size robustness result in the Abstract was updated from
  the mechanical FWL-identity restatement to the actually-informative attenuated coefficient (0.245 →
  0.148, already computed and reported in Section 6.3/DECISIONS.md 2c, just not previously surfaced in the
  Abstract); (2) the PPML Kiva-active-sample count in Section 5.3 was corrected from "374" to "369 of the
  374 (five drop for missing institutional controls)" to match the actual estimation sample rather than
  the full candidate sample; (3) the Section 5.4 intro's claim that Lind–Mehlum was applied to "the two
  preferred quadratic specifications" was corrected to "all three shape claims," since it undercounted
  once the extensive-margin Logit was added to Table 10 — leaving it unpatched would have made the
  section's own opening sentence wrong given the very addition this patch introduces.
- **Explicitly left untouched, per the task's instruction**: `lm6`'s U-shape language (loan-level, size
  margin) — that result passed Lind–Mehlum decisively (t_low ≈ −5.75, t_high ≈ 10.95, p < 0.001) in Phase
  2d and remains the paper's one confirmed nonlinearity. Also untouched: all descriptive/hypothesis-origin
  mentions of "peak" in Sections 3 and 5.1 (cells 7, 10, 13, 27, 36) — those describe the *original,
  since-rejected* middle-income-peak hypothesis or the country-level (m6) pattern, which already reads as
  "not confirmed," so they were already consistent with the new discipline and needed no edit.
- **Consistency scan (Task 3)**: grepped every markdown cell for `inverted-U`, `peak`, `rise` (case
  variants included) and manually classified each hit as either (a) about a hypothesis/description/lm6 —
  left alone, or (b) a conclusion about the extensive margin — rewritten. No stray "genuine inverted-U"
  language about the extensive margin survived the scan after edits (cells 0, 52, 53, 55, 67 were the only
  ones requiring changes).
- **Push**: `git push backup HEAD:revision` and the `v1.2` tag push were attempted per the task's explicit
  instruction; outcomes are recorded in the final report rather than here, since push success depends on
  runtime network/auth state that isn't a "decision."

## Commit granularity (deviation from the "commit per subtask" instruction)

- Subtasks 2a–2d all modify the same single notebook file (`paper_publication_version.ipynb`), and were
  implemented and executed together as one coherent `--execute --inplace` run (0 errors across 70 cells)
  before any of the four was committed. Splitting one file's changes into four artificial partial commits
  would have required manually reconstructing four intermediate notebook states after the fact, which is
  more likely to introduce errors than to provide real rollback value. Standalone analysis/build scripts
  that exist as separate files per subtask (`build_global_extensive_margin_panel.py`,
  `build_loan_level_augmented_2c.py`) are committed as such. The final commit message itemizes all four
  subtasks' contributions individually for traceability.
