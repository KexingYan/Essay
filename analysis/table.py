import pandas as pd
import numpy as np
from IPython.display import display, HTML

df = pd.read_csv("outputs/country_master_with_finance.csv")
df.columns = df.columns.str.strip()

df["population"] = pd.to_numeric(df["population"], errors="coerce")
df["n_loans"] = pd.to_numeric(df["n_loans"], errors="coerce")
df["total_loan_amount"] = pd.to_numeric(df["total_loan_amount"], errors="coerce")

df["loans_per_capita"] = df["n_loans"] / df["population"]
df["loan_amount_per_capita"] = df["total_loan_amount"] / df["population"]
df.loc[df["population"] <= 0, ["loans_per_capita", "loan_amount_per_capita"]] = np.nan

cols = [
    "loans_per_capita",
    "poverty_rate",
    "financial_access_index",   # NEW Z
    "atms_per_100k",
    "bank_branches_per_100k",
    "bank_accounts_per_1000",
    "credit_private_gdp"
]

for c in cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    else:
        df[c] = np.nan

tab = df[cols].agg(["count", "mean", "std", "min", "median", "max"]).T
tab = tab.rename(columns={"count": "N", "mean": "Mean", "std": "SD", "min": "Min", "median": "Median", "max": "Max"})
tab = tab.round(4)

display(HTML("<h4>Table 1. Summary Statistics</h4>"))
display(HTML(tab.to_html()))

mask = df["poverty_rate"].notna()
df.loc[mask, "poverty_tercile"] = pd.qcut(
    df.loc[mask, "poverty_rate"],
    q=3,
    labels=["Low poverty", "Medium poverty", "High poverty"]
)

group_mean = df.groupby("poverty_tercile")[cols].mean().round(4)

display(HTML("<h4>Table 2. Group Means by Poverty Tercile</h4>"))
display(HTML(group_mean.to_html()))
