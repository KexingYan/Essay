import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
from stargazer.stargazer import Stargazer

MASTER = "outputs/country_master_with_finance.csv"
OUT1 = "outputs/stargazer_table1_by_tercile.html"
OUT2 = "outputs/stargazer_table2_mechanism.html"

ACCESS_VARS = ["bank_branches_per_100k", "atms_per_100k", "bank_accounts_per_1000"]

def safe_zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    mu = s.mean(skipna=True)
    sd = s.std(skipna=True)
    if pd.isna(sd) or sd == 0:
        return pd.Series([np.nan] * len(s), index=s.index)
    return (s - mu) / sd

df = pd.read_csv(MASTER)
df.columns = df.columns.str.strip()

# ---- numeric safety ----
for c in ["poverty_rate", "population", "n_loans", "total_loan_amount",
          "financial_access_index", "credit_private_gdp"] + ACCESS_VARS:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# ---- per-capita outcomes ----
df["loans_per_capita"] = df["n_loans"] / df["population"]
df["loan_amount_per_capita"] = df["total_loan_amount"] / df["population"]
df.loc[df["population"] <= 0, ["loans_per_capita", "loan_amount_per_capita"]] = np.nan

# ---- poverty tercile ----
df["poverty_tercile"] = pd.qcut(
    df["poverty_rate"], 3,
    labels=["Low poverty", "Medium poverty", "High poverty"]
)

# ---- ensure financial_access_index exists (fallback compute) ----
if "financial_access_index" not in df.columns or df["financial_access_index"].notna().sum() == 0:
    found = [c for c in ACCESS_VARS if c in df.columns]
    if len(found) == 0:
        df["financial_access_index"] = np.nan
    else:
        z_cols = []
        for c in found:
            df[c + "_z"] = safe_zscore(df[c])
            z_cols.append(c + "_z")
        df["financial_access_index"] = df[z_cols].mean(axis=1, skipna=True)

# ---- Z split (median on financial_access_index) ----
z_med = df["financial_access_index"].median(skipna=True)
df["Z_split"] = pd.Series(pd.NA, index=df.index, dtype="object")
m = df["financial_access_index"].notna()
df.loc[m & (df["financial_access_index"] >= z_med), "Z_split"] = "High-Z"
df.loc[m & (df["financial_access_index"] <  z_med), "Z_split"] = "Low-Z"

# =========================================================
# Table 1: outcomes by poverty tercile
# =========================================================
d1 = df.dropna(subset=["poverty_tercile", "loans_per_capita", "loan_amount_per_capita"]).copy()

m1 = smf.ols("loans_per_capita ~ C(poverty_tercile)", data=d1).fit(cov_type="HC1")
m2 = smf.ols("loan_amount_per_capita ~ C(poverty_tercile)", data=d1).fit(cov_type="HC1")

sg1 = Stargazer([m1, m2])
sg1.title("Table 1. Kiva Lending Outcomes by Poverty Tercile")
sg1.custom_columns(["Loans per capita", "Loan amount per capita"], [1, 1])
sg1.dependent_variable_name("Outcome")
sg1.covariate_order([
    "Intercept",
    "C(poverty_tercile)[T.Medium poverty]",
    "C(poverty_tercile)[T.High poverty]",
])
sg1.rename_covariates({
    "Intercept": "Low poverty (baseline)",
    "C(poverty_tercile)[T.Medium poverty]": "Medium poverty",
    "C(poverty_tercile)[T.High poverty]": "High poverty",
})
sg1.add_line("SE type", ["Robust (HC1)", "Robust (HC1)"])
sg1.add_line("N countries", [str(int(m1.nobs)), str(int(m2.nobs))])

with open(OUT1, "w", encoding="utf-8") as f:
    f.write(sg1.render_html())

# =========================================================
# Table 2: mechanism regression (NEW Z = financial_access_index)
# =========================================================
controls = [
    "poverty_rate",
    "financial_access_index",
    "bank_branches_per_100k",
    "atms_per_100k",
    "bank_accounts_per_1000",
    "credit_private_gdp",
]

d2 = df.dropna(subset=controls + ["loans_per_capita", "loan_amount_per_capita"]).copy()

fml_base = "poverty_rate + financial_access_index + bank_branches_per_100k + atms_per_100k + bank_accounts_per_1000 + credit_private_gdp"

m3 = smf.ols(f"loans_per_capita ~ {fml_base}", data=d2).fit(cov_type="HC1")
m4 = smf.ols(f"loan_amount_per_capita ~ {fml_base}", data=d2).fit(cov_type="HC1")

sg2 = Stargazer([m3, m4])
sg2.title("Table 2. Poverty and Lending with Mechanism (Financial Access Index) + Controls")
sg2.custom_columns(["Loans per capita", "Loan amount per capita"], [1, 1])
sg2.dependent_variable_name("Outcome")
sg2.covariate_order([
    "poverty_rate",
    "financial_access_index",
    "bank_branches_per_100k",
    "atms_per_100k",
    "bank_accounts_per_1000",
    "credit_private_gdp",
    "Intercept",
])
sg2.rename_covariates({
    "poverty_rate": "Poverty rate",
    "financial_access_index": "Financial access index (Z)",
    "bank_branches_per_100k": "Bank branches / 100k adults",
    "atms_per_100k": "ATMs / 100k adults",
    "bank_accounts_per_1000": "Bank accounts / 1000 adults",
    "credit_private_gdp": "Private credit (% GDP)",
    "Intercept": "Constant",
})
sg2.add_line("SE type", ["Robust (HC1)", "Robust (HC1)"])
sg2.add_line("N countries", [str(int(m3.nobs)), str(int(m4.nobs))])

with open(OUT2, "w", encoding="utf-8") as f:
    f.write(sg2.render_html())

print("Saved:")
print(OUT1)
print(OUT2)
