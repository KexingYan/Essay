import os
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("ECO225_DATA_DIR", BASE_DIR / "data"))

print(f"[summary] Using data directory: {DATA_DIR}")


# --------------------
# 1) Load + merge
# --------------------
loans = pd.read_csv(
    DATA_DIR / "loans.csv",
    usecols=["loan_id", "loan_amount", "country_code"]
)

country_stats = pd.read_csv(DATA_DIR / "country_stats.csv")


merged = loans.merge(country_stats, on="country_code", how="inner")

print("Merged rows:", merged.shape[0])
print("Unique countries in merged:", merged["country_code"].nunique())

# =====================================================
# 2) Construct poverty_rate at country level (CORRECT)
# =====================================================

# Keep only needed columns
cs = merged[["country_code", "population", "population_below_poverty_line"]] \
        .drop_duplicates("country_code") \
        .copy()

# Make sure numeric
cs["population"] = pd.to_numeric(cs["population"], errors="coerce")
cs["population_below_poverty_line"] = pd.to_numeric(cs["population_below_poverty_line"], errors="coerce")

# -----------------------------------------------------
# IMPORTANT:
# population_below_poverty_line is PERCENT (0–100)
# so divide by 100 ONLY (NOT by population)
# -----------------------------------------------------
cs["poverty_rate"] = cs["population_below_poverty_line"] / 100

# Drop invalid
cs = cs[cs["poverty_rate"].notna()]
cs = cs[(cs["poverty_rate"] >= 0) & (cs["poverty_rate"] <= 1)]

print("\nCountries with non-missing poverty_rate:", cs.shape[0])


# =====================================================
# 3) Create poverty terciles
# =====================================================

cs["poverty_tercile"] = pd.qcut(
    cs["poverty_rate"],
    q=3,
    labels=["Low poverty", "Medium poverty", "High poverty"]
)

# Attach back
merged = merged.merge(
    cs[["country_code", "poverty_rate", "poverty_tercile"]],
    on="country_code",
    how="left"
)

# --------------------
# 4) Compute summary stats by tercile
# --------------------
# Convert loan_amount numeric
merged["loan_amount"] = pd.to_numeric(merged["loan_amount"], errors="coerce")

# For per-capita, it's cleaner to compute at country level first:
country_agg = merged.groupby("country_code", as_index=False).agg(
    loans=("loan_id", "count"),
    total_loan_amount=("loan_amount", "sum"),
)

# merge population + tercile back
country_agg = country_agg.merge(cs[["country_code", "population", "poverty_tercile"]], on="country_code", how="inner")

# loans per capita at country level
country_agg["loans_per_capita"] = country_agg["loans"] / country_agg["population"]

# Now summarize by tercile (mean of country-level loans_per_capita is usually the fairest)
summary = country_agg.groupby("poverty_tercile", as_index=False).agg(
    num_countries=("country_code", "nunique"),
    num_loans=("loans", "sum"),
    total_loan_amount=("total_loan_amount", "sum"),
    avg_loans_per_capita=("loans_per_capita", "mean"),
)

# Nice formatting
summary = summary.sort_values("poverty_tercile")
print("\nSummary table by poverty tercile:")
print(summary)

# Optional: save to csv for report
summary.to_csv("summary_by_poverty_tercile.csv", index=False)
print("\nSaved: summary_by_poverty_tercile.csv")
