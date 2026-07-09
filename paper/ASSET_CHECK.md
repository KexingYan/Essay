# ASSET_CHECK.md

Programmatic comparison of every number recomputed by `export_assets.py` against the actual stored outputs of the executed `paper_publication_version.ipynb` (v1.2). The notebook is the source of truth; any FAIL must be fixed in `export_assets.py`, never in the notebook.

**Result: 84 PASS / 0 FAIL / 0 SKIP / 1 INFO, out of 85 checks.**

| Check | Notebook value | Computed value | Status |
|---|---|---|---|
| reg rows | 357.0 | 357 | **PASS** |
| reg countries | 84.0 | 84 | **PASS** |
| loan_reg rows | 917955.0 | 917955 | **PASS** |
| gpanel rows | 1020.0 | 1020 | **PASS** |
| gpanel active | 374.0 | 374 | **PASS** |
| m5 coef c_log_gdp_pc | -0.1173 | -0.11725616957845464 | **PASS** |
| m5 coef c_log_gdp_pc_sq | -0.1553 | -0.15526309858615556 | **PASS** |
| m5 p-value sq | 0.181 | 0.18102394349953244 | **PASS** |
| m5 turning point (log gdp) | 7.456 | 7.45646417728141 | **PASS** |
| m5 turning point (USD) | 1731.02 | 1731.0166559442357 | **PASS** |
| m5 coef (Table4 stargazer) | -0.155 | -0.15526309858615556 | **PASS** |
| m6 coef (Table4 stargazer) | -0.168 | -0.16762965655507142 | **PASS** |
| m7 coef (Table4 stargazer) | -0.17 | -0.1699747534306184 | **PASS** |
| m8 coef (Table4 stargazer) | -0.201 | -0.20125715236598812 | **PASS** |
| m6 c_log_gdp_pc (Table11) | -0.1106 | -0.11056783090949068 | **PASS** |
| m6 p (Table11) | 0.5018 | 0.5018476967368761 | **PASS** |
| m6 c_log_gdp_pc_sq (Table11) | -0.1676 | -0.16762965655507142 | **PASS** |
| m6 p_sq (Table11) | 0.1795 | 0.17949323742979917 | **PASS** |
| m6 N (Table11) | 348.0 | 348 | **PASS** |
| lm6 c_log_gdp_pc (Table11) | 0.2055 | 0.20551782055645126 | **PASS** |
| lm6 c_log_gdp_pc_sq (Table11) | 0.2447 | 0.24470659624425728 | **PASS** |
| lm6 p_sq (Table11) | 0.0 | 2.3837406469569737e-18 | **PASS** |
| lm6 N (Table11) | 913128.0 | 913128 | **PASS** |
| table11 m6_1417 c_log_gdp_pc_sq | -0.176 | -0.176 | **PASS** |
| table11 lm6_1417 c_log_gdp_pc_sq | 0.2456 | 0.2456 | **PASS** |
| lm6 coef c_log_gdp_pc (cell42) | 0.2055 | 0.20551782055645126 | **PASS** |
| lm6 coef c_log_gdp_pc_sq (cell42) | 0.2447 | 0.24470659624425728 | **PASS** |
| lm6 p_sq (cell42) | 0.0 | 2.3837406469569737e-18 | **PASS** |
| lm6 turning point (log gdp) | 7.363 | 7.36315765504763 | **PASS** |
| lm6 turning point (USD) | 1576.81 | 1576.8077250918625 | **PASS** |
| lm1 N | 913128.0 | 913128 | **PASS** |
| lm2 N | 913128.0 | 913128 | **PASS** |
| lm5 N | 913128.0 | 913128 | **PASS** |
| lm8 N | 891246.0 | 891246 | **PASS** |
| logit coef c_log_gdp_pc | -1.0265 | -1.0264596046363355 | **PASS** |
| logit p c_log_gdp_pc | 0.0 | 4.83744097473589e-07 | **PASS** |
| logit coef c_log_gdp_pc_sq | -0.2603 | -0.26030350423674997 | **PASS** |
| logit p_sq | 0.0226 | 0.022588578752180465 | **PASS** |
| logit AME sq | -0.0398 | -0.0397956469793404 | **PASS** |
| logit AME sq p | 0.0183 | 0.0183181349022087 | **PASS** |
| Table9 logit coef sq | -0.2603 | -0.26030350423674997 | **PASS** |
| Table9 PPML global coef sq | -0.2318 | -0.23181951551464502 | **PASS** |
| Table9 PPML global p sq | 0.2417 | 0.24171444516447949 | **PASS** |
| Table9 PPML Kiva-only coef sq | -0.0698 | -0.06981308363001369 | **PASS** |
| Table9 PPML Kiva-only p sq | 0.53 | 0.529994384566141 | **PASS** |
| PPML global N | 1020.0 | 1020 | **PASS** |
| PPML Kiva-only N | 369.0 | 369 | **PASS** |
| utest m6 t_low | 1.079781 | 1.07978118095743 | **PASS** |
| utest m6 t_high | -1.478231 | -1.4782306582242797 | **PASS** |
| utest lm6 t_low | -5.751691 | -5.751691426421615 | **PASS** |
| utest lm6 t_high | 10.953801 | 10.953800839045352 | **PASS** |
| utest logit t_low | 1.065149 | 1.0651493071596214 | **PASS** |
| utest logit t_high | -3.028234 | -3.028233927189949 | **PASS** |
| utest logit shape_confirmed | False | False | **PASS** |
| Table7 c_log_gdp_pc_sq country_year_se | 0.028 | 0.028 | **PASS** |
| Table7 c_log_gdp_pc_sq country_se | 0.0561 | 0.0561 | **PASS** |
| US share of loans (2c file, informational) | 0.9 | (not independently recomputed; single descriptive stat) | **INFO** |
| Table12 (1) baseline coef sq | 0.2447 | 0.2447 | **PASS** |
| Table12 (2) excl US coef sq | 0.3322 | 0.3322 | **PASS** |
| Table12 (3) relative coef sq | 0.2447 | 0.2447 | **PASS** |
| Table12 (4) sector coef sq | 0.234 | 0.234 | **PASS** |
| lm6_rel_no_linear coef sq | 0.1476 | 0.14762536083023803 | **PASS** |
| lm6_rel_no_linear p sq | 0.0017 | 0.0017453744398424208 | **PASS** |
| FWL: col1 linear - 1 | -0.794482 | -0.7944821794438243 | **PASS** |
| FWL: col3 linear coef | -0.794482 | -0.7944821794428554 | **PASS** |
| Table13 (1) lm6 baseline t_low | -5.751691 | -5.751691426399715 | **PASS** |
| Table13 (1) lm6 baseline t_high | 10.953801 | 10.95380083899162 | **PASS** |
| Table13 (2) Excl. US t_low | -4.867803 | -4.867803229930973 | **PASS** |
| Table13 (2) Excl. US t_high | 7.128978 | 7.128977736270433 | **PASS** |
| Table13 (3) Relative size t_low | -12.193948 | -12.193947933953794 | **PASS** |
| Table13 (3) Relative size t_high | 4.749906 | 4.749905862990816 | **PASS** |
| Table13 (4) Sector FE t_low | -5.649737 | -5.649736577222124 | **PASS** |
| Table13 (4) Sector FE t_high | 11.070625 | 11.070625460809724 | **PASS** |
| Table1 log_gdp_pc mean | 7.834 | 7.8341 | **PASS** |
| Table1 log_total_loan_amount N | 357.0 | 357.0 | **PASS** |
| Table2 Low development mean_log_loan | 12.806 | 12.8056 | **PASS** |
| Table2 Middle development mean_log_loan | 13.435 | 13.4355 | **PASS** |
| Table2 High development mean_log_loan | 12.776 | 12.7757 | **PASS** |
| TableA1 present | True | True | **PASS** |
| entry_rate decile 1 | 0.647 | 0.6471 | **PASS** |
| entry_rate decile 2 | 0.716 | 0.7157 | **PASS** |
| entry_rate decile 4 | 0.5 | 0.5 | **PASS** |
| entry_rate decile 8 | 0.01 | 0.0098 | **PASS** |
| entry_rate decile 9 | 0.069 | 0.0686 | **PASS** |
| entry_rate decile 10 | 0.049 | 0.049 | **PASS** |
