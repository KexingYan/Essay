"""
Re-estimates every model used in paper_publication_version.ipynb (v1.2), from the same source
CSVs and the same formula strings/clustering choices as the notebook, and renders:
  - paper/tables/table*.tex   (booktabs LaTeX, self-contained `table` environments)
  - paper/figures/figure*.pdf (vector PDF, regenerated from the same plotting code)
  - paper/tables/_key_numbers.json (machine-readable numbers, for verify_against_notebook.py)

This script does not read any notebook output text; it recomputes everything from
outputs/*.csv using the identical model specifications. Cross-checking against the notebook's
own stored outputs happens separately in verify_against_notebook.py -> paper/ASSET_CHECK.md.
"""
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
TABLES = Path(__file__).resolve().parent / "tables"
FIGURES = Path(__file__).resolve().parent / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

KEY_NUMBERS = {}

# ---------------------------------------------------------------------------
# Section 4 helper functions (verbatim from the notebook's Empirical Strategy cell)
# ---------------------------------------------------------------------------

def fit_ols(formula, data, se=None, cluster_col=None):
    if se == "cluster" and cluster_col is None:
        raise ValueError("cluster_col must be provided when se='cluster'.")
    model = smf.ols(formula=formula, data=data, missing="drop")
    used_rows = model.data.row_labels
    if se == "cluster":
        groups = data.loc[used_rows, cluster_col]
        result = model.fit(cov_type="cluster", cov_kwds={"groups": groups})
    else:
        result = model.fit()
    return result


def sample_audit(data, cols):
    cols = [c for c in cols if c in data.columns]
    used = data[cols].dropna().copy()
    return pd.Series({
        "obs": len(used),
        "countries": used["country_code"].nunique() if "country_code" in used.columns else np.nan,
        "years": used["year"].nunique() if "year" in used.columns else np.nan,
        "mean_log_gdp_pc": used["log_gdp_pc"].mean() if "log_gdp_pc" in used.columns else np.nan,
    })


def interaction_margins(model, x_var, z_var, z_values):
    inter = f"{x_var}:{z_var}"
    b_x, b_xz = model.params[x_var], model.params[inter]
    cov = model.cov_params()
    var_x, var_xz, cov_x_xz = cov.loc[x_var, x_var], cov.loc[inter, inter], cov.loc[x_var, inter]
    rows = []
    for label, z in z_values.items():
        me = b_x + b_xz * z
        se = np.sqrt(var_x + (z ** 2) * var_xz + 2 * z * cov_x_xz)
        t = me / se
        p = 2 * (1 - stats.norm.cdf(abs(t)))
        rows.append({"level": label, "value": z, "marginal_effect": me, "se": se, "p_value": p})
    return pd.DataFrame(rows)


def lind_mehlum_utest(model, b1_name, b2_name, x_min, x_max, alpha=0.05):
    b1, b2 = model.params[b1_name], model.params[b2_name]
    cov = model.cov_params()
    var_b1, var_b2 = cov.loc[b1_name, b1_name], cov.loc[b2_name, b2_name]
    cov_b1b2 = cov.loc[b1_name, b2_name]

    slope_lo = b1 + 2 * b2 * x_min
    slope_hi = b1 + 2 * b2 * x_max
    se_lo = np.sqrt(var_b1 + (2 * x_min) ** 2 * var_b2 + 2 * (2 * x_min) * cov_b1b2)
    se_hi = np.sqrt(var_b1 + (2 * x_max) ** 2 * var_b2 + 2 * (2 * x_max) * cov_b1b2)
    t_lo, t_hi = slope_lo / se_lo, slope_hi / se_hi

    opposite_signs = (slope_lo * slope_hi) < 0
    u_test_t = min(abs(t_lo), abs(t_hi))
    u_test_p = 1 - stats.norm.cdf(u_test_t)
    shape_confirmed = bool(opposite_signs and (u_test_p < alpha))

    z = stats.norm.ppf(1 - alpha / 2)
    A = b2 ** 2 - z ** 2 * var_b2
    B = b1 * b2 - z ** 2 * cov_b1b2
    C = b1 ** 2 - z ** 2 * var_b1
    disc = B ** 2 - A * C
    x0 = -b1 / (2 * b2)
    if A > 0 and disc >= 0:
        r1, r2 = (B - np.sqrt(disc)) / A, (B + np.sqrt(disc)) / A
        x0_ci = tuple(sorted([-r1 / 2, -r2 / 2]))
        fieller_valid = True
    else:
        x0_ci = (-np.inf, np.inf)
        fieller_valid = False

    return {
        "slope_low": slope_lo, "t_low": t_lo,
        "slope_high": slope_hi, "t_high": t_hi,
        "opposite_signs": opposite_signs,
        "u_test_t": u_test_t, "u_test_p": u_test_p,
        "shape_confirmed": shape_confirmed,
        "turning_point_centered": x0, "turning_point_ci_centered": x0_ci, "fieller_valid": fieller_valid,
    }


# ---------------------------------------------------------------------------
# LaTeX rendering helpers
# ---------------------------------------------------------------------------

