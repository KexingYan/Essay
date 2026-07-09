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

(Further entries appended by subtask below.)
