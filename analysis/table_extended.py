import pandas as pd
import numpy as np

PATH = "outputs/country_master_with_finance.csv"
df = pd.read_csv(PATH)
df.columns = df.columns.str.strip()

# ---------- numeric safety ----------
for c in ["poverty_rate", "financial_access_index", "population", "n_loans", "total_loan_amount",
          "bank_branches_per_100k", "atms_per_100k", "bank_accounts_per_1000", "credit_private_gdp"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# ---------- per-capita outcomes ----------
df.loc[df["population"] <= 0, ["population"]] = np.nan
df["loans_per_capita"] = df["n_loans"] / df["population"]
df["loan_amount_per_capita"] = df["total_loan_amount"] / df["population"]
df.loc[df["population"] <= 0, ["loans_per_capita", "loan_amount_per_capita"]] = np.nan

# ---------- poverty tercile ----------
df["poverty_tercile"] = pd.NA
mask = df["poverty_rate"].notna()

try:
    df.loc[mask, "poverty_tercile"] = pd.qcut(
        df.loc[mask, "poverty_rate"],
        3,
        labels=["Low poverty", "Medium poverty", "High poverty"]
    )
except ValueError:
    ranked = df.loc[mask, "poverty_rate"].rank(method="first")
    df.loc[mask, "poverty_tercile"] = pd.qcut(
        ranked,
        3,
        labels=["Low poverty", "Medium poverty", "High poverty"]
    )

# =========================================================
# Table 1: By poverty tercile (extended)
# =========================================================
t1 = (
    df.dropna(subset=["poverty_tercile"])
      .groupby("poverty_tercile", observed=False)
      .agg(
          n_countries=("country_code", "nunique"),
          total_loans=("n_loans", "sum"),
          mean_loans_pc=("loans_per_capita", "mean"),
          mean_amt_pc=("loan_amount_per_capita", "mean"),

          mean_poverty=("poverty_rate", "mean"),
          mean_fin_access=("financial_access_index", "mean"),

          mean_branches=("bank_branches_per_100k", "mean"),
          mean_atms=("atms_per_100k", "mean"),
          mean_accounts=("bank_accounts_per_1000", "mean"),
          mean_credit=("credit_private_gdp", "mean"),
      )
      .reset_index()
)

t1.to_csv("outputs/table_by_tercile_extended.csv", index=False)

# =========================================================
# Table 2: poverty tercile × Z split (NEW Z = financial_access_index)
# =========================================================
df["Z_split"] = pd.Series(pd.NA, index=df.index, dtype="object")

if "financial_access_index" in df.columns:
    z_med = df["financial_access_index"].median(skipna=True)
    m = df["financial_access_index"].notna()
    df.loc[m & (df["financial_access_index"] >= z_med), "Z_split"] = "High-Z"
    df.loc[m & (df["financial_access_index"] <  z_med), "Z_split"] = "Low-Z"

t2 = (
    df.dropna(subset=["poverty_tercile", "Z_split"])
      .groupby(["poverty_tercile", "Z_split"], observed=False)
      .agg(
          n_countries=("country_code", "nunique"),
          total_loans=("n_loans", "sum"),
          mean_loans_pc=("loans_per_capita", "mean"),
          mean_amt_pc=("loan_amount_per_capita", "mean"),

          mean_fin_access=("financial_access_index", "mean"),
          mean_branches=("bank_branches_per_100k", "mean"),
          mean_atms=("atms_per_100k", "mean"),
          mean_accounts=("bank_accounts_per_1000", "mean"),
          mean_credit=("credit_private_gdp", "mean"),
      )
      .reset_index()
      .sort_values(["poverty_tercile", "Z_split"])
)

t2.to_csv("outputs/table_mechanism_extended.csv", index=False)

print("Saved:")
print("outputs/table_by_tercile_extended.csv")
print("outputs/table_mechanism_extended.csv")