def stars(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def esc(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


COEF_LABELS = {
    "Intercept": "Constant",
    "log_gdp_pc": "Log GDP per capita",
    "c_log_gdp_pc": "Log GDP per capita (centered)",
    "c_log_gdp_pc_sq": "Log GDP per capita\\textsuperscript{2} (centered)",
    "institutional_pca1": "Institutional quality (PCA1)",
    "institutional_index": "Institutional quality index",
    "financial_access_index": "Financial access index",
    "log_population": "Log population",
    "log_gdp_pc:institutional_pca1": "Log GDP per capita $\\times$ institutional quality",
}


def write_table_file(name, body):
    path = TABLES / f"{name}.tex"
    path.write_text(body)


def render_regression_table(models, col_labels, coef_order, title, label, notes,
                             extra_lines=None, decimals=3, fe_flags=None, se_note="",
                             stat_rows=("N",)):
    """models: list of fitted statsmodels results (OLS or GLM/Logit).
    coef_order: list of coefficient names, in display order, to include as rows.
    fe_flags: dict[row_label] -> list of "Yes"/"No" aligned with models, appended as extra lines.
    """
    ncol = len(models)
    colspec = "l" + "c" * ncol
    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{" + title + "}")
    lines.append(r"\label{" + label + "}")
    lines.append(r"\begin{tabular}{" + colspec + "}")
    lines.append(r"\toprule")
    lines.append(" & " + " & ".join(col_labels) + r" \\")
    lines.append(r"\midrule")

    for cname in coef_order:
        label_txt = COEF_LABELS.get(cname, esc(cname))
        coef_cells, se_cells = [], []
        any_present = False
        for m in models:
            if cname in m.params.index:
                any_present = True
                c = m.params[cname]
                p = m.pvalues[cname]
                se = m.bse[cname]
                coef_cells.append(f"{c:.{decimals}f}{stars(p)}")
                se_cells.append(f"({se:.{decimals}f})")
            else:
                coef_cells.append("")
                se_cells.append("")
        if not any_present:
            continue
        lines.append(label_txt + " & " + " & ".join(coef_cells) + r" \\")
        lines.append(" & " + " & ".join(se_cells) + r" \\")

    lines.append(r"\midrule")
    if fe_flags:
        for flabel, flags in fe_flags.items():
            lines.append(flabel + " & " + " & ".join(flags) + r" \\")

    for stat in stat_rows:
        cells = []
        for m in models:
            if stat == "N":
                cells.append(f"{int(m.nobs):,}")
            elif stat == "R2":
                cells.append(f"{m.rsquared:.3f}" if hasattr(m, "rsquared") else "")
            elif stat == "PseudoR2":
                cells.append(f"{m.prsquared:.3f}" if hasattr(m, "prsquared") else "")
        stat_label = {"N": "Observations", "R2": "$R^2$", "PseudoR2": "Pseudo $R^2$"}[stat]
        lines.append(stat_label + " & " + " & ".join(cells) + r" \\")

    if extra_lines:
        for elabel, evals in extra_lines.items():
            lines.append(elabel + " & " + " & ".join(evals) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\par\smallskip\footnotesize " + notes + " Standard errors in parentheses. " +
                 se_note + " * $p<0.1$; ** $p<0.05$; *** $p<0.01$.")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def render_df_table(df, title, label, notes, index_label="", decimals=None, col_labels=None):
    cols = list(df.columns)
    if col_labels is None:
        col_labels = [esc(c) for c in cols]
    colspec = "l" + "c" * len(cols)
    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(r"\caption{" + title + "}")
    lines.append(r"\label{" + label + "}")
    lines.append(r"\resizebox{\textwidth}{!}{%")
    lines.append(r"\begin{tabular}{" + colspec + "}")
    lines.append(r"\toprule")
    lines.append(esc(index_label) + " & " + " & ".join(col_labels) + r" \\")
    lines.append(r"\midrule")
    for idx, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, (int, np.integer)):
                cells.append(f"{v:,}")
            elif isinstance(v, (float, np.floating)):
                d = decimals if decimals is not None else 3
                cells.append(f"{v:.{d}f}")
            else:
                cells.append(esc(v))
        lines.append(esc(idx) + " & " + " & ".join(cells) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}%")
    lines.append(r"}")
    lines.append(r"\par\smallskip\footnotesize " + notes)
    lines.append(r"\end{table}")
    return "\n".join(lines)


# ===========================================================================
# DATA LOADING (identical source files to the notebook)
# ===========================================================================
reg = pd.read_csv(ROOT / "outputs" / "final_panel_country_year.csv")
for col in ["total_loan_amount", "log_total_loan_amount", "log_gdp_pc", "institutional_pca1",
            "institutional_index", "financial_access_index", "population", "log_population",
            "poverty_rate", "year"]:
    if col in reg.columns:
        reg[col] = pd.to_numeric(reg[col], errors="coerce")
reg["country_code"] = reg["country_code"].astype(str).str.strip().str.upper()
reg["c_log_gdp_pc"] = reg["log_gdp_pc"] - reg["log_gdp_pc"].mean()
reg["c_log_gdp_pc_sq"] = reg["c_log_gdp_pc"] ** 2

loan = pd.read_csv(ROOT / "outputs" / "final_panel_loan_level.csv")
loan_reg = loan.copy()
loan_reg["c_log_gdp_pc"] = loan_reg["log_gdp_pc"] - loan_reg["log_gdp_pc"].mean()
loan_reg["c_log_gdp_pc_sq"] = loan_reg["c_log_gdp_pc"] ** 2

gpanel = pd.read_csv(ROOT / "outputs" / "final_panel_global_extensive.csv")

loan_2c = pd.read_csv(ROOT / "outputs" / "final_panel_loan_level_augmented_2c.csv")
loan_2c["c_log_gdp_pc"] = loan_2c["log_gdp_pc"] - loan_2c["log_gdp_pc"].mean()
loan_2c["c_log_gdp_pc_sq"] = loan_2c["c_log_gdp_pc"] ** 2

year_coverage = pd.read_csv(ROOT / "outputs" / "table_year_month_coverage.csv")

KEY_NUMBERS["n_reg"] = len(reg)
KEY_NUMBERS["n_countries_reg"] = int(reg["country_code"].nunique())
KEY_NUMBERS["n_loan"] = len(loan_reg)
KEY_NUMBERS["n_gpanel"] = len(gpanel)
KEY_NUMBERS["n_gpanel_zero"] = int((gpanel["kiva_active"] == 0).sum())

print(f"reg: {len(reg)} rows, {reg['country_code'].nunique()} countries")
print(f"loan_reg: {len(loan_reg)} rows")
print(f"gpanel: {len(gpanel)} rows, {int(gpanel['kiva_active'].sum())} active, "
      f"{int((gpanel['kiva_active']==0).sum())} zero")

# ===========================================================================
# COUNTRY-YEAR MODELS (Section 5.1 -> Tables 3, 3b, 4)
# ===========================================================================
f1 = "log_total_loan_amount ~ log_gdp_pc + log_population"
f2 = "log_total_loan_amount ~ log_gdp_pc + institutional_pca1 + log_population"
f3 = "log_total_loan_amount ~ log_gdp_pc + institutional_pca1 + log_population + C(year)"
f4 = "log_total_loan_amount ~ log_gdp_pc * institutional_pca1 + log_population + C(year)"
m1 = fit_ols(f1, reg, se="cluster", cluster_col="country_code")
m2 = fit_ols(f2, reg, se="cluster", cluster_col="country_code")
m3 = fit_ols(f3, reg, se="cluster", cluster_col="country_code")
m4 = fit_ols(f4, reg, se="cluster", cluster_col="country_code")

f5 = "log_total_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1 + log_population"
f6 = "log_total_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1 + log_population + C(year)"
f7 = "log_total_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_index + log_population + C(year)"
f8 = "log_total_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + financial_access_index + log_population + C(year)"
m5 = fit_ols(f5, reg, se="cluster", cluster_col="country_code")
m6 = fit_ols(f6, reg, se="cluster", cluster_col="country_code")
m7 = fit_ols(f7, reg, se="cluster", cluster_col="country_code")
m8 = fit_ols(f8, reg, se="cluster", cluster_col="country_code")

KEY_NUMBERS["m5"] = {"c_log_gdp_pc": m5.params["c_log_gdp_pc"], "c_log_gdp_pc_sq": m5.params["c_log_gdp_pc_sq"],
                      "p_sq": m5.pvalues["c_log_gdp_pc_sq"], "N": int(m5.nobs)}
KEY_NUMBERS["m6"] = {"c_log_gdp_pc": m6.params["c_log_gdp_pc"], "p": m6.pvalues["c_log_gdp_pc"],
                      "c_log_gdp_pc_sq": m6.params["c_log_gdp_pc_sq"], "p_sq": m6.pvalues["c_log_gdp_pc_sq"],
                      "N": int(m6.nobs)}
KEY_NUMBERS["m7"] = {"c_log_gdp_pc_sq": m7.params["c_log_gdp_pc_sq"], "p_sq": m7.pvalues["c_log_gdp_pc_sq"], "N": int(m7.nobs)}
KEY_NUMBERS["m8"] = {"c_log_gdp_pc_sq": m8.params["c_log_gdp_pc_sq"], "p_sq": m8.pvalues["c_log_gdp_pc_sq"], "N": int(m8.nobs)}

mean_log_gdp = reg["log_gdp_pc"].mean()
b1_5, b2_5 = m5.params["c_log_gdp_pc"], m5.params["c_log_gdp_pc_sq"]
if b2_5 < 0:
    tp_centered = -b1_5 / (2 * b2_5)
    tp_log = mean_log_gdp + tp_centered
    KEY_NUMBERS["m5_turning_point_log_gdp"] = tp_log
    KEY_NUMBERS["m5_turning_point_usd"] = float(np.exp(tp_log))

table3 = render_regression_table(
    [m1, m2, m3, m4], ["(1)", "(2)", "(3)", "(4)"],
    ["log_gdp_pc", "institutional_pca1", "log_population", "log_gdp_pc:institutional_pca1", "Intercept"],
    "Country-Year: Linear and Interaction Specifications (Total Lending Volume)",
    "tab:table3",
    "Dependent variable: log total Kiva lending volume, country-year level.",
    fe_flags={"Year fixed effects": ["No", "No", "Yes", "Yes"]},
    se_note="Country-clustered standard errors.",
)
write_table_file("table3_country_linear", table3)

table4 = render_regression_table(
    [m5, m6, m7, m8], ["(5)", "(6)", "(7)", "(8)"],
    ["c_log_gdp_pc", "c_log_gdp_pc_sq", "institutional_pca1", "institutional_index",
     "financial_access_index", "log_population", "Intercept"],
    "Country-Year: Quadratic and Robustness Specifications (Total Lending Volume)",
    "tab:table4",
    "Dependent variable: log total Kiva lending volume, country-year level. Log GDP per capita is centered.",
    fe_flags={"Year fixed effects": ["No", "Yes", "Yes", "Yes"]},
    se_note="Country-clustered standard errors.",
)
write_table_file("table4_country_quadratic", table4)

z_levels = {"25th percentile": reg["institutional_pca1"].quantile(0.25),
            "Mean": reg["institutional_pca1"].mean(),
            "75th percentile": reg["institutional_pca1"].quantile(0.75)}
margins3b = interaction_margins(m4, "log_gdp_pc", "institutional_pca1", z_levels)
KEY_NUMBERS["table3b"] = margins3b.round(4).to_dict("records")
margins3b_disp = margins3b.set_index("level")[["value", "marginal_effect", "se", "p_value"]]
margins3b_disp.columns = ["Institutional quality level", "Marginal effect", "SE", "p-value"]
table3b = render_df_table(
    margins3b_disp, "Marginal Effect of Log GDP per Capita on Log Total Lending Volume (Model 4)",
    "tab:table3b",
    "Delta-method marginal effects of log GDP per capita at percentiles of institutional quality, model (4).",
    index_label="",
)
write_table_file("table3b_margins", table3b)

# ===========================================================================
# LOAN-LEVEL MODELS (Section 5.2 -> Tables 5, 5b, 6, 7)
# ===========================================================================
lf1 = "log_loan_amount ~ log_gdp_pc + log_population"
lf2 = "log_loan_amount ~ log_gdp_pc + institutional_pca1 + log_population"
lf3 = "log_loan_amount ~ log_gdp_pc + institutional_pca1 + log_population + C(year)"
lf4 = "log_loan_amount ~ log_gdp_pc * institutional_pca1 + log_population + C(year)"
lf5 = "log_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1 + log_population"
lf6 = "log_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1 + log_population + C(year)"
lf7 = "log_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_index + log_population + C(year)"
lf8 = "log_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + financial_access_index + log_population + C(year)"

lm1 = fit_ols(lf1, loan_reg, se="cluster", cluster_col="country_year_id")
lm2 = fit_ols(lf2, loan_reg, se="cluster", cluster_col="country_year_id")
lm3 = fit_ols(lf3, loan_reg, se="cluster", cluster_col="country_year_id")
lm4 = fit_ols(lf4, loan_reg, se="cluster", cluster_col="country_year_id")
lm5 = fit_ols(lf5, loan_reg, se="cluster", cluster_col="country_year_id")
lm6 = fit_ols(lf6, loan_reg, se="cluster", cluster_col="country_year_id")
lm7 = fit_ols(lf7, loan_reg, se="cluster", cluster_col="country_year_id")
lm8 = fit_ols(lf8, loan_reg, se="cluster", cluster_col="country_year_id")

KEY_NUMBERS["lm1_N"] = int(lm1.nobs)
KEY_NUMBERS["lm2_N"] = int(lm2.nobs)
KEY_NUMBERS["lm5_N"] = int(lm5.nobs)
KEY_NUMBERS["lm8_N"] = int(lm8.nobs)
KEY_NUMBERS["lm6"] = {"c_log_gdp_pc": lm6.params["c_log_gdp_pc"], "c_log_gdp_pc_sq": lm6.params["c_log_gdp_pc_sq"],
                       "p_sq": lm6.pvalues["c_log_gdp_pc_sq"], "N": int(lm6.nobs)}

loan_mean_log_gdp = loan_reg["log_gdp_pc"].mean()
lb1, lb2 = lm6.params["c_log_gdp_pc"], lm6.params["c_log_gdp_pc_sq"]
if lb2 > 0:
    loan_tp_centered = -lb1 / (2 * lb2)
    loan_tp_log = loan_mean_log_gdp + loan_tp_centered
    KEY_NUMBERS["lm6_turning_point_log_gdp"] = loan_tp_log
    KEY_NUMBERS["lm6_turning_point_usd"] = float(np.exp(loan_tp_log))

table5 = render_regression_table(
    [lm1, lm2, lm3, lm4], ["(1)", "(2)", "(3)", "(4)"],
    ["log_gdp_pc", "institutional_pca1", "log_population", "log_gdp_pc:institutional_pca1", "Intercept"],
    "Loan-Level: Linear and Interaction Specifications (Loan Size)",
    "tab:table5",
    "Dependent variable: log individual loan amount.",
    fe_flags={"Year fixed effects": ["No", "No", "Yes", "Yes"]},
    se_note="Country-year-clustered standard errors.",
)
write_table_file("table5_loan_linear", table5)

loan_z_levels = {"25th percentile": loan_reg["institutional_pca1"].quantile(0.25),
                  "Mean": loan_reg["institutional_pca1"].mean(),
                  "75th percentile": loan_reg["institutional_pca1"].quantile(0.75)}
margins5b = interaction_margins(lm4, "log_gdp_pc", "institutional_pca1", loan_z_levels)
KEY_NUMBERS["table5b"] = margins5b.round(4).to_dict("records")
margins5b_disp = margins5b.set_index("level")[["value", "marginal_effect", "se", "p_value"]]
margins5b_disp.columns = ["Institutional quality level", "Marginal effect", "SE", "p-value"]
table5b = render_df_table(
    margins5b_disp, "Marginal Effect of Log GDP per Capita on Log Loan Size (Model 4, Loan Level)",
    "tab:table5b",
    "Delta-method marginal effects of log GDP per capita at percentiles of institutional quality, loan-level model (4).",
    index_label="",
)
write_table_file("table5b_margins", table5b)

table6 = render_regression_table(
    [lm5, lm6, lm7, lm8], ["(5)", "(6)", "(7)", "(8)"],
    ["c_log_gdp_pc", "c_log_gdp_pc_sq", "institutional_pca1", "institutional_index",
     "financial_access_index", "log_population", "Intercept"],
    "Loan-Level: Quadratic and Robustness Specifications (Loan Size)",
    "tab:table6",
    "Dependent variable: log individual loan amount. Log GDP per capita is centered.",
    fe_flags={"Year fixed effects": ["No", "Yes", "Yes", "Yes"]},
    se_note="Country-year-clustered standard errors.",
)
write_table_file("table6_loan_quadratic", table6)

lm6_country_cluster = fit_ols(lf6, loan_reg, se="cluster", cluster_col="country_code")
compare_rows = [r for r in lm6.bse.index if "c_log_gdp_pc" in r or "log_population" in r or "institutional_pca1" in r]
loan_compare = pd.DataFrame({
    "Country-year-clustered SE": lm6.bse.loc[compare_rows],
    "Country-clustered SE": lm6_country_cluster.bse.loc[compare_rows],
})
loan_compare.index = [COEF_LABELS.get(i, i) for i in loan_compare.index]
KEY_NUMBERS["table7"] = loan_compare.round(4).to_dict()
table7 = render_df_table(
    loan_compare, "Loan-Level Standard Errors: Country-Year vs. Country Clustering", "tab:table7",
    "Coefficients are from model (6) of Table \\ref{tab:table6} (lm6); only standard errors differ by clustering level.",
    index_label="Covariate", decimals=4,
)
write_table_file("table7_cluster_compare", table7)

# ===========================================================================
# EXTENSIVE / INTENSIVE MARGIN (Section 5.3 -> Tables 8, 9; Figure 8)
# ===========================================================================
logit_formula = "kiva_active ~ c_log_gdp_pc + c_log_gdp_pc_sq + log_population + C(year)"
logit_model = smf.logit(logit_formula, data=gpanel, missing="drop")
logit_rows = logit_model.data.row_labels
logit_groups = gpanel.loc[logit_rows, "iso3"]
logit_fit = logit_model.fit(cov_type="cluster", cov_kwds={"groups": logit_groups}, disp=0)
logit_margeff = logit_fit.get_margeff()
logit_ame = logit_margeff.summary_frame()["dy/dx"]
logit_ame_se = logit_margeff.summary_frame()["Std. Err."]
logit_ame_p = logit_margeff.summary_frame()["Pr(>|z|)"]

KEY_NUMBERS["logit"] = {
    "c_log_gdp_pc": logit_fit.params["c_log_gdp_pc"], "p": logit_fit.pvalues["c_log_gdp_pc"],
    "c_log_gdp_pc_sq": logit_fit.params["c_log_gdp_pc_sq"], "p_sq": logit_fit.pvalues["c_log_gdp_pc_sq"],
    "ame_sq": float(logit_ame.get("c_log_gdp_pc_sq", np.nan)),
    "ame_sq_p": float(logit_ame_p.get("c_log_gdp_pc_sq", np.nan)),
    "N": int(logit_fit.nobs),
}

key_rows = ["c_log_gdp_pc", "c_log_gdp_pc_sq", "log_population"]
table8_rows = []
for r in key_rows:
    coef, p_c, se_c = logit_fit.params[r], logit_fit.pvalues[r], logit_fit.bse[r]
    ame = logit_ame.get(r, np.nan)
    ame_p = logit_ame_p.get(r, np.nan)
    ame_se = logit_ame_se.get(r, np.nan)
    table8_rows.append([COEF_LABELS.get(r, r), f"{coef:.3f}{stars(p_c)}", f"({se_c:.3f})",
                         f"{ame:.3f}{stars(ame_p)}", f"({ame_se:.3f})"])
table8_lines = [
    r"\begin{table}[htbp]", r"\centering",
    r"\caption{Extensive Margin: Logit Coefficients and Average Marginal Effects}",
    r"\label{tab:table8}",
    r"\begin{tabular}{lcc}", r"\toprule",
    r" & Coefficient & Average marginal effect \\", r"\midrule",
]
for row in table8_rows:
    table8_lines.append(f"{row[0]} & {row[1]} & {row[3]} \\\\")
    table8_lines.append(f" & {row[2]} & {row[4]} \\\\")
table8_lines += [
    r"\midrule",
    f"Year fixed effects & Yes & Yes \\\\",
    f"Observations & {int(logit_fit.nobs):,} & {int(logit_fit.nobs):,} \\\\",
    f"Pseudo $R^2$ & {logit_fit.prsquared:.3f} & \\\\",
    r"\bottomrule", r"\end{tabular}",
    r"\par\smallskip\footnotesize Dependent variable: indicator for Kiva active in a country-year, "
    r"global panel including zero-lending country-years. Country-clustered standard errors in "
    r"parentheses. Log GDP per capita is centered. * $p<0.1$; ** $p<0.05$; *** $p<0.01$.",
    r"\end{table}",
]
write_table_file("table8_logit", "\n".join(table8_lines))

# PPML (intensive margin)
gpanel["total_loan_amount_k"] = gpanel["total_loan_amount"] / 1000.0
ppml_global_formula = "total_loan_amount_k ~ c_log_gdp_pc + c_log_gdp_pc_sq + log_population + C(year)"
ppml_global_model = smf.glm(ppml_global_formula, data=gpanel, family=sm.families.Poisson(), missing="drop")
ppml_global_rows = ppml_global_model.data.row_labels
ppml_global_groups = gpanel.loc[ppml_global_rows, "iso3"]
ppml_global_fit = ppml_global_model.fit(cov_type="cluster", cov_kwds={"groups": ppml_global_groups})

kiva_only = gpanel[gpanel["kiva_active"] == 1].copy()
ppml_kiva_formula = "total_loan_amount_k ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1 + log_population + C(year)"
ppml_kiva_model = smf.glm(ppml_kiva_formula, data=kiva_only, family=sm.families.Poisson(), missing="drop")
ppml_kiva_rows = ppml_kiva_model.data.row_labels
ppml_kiva_groups = kiva_only.loc[ppml_kiva_rows, "iso3"]
ppml_kiva_fit = ppml_kiva_model.fit(cov_type="cluster", cov_kwds={"groups": ppml_kiva_groups})

KEY_NUMBERS["ppml_global"] = {"c_log_gdp_pc_sq": ppml_global_fit.params["c_log_gdp_pc_sq"],
                               "p_sq": ppml_global_fit.pvalues["c_log_gdp_pc_sq"], "N": int(ppml_global_fit.nobs)}
KEY_NUMBERS["ppml_kiva"] = {"c_log_gdp_pc_sq": ppml_kiva_fit.params["c_log_gdp_pc_sq"],
                             "p_sq": ppml_kiva_fit.pvalues["c_log_gdp_pc_sq"], "N": int(ppml_kiva_fit.nobs)}

table9_key_rows = ["c_log_gdp_pc", "c_log_gdp_pc_sq"]
table9 = pd.DataFrame({
    "Logit coef.": logit_fit.params.loc[table9_key_rows],
    "Logit p": logit_fit.pvalues.loc[table9_key_rows],
    "Logit AME": logit_ame.loc[table9_key_rows],
    "PPML (global) coef.": ppml_global_fit.params.loc[table9_key_rows],
    "PPML (global) p": ppml_global_fit.pvalues.loc[table9_key_rows],
    "PPML (Kiva-only) coef.": ppml_kiva_fit.params.loc[table9_key_rows],
    "PPML (Kiva-only) p": ppml_kiva_fit.pvalues.loc[table9_key_rows],
})
table9.index = [COEF_LABELS.get(i, i) for i in table9.index]
KEY_NUMBERS["table9"] = table9.round(4).to_dict()
table9_tex = render_df_table(
    table9, "Two Margins: Logit (Extensive) vs. PPML (Intensive), Development Terms", "tab:table9",
    "Logit: global panel including zero-lending country-years, country-clustered SE. PPML (global): "
    "same sample; PPML (Kiva-only): restricted to Kiva-active country-years. All models include year "
    "fixed effects and log population; PPML (Kiva-only) also includes institutional quality.",
    index_label="Covariate", decimals=4,
)
write_table_file("table9_two_margins", table9_tex)

# Entry rate by decile (also drives Figure 8)
gpanel["gdp_decile"] = pd.qcut(gpanel["log_gdp_pc"], 10, labels=False, duplicates="drop") + 1
entry_by_decile = gpanel.groupby("gdp_decile").agg(
    mean_log_gdp_pc=("log_gdp_pc", "mean"), entry_rate=("kiva_active", "mean"), n=("kiva_active", "size"),
)
KEY_NUMBERS["entry_by_decile"] = entry_by_decile.round(4).reset_index().to_dict("records")

# ===========================================================================
# LIND-MEHLUM U-TEST (Section 5.4 -> Table 10)
# ===========================================================================
utest_m6 = lind_mehlum_utest(m6, "c_log_gdp_pc", "c_log_gdp_pc_sq", reg["c_log_gdp_pc"].min(), reg["c_log_gdp_pc"].max())
utest_lm6 = lind_mehlum_utest(lm6, "c_log_gdp_pc", "c_log_gdp_pc_sq", loan_reg["c_log_gdp_pc"].min(), loan_reg["c_log_gdp_pc"].max())
utest_logit = lind_mehlum_utest(logit_fit, "c_log_gdp_pc", "c_log_gdp_pc_sq", gpanel["c_log_gdp_pc"].min(), gpanel["c_log_gdp_pc"].max())

KEY_NUMBERS["utest_m6"] = {k: (v if not isinstance(v, tuple) else list(v)) for k, v in utest_m6.items()}
KEY_NUMBERS["utest_lm6"] = {k: (v if not isinstance(v, tuple) else list(v)) for k, v in utest_lm6.items()}
KEY_NUMBERS["utest_logit"] = {k: (v if not isinstance(v, tuple) else list(v)) for k, v in utest_logit.items()}


def fmt_ci(ci):
    if np.isfinite(ci[0]):
        return f"[{ci[0]:.3f}, {ci[1]:.3f}]"
    return "Unbounded"


utest_table = pd.DataFrame({
    "m6 (country-year, volume)": utest_m6,
    "lm6 (loan-level, size)": utest_lm6,
    "Logit (global, extensive margin)": utest_logit,
}).T
disp10 = pd.DataFrame({
    "Slope, low end": utest_table["slope_low"].astype(float),
    "$t$, low end": utest_table["t_low"].astype(float),
    "Slope, high end": utest_table["slope_high"].astype(float),
    "$t$, high end": utest_table["t_high"].astype(float),
    "U-test $p$": utest_table["u_test_p"].astype(float),
    "Shape confirmed": utest_table["shape_confirmed"].apply(lambda b: "Yes" if b else "No"),
    "Fieller 95\\% CI (turning point)": utest_table["turning_point_ci_centered"].apply(fmt_ci),
})
table10_lines = [
    r"\begin{table}[htbp]", r"\centering",
    r"\caption{Lind--Mehlum (2010) U-Test: m6, lm6, and the Extensive-Margin Logit}",
    r"\label{tab:table10}",
    r"\resizebox{\textwidth}{!}{%",
    r"\begin{tabular}{lccccccc}", r"\toprule",
    r"Model & Slope (low) & $t$ (low) & Slope (high) & $t$ (high) & U-test $p$ & Confirmed? & Fieller 95\% CI \\",
    r"\midrule",
]
for idx, row in disp10.iterrows():
    table10_lines.append(
        f"{esc(idx)} & {row['Slope, low end']:.3f} & {row['$t$, low end']:.3f} & "
        f"{row['Slope, high end']:.3f} & {row['$t$, high end']:.3f} & {row['U-test $p$']:.3f} & "
        f"{row['Shape confirmed']} & {row['Fieller 95\\% CI (turning point)']} \\\\"
    )
table10_lines += [
    r"\bottomrule", r"\end{tabular}%", r"}",
    r"\par\smallskip\footnotesize Slopes evaluated at the sample minimum and maximum of "
    r"(centered) log GDP per capita, with delta-method standard errors using each model's full "
    r"clustered covariance matrix. The U-test statistic is the weaker of the two end $t$-statistics "
    r"(one-sided); shape is confirmed only if both ends are individually significant at the 5\% level "
    r"with opposite-signed slopes. The Logit row is evaluated on the linear-index (log-odds) scale.",
    r"\end{table}",
]
write_table_file("table10_lind_mehlum", "\n".join(table10_lines))

# ===========================================================================
# ROBUSTNESS (Section 6 -> Tables 11, 12, 13)
# ===========================================================================
reg_1417 = reg[reg["year"] >= 2014].copy()
loan_1417 = loan_reg[loan_reg["year"] >= 2014].copy()
m6_1417 = fit_ols(f6, reg_1417, se="cluster", cluster_col="country_code")
lm6_1417 = fit_ols(lf6, loan_1417, se="cluster", cluster_col="country_year_id")

sample_period_table = pd.DataFrame({
    "m6, full sample (2013-2017)": {
        "c_log_gdp_pc": m6.params["c_log_gdp_pc"], "p": m6.pvalues["c_log_gdp_pc"],
        "c_log_gdp_pc_sq": m6.params["c_log_gdp_pc_sq"], "p (sq)": m6.pvalues["c_log_gdp_pc_sq"], "N": int(m6.nobs)},
    "m6, 2014-2017 only": {
        "c_log_gdp_pc": m6_1417.params["c_log_gdp_pc"], "p": m6_1417.pvalues["c_log_gdp_pc"],
        "c_log_gdp_pc_sq": m6_1417.params["c_log_gdp_pc_sq"], "p (sq)": m6_1417.pvalues["c_log_gdp_pc_sq"], "N": int(m6_1417.nobs)},
    "lm6, full sample (2013-2017)": {
        "c_log_gdp_pc": lm6.params["c_log_gdp_pc"], "p": lm6.pvalues["c_log_gdp_pc"],
        "c_log_gdp_pc_sq": lm6.params["c_log_gdp_pc_sq"], "p (sq)": lm6.pvalues["c_log_gdp_pc_sq"], "N": int(lm6.nobs)},
    "lm6, 2014-2017 only": {
        "c_log_gdp_pc": lm6_1417.params["c_log_gdp_pc"], "p": lm6_1417.pvalues["c_log_gdp_pc"],
        "c_log_gdp_pc_sq": lm6_1417.params["c_log_gdp_pc_sq"], "p (sq)": lm6_1417.pvalues["c_log_gdp_pc_sq"], "N": int(lm6_1417.nobs)},
}).T
KEY_NUMBERS["table11"] = sample_period_table.round(4).to_dict()
sample_period_table_disp = sample_period_table.rename(columns={
    "c_log_gdp_pc": "Linear coef.", "p": "$p$", "c_log_gdp_pc_sq": "Quadratic coef.", "p (sq)": "$p$ (sq.)"})
table11 = render_df_table(
    sample_period_table_disp, "Sample-Period Robustness: Full Sample vs. 2014--2017 Only", "tab:table11",
    "m6: country-year volume model; lm6: loan-level size model, both with year fixed effects.",
    index_label="Specification", decimals=4,
)
write_table_file("table11_sample_period", table11)

lf6_sector = "log_loan_amount ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1 + log_population + C(year) + C(sector_name)"
lf6_rel = "log_relative_loan_size ~ c_log_gdp_pc + c_log_gdp_pc_sq + institutional_pca1 + log_population + C(year)"
no_us_data = loan_2c[loan_2c["country_code"] != "US"].copy()
lm6_no_us = fit_ols(lf6, no_us_data, se="cluster", cluster_col="country_year_id")
lm6_rel = fit_ols(lf6_rel, loan_2c, se="cluster", cluster_col="country_year_id")
lm6_sector = fit_ols(lf6_sector, loan_2c, se="cluster", cluster_col="country_year_id")
lm6_on_2c_file = fit_ols(lf6, loan_2c, se="cluster", cluster_col="country_year_id")

lf6_rel_no_linear = "log_relative_loan_size ~ c_log_gdp_pc_sq + institutional_pca1 + log_population + C(year)"
lm6_rel_no_linear = fit_ols(lf6_rel_no_linear, loan_2c, se="cluster", cluster_col="country_year_id")
KEY_NUMBERS["lm6_rel_no_linear"] = {"c_log_gdp_pc_sq": lm6_rel_no_linear.params["c_log_gdp_pc_sq"],
                                     "p_sq": lm6_rel_no_linear.pvalues["c_log_gdp_pc_sq"], "N": int(lm6_rel_no_linear.nobs)}
KEY_NUMBERS["lm6_on_2c_file_c_log_gdp_pc"] = lm6_on_2c_file.params["c_log_gdp_pc"]
KEY_NUMBERS["lm6_rel_c_log_gdp_pc"] = lm6_rel.params["c_log_gdp_pc"]

robustness_2c_table = pd.DataFrame({
    "(1) Baseline (lm6)": {"c_log_gdp_pc": lm6_on_2c_file.params["c_log_gdp_pc"], "p": lm6_on_2c_file.pvalues["c_log_gdp_pc"],
                            "c_log_gdp_pc_sq": lm6_on_2c_file.params["c_log_gdp_pc_sq"], "p (sq)": lm6_on_2c_file.pvalues["c_log_gdp_pc_sq"], "N": int(lm6_on_2c_file.nobs)},
    "(2) Excluding US": {"c_log_gdp_pc": lm6_no_us.params["c_log_gdp_pc"], "p": lm6_no_us.pvalues["c_log_gdp_pc"],
                          "c_log_gdp_pc_sq": lm6_no_us.params["c_log_gdp_pc_sq"], "p (sq)": lm6_no_us.pvalues["c_log_gdp_pc_sq"], "N": int(lm6_no_us.nobs)},
    "(3) Relative loan size": {"c_log_gdp_pc": lm6_rel.params["c_log_gdp_pc"], "p": lm6_rel.pvalues["c_log_gdp_pc"],
                                "c_log_gdp_pc_sq": lm6_rel.params["c_log_gdp_pc_sq"], "p (sq)": lm6_rel.pvalues["c_log_gdp_pc_sq"], "N": int(lm6_rel.nobs)},
    "(4) Sector fixed effects": {"c_log_gdp_pc": lm6_sector.params["c_log_gdp_pc"], "p": lm6_sector.pvalues["c_log_gdp_pc"],
                                  "c_log_gdp_pc_sq": lm6_sector.params["c_log_gdp_pc_sq"], "p (sq)": lm6_sector.pvalues["c_log_gdp_pc_sq"], "N": int(lm6_sector.nobs)},
}).T
KEY_NUMBERS["table12"] = robustness_2c_table.round(4).to_dict()
robustness_2c_disp = robustness_2c_table.rename(columns={
    "c_log_gdp_pc": "Linear coef.", "p": "$p$", "c_log_gdp_pc_sq": "Quadratic coef.", "p (sq)": "$p$ (sq.)"})
table12 = render_df_table(
    robustness_2c_disp, "Loan-Level Robustness: lm6 Under Four Specifications", "tab:table12",
    "(3) Relative loan size regresses log(loan amount / local GDP per capita) on the same "
    "controls; because log GDP per capita already enters linearly, this reproduces (1) by a "
    "Frisch--Waugh--Lovell identity and is not independently informative about curvature (see text). "
    "All columns use country-year-clustered standard errors.",
    index_label="Specification", decimals=4,
)
write_table_file("table12_loan_robustness", table12)

x_min_2c, x_max_2c = loan_2c["c_log_gdp_pc"].min(), loan_2c["c_log_gdp_pc"].max()
x_min_no_us, x_max_no_us = no_us_data["c_log_gdp_pc"].min(), no_us_data["c_log_gdp_pc"].max()
utest_variants = {
    "(1) Baseline (lm6)": lind_mehlum_utest(lm6_on_2c_file, "c_log_gdp_pc", "c_log_gdp_pc_sq", x_min_2c, x_max_2c),
    "(2) Excluding US": lind_mehlum_utest(lm6_no_us, "c_log_gdp_pc", "c_log_gdp_pc_sq", x_min_no_us, x_max_no_us),
    "(3) Relative loan size": lind_mehlum_utest(lm6_rel, "c_log_gdp_pc", "c_log_gdp_pc_sq", x_min_2c, x_max_2c),
    "(4) Sector fixed effects": lind_mehlum_utest(lm6_sector, "c_log_gdp_pc", "c_log_gdp_pc_sq", x_min_2c, x_max_2c),
}
utest_variants_table = pd.DataFrame(utest_variants).T[["t_low", "t_high", "u_test_p", "shape_confirmed"]]
KEY_NUMBERS["table13"] = {k: {kk: (vv if not isinstance(vv, bool) else vv) for kk, vv in v.items()}
                           for k, v in utest_variants_table.round(4).to_dict("index").items()}
utest_variants_disp = utest_variants_table.rename(columns={
    "t_low": "$t$, low end", "t_high": "$t$, high end", "u_test_p": "U-test $p$"})
utest_variants_disp["shape_confirmed"] = utest_variants_disp["shape_confirmed"].apply(lambda b: "Yes" if b else "No")
utest_variants_disp = utest_variants_disp.rename(columns={"shape_confirmed": "Shape confirmed"})
table13 = render_df_table(
    utest_variants_disp, "Lind--Mehlum U-Test Applied to All Four Loan-Level Robustness Variants", "tab:table13",
    "One-sided U-test statistics for each column of Table \\ref{tab:table12}.",
    index_label="Specification", decimals=3,
)
write_table_file("table13_loan_robustness_utest", table13)

# ===========================================================================
# DESCRIPTIVE TABLES (Section 3 -> Tables 1, 2; Appendix -> Table A1)
# ===========================================================================
core_summary_vars = ["log_total_loan_amount", "log_gdp_pc", "institutional_pca1",
                      "institutional_index", "financial_access_index", "log_population", "poverty_rate"]
summary_table = reg[core_summary_vars].agg(["count", "mean", "std", "min", "median", "max"]).T
summary_table.columns = ["N", "Mean", "SD", "Min", "Median", "Max"]
summary_table.index = [COEF_LABELS.get(i, esc(i).replace("\\_", " ").title()) for i in summary_table.index]
KEY_NUMBERS["table1"] = summary_table.round(4).to_dict()
table1 = render_df_table(
    summary_table, "Summary Statistics (Country-Year Panel)", "tab:table1",
    "Country-year panel, $N=" + str(len(reg)) + "$ observations across " +
    str(reg["country_code"].nunique()) + " countries, 2013--2017.",
    index_label="Variable", decimals=3,
)
write_table_file("table1_summary_stats", table1)

tercile_cols = ["log_total_loan_amount", "log_gdp_pc", "institutional_pca1", "log_population"]
summary_df = reg[tercile_cols].dropna().copy()
summary_df["development_tercile"] = pd.qcut(summary_df["log_gdp_pc"], q=3,
    labels=["Low development", "Middle development", "High development"], duplicates="drop")
subgroup_table = summary_df.groupby("development_tercile", observed=False).agg(
    observations=("log_total_loan_amount", "size"), mean_log_loan=("log_total_loan_amount", "mean"),
    mean_log_gdp_pc=("log_gdp_pc", "mean"), mean_institution=("institutional_pca1", "mean"),
    mean_log_population=("log_population", "mean"))
KEY_NUMBERS["table2"] = subgroup_table.round(4).to_dict()
subgroup_table_disp = subgroup_table.rename(columns={
    "observations": "N", "mean_log_loan": "Mean log lending", "mean_log_gdp_pc": "Mean log GDP p.c.",
    "mean_institution": "Mean institutional quality", "mean_log_population": "Mean log population"})
table2 = render_df_table(
    subgroup_table_disp, "Lending Activity by Development Tercile", "tab:table2",
    "Terciles of log GDP per capita, country-year panel.",
    index_label="Development tercile", decimals=3,
)
write_table_file("table2_terciles", table2)

appendix_cov = year_coverage.rename(columns={
    "n_loans": "N loans", "total_loan_amount_usd": "Total loan amount (USD)", "n_countries": "N countries",
    "n_months_covered": "Months covered (of 12)", "min_monthly_loans": "Min monthly loans",
    "max_monthly_loans": "Max monthly loans", "pct_of_2014_n_loans": "N loans, \\% of 2014",
}).set_index("year")
KEY_NUMBERS["tableA1"] = appendix_cov.round(3).to_dict()
tableA1 = render_df_table(
    appendix_cov, "Year and Month Coverage of Raw Kiva Loan-Posting Data (2013--2017)", "tab:tableA1",
    "Coverage diagnostics computed directly from Kiva's raw loan-posting timestamps.",
    index_label="Year", decimals=1,
)
write_table_file("tableA1_year_coverage", tableA1)

# ===========================================================================
# FIGURES (regenerated as vector PDF; captions handled in main.tex, not on the plot)
# ===========================================================================
plt.rcParams.update({"font.size": 11})

# Figure 1
plot_df = reg[["log_gdp_pc", "log_total_loan_amount"]].replace([np.inf, -np.inf], np.nan).dropna()
x = plot_df["log_gdp_pc"].to_numpy(); y = plot_df["log_total_loan_amount"].to_numpy()
coef = np.polyfit(x, y, 2); poly = np.poly1d(coef)
x_grid = np.linspace(x.min(), x.max(), 200); y_grid = poly(x_grid)
low = lowess(y, x, frac=0.4, return_sorted=True)
descriptive_tp = -coef[1] / (2 * coef[0]) if coef[0] != 0 else np.nan
fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.scatter(x, y, alpha=0.35, s=14)
ax.plot(x_grid, y_grid, linewidth=2, label="Quadratic fit")
ax.plot(low[:, 0], low[:, 1], linewidth=2, label="LOWESS")
if np.isfinite(descriptive_tp) and x.min() <= descriptive_tp <= x.max():
    ax.axvline(descriptive_tp, linestyle="--", linewidth=1, color="grey")
ax.set_xlabel("Log GDP per capita"); ax.set_ylabel("Log total loan amount")
ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(FIGURES / "figure1_scatter_quadratic.pdf"); plt.close(fig)

# Figure 2
fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.hist(reg["log_total_loan_amount"].dropna(), bins=20)
ax.set_xlabel("Log Total Loan Amount"); ax.set_ylabel("Frequency")
fig.tight_layout(); fig.savefig(FIGURES / "figure2_hist_lending.pdf"); plt.close(fig)

# Figure 3
fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.hist(reg["log_gdp_pc"].dropna(), bins=20)
ax.set_xlabel("Log GDP per Capita"); ax.set_ylabel("Frequency")
fig.tight_layout(); fig.savefig(FIGURES / "figure3_hist_gdp.pdf"); plt.close(fig)

# Figure 4
plot_df4 = reg[["log_gdp_pc", "total_loan_amount", "population"]].replace([np.inf, -np.inf], np.nan).dropna().copy()
plot_df4 = plot_df4[plot_df4["population"] > 0].copy()
plot_df4["loan_per_100k"] = plot_df4["total_loan_amount"] / plot_df4["population"] * 100000
plot_df4["log_loan_per_100k"] = np.log(plot_df4["loan_per_100k"])
x4 = plot_df4["log_gdp_pc"].to_numpy(); y4 = plot_df4["log_loan_per_100k"].to_numpy()
coef4 = np.polyfit(x4, y4, 2); poly4 = np.poly1d(coef4)
x4_grid = np.linspace(x4.min(), x4.max(), 200)
fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.scatter(x4, y4, alpha=0.35, s=14)
ax.plot(x4_grid, poly4(x4_grid), linewidth=2)
ax.set_xlabel("Log GDP per capita"); ax.set_ylabel("Log loan amount per 100k people")
fig.tight_layout(); fig.savefig(FIGURES / "figure4_percapita.pdf"); plt.close(fig)

# Figures 5-7 (maps)
try:
    import geopandas as gpd
    map_df = reg.copy()
    map_df = map_df[map_df["population"].notna() & (map_df["population"] > 0)].copy()
    map_df["loan_per_100k"] = map_df["total_loan_amount"] / map_df["population"] * 100000
    map_df["log_loan_per_100k"] = np.log(map_df["loan_per_100k"])
    map_df = map_df.groupby("country_code", as_index=False).mean(numeric_only=True)
    map_df["country_code"] = map_df["country_code"].astype(str).str.strip().str.upper()

    shp_path = ROOT / "data" / "natural_earth_countries_110m" / "ne_110m_admin_0_countries.shp"
    world = gpd.read_file(shp_path)
    world["ISO_A2_EH"] = world["ISO_A2_EH"].astype(str).str.strip().str.upper()
    world = world.merge(map_df, left_on="ISO_A2_EH", right_on="country_code", how="left")

    def plot_map(column, outfile):
        fig, ax = plt.subplots(figsize=(10, 5.2))
        try:
            world.plot(column=column, cmap="viridis", legend=True, scheme="quantiles", k=5, ax=ax,
                       missing_kwds={"color": "lightgrey"})
        except Exception:
            world.plot(column=column, cmap="viridis", legend=True, ax=ax, missing_kwds={"color": "lightgrey"})
        ax.set_axis_off()
        fig.tight_layout(); fig.savefig(FIGURES / outfile); plt.close(fig)

    plot_map("log_loan_per_100k", "figure5_map_lending.pdf")
    plot_map("log_gdp_pc", "figure6_map_gdp.pdf")
    plot_map("institutional_pca1", "figure7_map_institutions.pdf")
except Exception as e:
    print("WARNING: map figures (5-7) failed:", e)

# Figure 8
entry_disp = entry_by_decile.copy()
fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.bar(entry_disp.index, entry_disp["entry_rate"])
ax.set_xlabel("GDP per capita decile (1 = poorest, 10 = richest)")
ax.set_ylabel("Share of country-years with Kiva active")
ax.set_xticks(entry_disp.index)
fig.tight_layout(); fig.savefig(FIGURES / "figure8_entry_by_decile.pdf"); plt.close(fig)

print("\nAll tables written to:", TABLES)
print("All figures written to:", FIGURES)

with open(TABLES / "_key_numbers.json", "w") as f:
    json.dump(KEY_NUMBERS, f, indent=2, default=str)
print("Key numbers written to:", TABLES / "_key_numbers.json")
