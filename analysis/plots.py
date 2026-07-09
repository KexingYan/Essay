# analysis/plots.py
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH_PRIMARY = "outputs/country_master_with_finance.csv"
DATA_PATH_FALLBACK = "outputs/country_master.csv"
FIG_DIR = os.path.join("outputs", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

def safe_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def ensure_per_capita_vars(df):
    need_loans_pc = "loans_per_capita" not in df.columns
    need_amt_pc = "loan_amount_per_capita" not in df.columns

    required = ["population", "n_loans", "total_loan_amount"]
    df = safe_numeric(df, required)

    if need_loans_pc:
        if all(c in df.columns for c in ["n_loans", "population"]):
            df["loans_per_capita"] = df["n_loans"] / df["population"]
        else:
            raise KeyError("Missing columns to compute loans_per_capita. Need n_loans and population.")

    if need_amt_pc:
        if all(c in df.columns for c in ["total_loan_amount", "population"]):
            df["loan_amount_per_capita"] = df["total_loan_amount"] / df["population"]
        else:
            raise KeyError("Missing columns to compute loan_amount_per_capita. Need total_loan_amount and population.")

    return df

def ensure_poverty_tercile(df):
    if "poverty_tercile" in df.columns:
        return df

    if "poverty_rate" not in df.columns:
        raise KeyError("poverty_rate not found. Can't create poverty_tercile.")

    df["poverty_rate"] = pd.to_numeric(df["poverty_rate"], errors="coerce")

    mask = df["poverty_rate"].notna()
    df.loc[mask, "poverty_tercile"] = pd.qcut(
        df.loc[mask, "poverty_rate"],
        q=3,
        labels=["Low poverty", "Medium poverty", "High poverty"]
    )
    df.loc[~mask, "poverty_tercile"] = pd.NA
    return df

def ensure_Z_split(df):
    # NEW: Z split based on median financial_access_index
    if "Z_split" in df.columns:
        return df

    if "financial_access_index" not in df.columns:
        df["Z_split"] = pd.NA
        return df

    df["financial_access_index"] = pd.to_numeric(df["financial_access_index"], errors="coerce")
    z_med = df["financial_access_index"].median(skipna=True)

    df["Z_split"] = pd.NA
    m = df["financial_access_index"].notna()
    df.loc[m & (df["financial_access_index"] >= z_med), "Z_split"] = "High-Z"
    df.loc[m & (df["financial_access_index"] <  z_med), "Z_split"] = "Low-Z"
    return df

def order_tercile(s):
    order = ["Low poverty", "Medium poverty", "High poverty"]
    return pd.Categorical(s, categories=order, ordered=True)

def coverage_report(df):
    total = len(df)
    out = {
        "Total countries in dataset": total,
        "Countries with poverty_rate": int(df["poverty_rate"].notna().sum()) if "poverty_rate" in df.columns else 0,
        "Countries with poverty_tercile": int(df["poverty_tercile"].notna().sum()) if "poverty_tercile" in df.columns else 0,
        "Countries with financial_access_index": int(df["financial_access_index"].notna().sum()) if "financial_access_index" in df.columns else 0,
        "Countries with Z_split": int(df["Z_split"].notna().sum()) if "Z_split" in df.columns else 0,
        "Countries with loans_per_capita": int(df["loans_per_capita"].notna().sum()) if "loans_per_capita" in df.columns else 0,
        "Countries with loan_amount_per_capita": int(df["loan_amount_per_capita"].notna().sum()) if "loan_amount_per_capita" in df.columns else 0,
    }

    for c in ["bank_branches_per_100k", "atms_per_100k", "bank_accounts_per_1000", "credit_private_gdp"]:
        if c in df.columns:
            out[f"Countries with {c}"] = int(pd.to_numeric(df[c], errors="coerce").notna().sum())

    print("\n=== Coverage diagnostics ===")
    for k, v in out.items():
        print(f"{k:40s} {v}")
    print("")

# ----------------------------
# Load data
# ----------------------------
path = DATA_PATH_PRIMARY if os.path.exists(DATA_PATH_PRIMARY) else DATA_PATH_FALLBACK
df = pd.read_csv(path)
df.columns = df.columns.str.strip()

df = ensure_per_capita_vars(df)
df = ensure_poverty_tercile(df)
df = ensure_Z_split(df)

df["poverty_tercile"] = order_tercile(df["poverty_tercile"])
coverage_report(df)

# ----------------------------
# Figure 1
# ----------------------------
df1 = df.dropna(subset=["poverty_tercile", "loans_per_capita"]).copy()
g1 = df1.groupby("poverty_tercile", observed=False)["loans_per_capita"].mean()

plt.figure(figsize=(9, 5))
plt.bar(g1.index.astype(str), g1.values)
plt.title("Figure 1. Average Loans per Capita by Poverty Tercile")
plt.xlabel("Poverty tercile")
plt.ylabel("Loans per capita")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig1_loans_per_capita_by_tercile.png"), dpi=200, bbox_inches="tight")
plt.close()

# ----------------------------
# Figure 2
# ----------------------------
df2 = df.dropna(subset=["poverty_rate", "loans_per_capita"]).copy()

plt.figure(figsize=(8, 5))
plt.scatter(df2["poverty_rate"], df2["loans_per_capita"], alpha=0.7)
plt.title("Figure 2. Poverty Rate vs Loans per Capita")
plt.xlabel("Poverty rate")
plt.ylabel("Loans per capita")
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig2_scatter_poverty_rate_vs_loans_per_capita.png"), dpi=200, bbox_inches="tight")
plt.close()

# ----------------------------
# Figure 3 (UPDATED TITLE + Z meaning)
# ----------------------------
df3 = df.dropna(subset=["poverty_tercile", "Z_split", "loans_per_capita"]).copy()
pivot3 = df3.pivot_table(
    index="poverty_tercile",
    columns="Z_split",
    values="loans_per_capita",
    aggfunc="mean",
    observed=False
).reindex(index=["Low poverty", "Medium poverty", "High poverty"])

cols = [c for c in ["High-Z", "Low-Z"] if c in pivot3.columns]
pivot3 = pivot3[cols]

x = np.arange(len(pivot3.index))
width = 0.35 if len(cols) == 2 else 0.6

plt.figure(figsize=(10, 6))
if len(cols) == 2:
    plt.bar(x - width/2, pivot3[cols[0]].values, width, label=cols[0])
    plt.bar(x + width/2, pivot3[cols[1]].values, width, label=cols[1])
elif len(cols) == 1:
    plt.bar(x, pivot3[cols[0]].values, width, label=cols[0])

plt.title("Figure 3. Loans per Capita by Poverty Tercile and Financial Access (Z Split)")
plt.xlabel("Poverty tercile")
plt.ylabel("Loans per capita")
plt.xticks(x, [str(i) for i in pivot3.index], rotation=30, ha="right")
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig3_loans_per_capita_by_tercile_and_Zsplit.png"), dpi=300, bbox_inches="tight")
plt.close()

# ----------------------------
# Figure 4
# ----------------------------
df4 = df.dropna(subset=["poverty_tercile", "loan_amount_per_capita"]).copy()
g4 = df4.groupby("poverty_tercile", observed=False)["loan_amount_per_capita"].mean()

plt.figure(figsize=(9, 5))
plt.bar(g4.index.astype(str), g4.values)
plt.title("Figure 4. Average Loan Amount per Capita by Poverty Tercile")
plt.xlabel("Poverty tercile")
plt.ylabel("Loan amount per capita")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig4_loan_amount_per_capita_by_tercile.png"), dpi=200, bbox_inches="tight")
plt.close()

print("Saved figures to:", FIG_DIR)
