import pandas as pd
import numpy as np
from IPython.display import display, HTML

df = pd.read_csv("outputs/country_master_with_finance.csv")
df.columns = df.columns.str.strip()

# contentReference[oaicite:3]{index=3}
df["population"] = pd.to_numeric(df["population"], errors="coerce")
df["n_loans"] = pd.to_numeric(df["n_loans"], errors="coerce")
df["total_loan_amount"] = pd.to_numeric(df["total_loan_amount"], errors="coerce")

df["loans_per_capita"] = df["n_loans"] / df["population"]
df["loan_amount_per_capita"] = df["total_loan_amount"] / df["population"]
df.loc[df["population"] <= 0, ["loans_per_capita", "loan_amount_per_capita"]] = np.nan

cols = [
    "loans_per_capita",           # Y
    "poverty_rate",               # X1 (main)
    "urban_rural_gap",            # Z proxy
    "atms_per_100k",
    "bank_branches_per_100k",
    "bank_accounts_per_1000",
    "credit_private_gdp"
]


for c in cols:
    df[c] = pd.to_numeric(df[c], errors="coerce")

tab = df[cols].agg(["count", "mean", "std", "min", "median", "max"]).T
tab = tab.rename(columns={"count": "N", "mean": "Mean", "std": "SD", "min": "Min", "median": "Median", "max": "Max"})
tab = tab.round(4)

display(HTML("<h4>Table 1. Summary Statistics</h4>"))
display(HTML(tab.to_html()))


df["poverty_rate"] = pd.to_numeric(df["poverty_rate"], errors="coerce")
mask = df["poverty_rate"].notna()
df.loc[mask, "poverty_tercile"] = pd.qcut(
    df.loc[mask, "poverty_rate"],
    q=3,
    labels=["Low poverty", "Medium poverty", "High poverty"]
)

group_tab = (
    df.groupby("poverty_tercile")[cols]
      .agg(["count", "mean"])
)


group_mean = df.groupby("poverty_tercile")[cols].mean().round(4)

display(HTML("<h4>Table 2. Group Means by Poverty Tercile</h4>"))
display(HTML(group_mean.to_html()))

