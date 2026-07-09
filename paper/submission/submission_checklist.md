# Submission Checklist

## Double-blind anonymity self-check (`main_anonymous.tex` / `main_anonymous.pdf`)

- [x] Author name removed from title page (`\author{Author information removed for blind review}`)
- [x] Affiliation (University of Toronto) removed from title page
- [x] No acknowledgments section present in either version (none was ever written)
- [x] No first-person self-identification ("my Degree", course codes, etc.) — searched, none found
- [x] PDF metadata author field inherits the anonymized `\author` field, not the real name
- [x] `tables/`, `figures/`, and `references.bib` are shared, content-identical, and carry no
      author-identifying information themselves
- [ ] **Manual step before submission**: strip PDF producer/creator metadata if the target
      journal's system flags it (tectonic sets standard LaTeX producer strings, not personal
      metadata, but some portals are stricter — check with `exiftool main_anonymous.pdf`)
- [ ] **Manual step**: if submitting to a portal that inspects file properties, re-save/print the
      anonymous PDF through the portal's own uploader rather than attaching the file directly, per
      that journal's own guidance

## Word count and length

- Main body (Introduction through Conclusion, excluding tables, figures, references, appendix):
  **6,411 words**
- Target band: 6,500–8,000 words (within ~2% of the floor; no cuts triggered, since the binding
  constraint in the task brief is only an *upper* bound of 8,000 words / 30 pages)
- Total PDF length: **28 pages** (body + tables + figures + references + appendix), under the
  30-page ceiling

## Tables and figures inventory

16 tables (`paper/tables/*.tex`, booktabs, self-contained `table` environments) + 8 figures
(`paper/figures/*.pdf`, vector, 300 dpi-equivalent):

| # | Main body | # | Appendix |
|---|---|---|---|
| 1 | Table 1 — Summary statistics | A1 | Table 2 — Lending by development tercile |
| 2 | Table 3 — Country-year linear/interaction | A2 | Table 5 — Loan-level linear/interaction |
| 3 | Table 3b — Country-year margins | A3 | Table 7 — Cluster-SE comparison |
| 4 | Table 4 — Country-year quadratic | A4 | Table A1 — Year/month coverage diagnostic |
| 5 | Table 5b — Loan-level margins | | |
| 6 | Table 6 — Loan-level quadratic | | |
| 7 | Table 8 — Logit coefficients + AME | | |
| 8 | Table 9 — Extensive vs. intensive margin | | |
| 9 | Table 10 — Lind–Mehlum U-test (3 rows) | | |
| 10 | Table 11 — Sample-period robustness | | |
| 11 | Table 12 — Loan-level robustness (4 variants) | | |
| 12 | Table 13 — U-test on robustness variants | | |

Figures 1–8 (all in main body): bivariate scatter with quadratic/LOWESS fit; lending-volume
histogram; GDP-per-capita histogram; per-capita lending scatter; three choropleth maps (lending,
GDP, institutions); entry-rate-by-decile bar chart.

## JEL codes and keywords

- **JEL codes:** G21 (Banks; Depository Institutions; Micro Finance Institutions), O16 (Financial
  Markets; Saving and Capital Investment), O12 (Microeconomic Analyses of Economic Development)
- **Keywords:** microfinance; Kiva; economic development; extensive margin; PPML; U-test

## Data and code availability

- `paper/export_assets.py` regenerates every table and figure directly from `outputs/*.csv`, using
  the same model specifications as `paper_publication_version.ipynb` (v1.2)
- `paper/verify_against_notebook.py` cross-checks 84 of 85 recomputed numbers against the
  notebook's own stored outputs (1 informational, 0 failures) — see `paper/ASSET_CHECK.md`
- Raw Kiva loan data and the large loan-level panel are excluded from the repository per
  `.gitignore` (see `README.md`, Data note)

## Before final submission

- [ ] Confirm target journal name and insert into `cover_letter_template.md`
- [ ] Confirm target journal's specific AI-disclosure policy (cover letter vs. manuscript
      acknowledgments vs. a separate disclosure form) and use the matching template sentence
- [ ] Confirm target journal's reference style; this manuscript uses `natbib` + `apalike`
      (author–year), which may need to be swapped for the journal's own `.bst` file
- [ ] Re-run `export_assets.py` and `verify_against_notebook.py` if the underlying notebook is
      re-executed for any reason before submission, to keep the iron rule (paper numbers = notebook
      numbers) intact
