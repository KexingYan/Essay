"""
Phase 2c helper: build a loan-level frame that keeps fields the main
outputs/final_panel_loan_level.csv drops (sector_name, gdp_pc_const2015 in levels), needed for the
loan-level robustness variants (exclude US, relative loan size, sector fixed effects).

Mirrors analysis/build_final_panel_loan_level.py's filtering/merge logic exactly (2013-2017,
loan_amount > 0, same GDP panel and institutions master), just with two extra columns retained.
"""
from pathlib import Path
import pandas as pd
import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_DIR / "outputs"

loans = pd.read_csv(
    REPO_DIR / "data" / "loans.csv",
    usecols=["loan_id", "loan_amount", "sector_name", "country_code", "posted_time"],
)
loans["posted_time"] = pd.to_datetime(loans["posted_time"], errors="coerce", utc=True)
loans["year"] = loans["posted_time"].dt.year
loans = loans[loans["year"].between(2013, 2017)].copy()
loans["loan_amount"] = pd.to_numeric(loans["loan_amount"], errors="coerce")
loans = loans[loans["loan_amount"] > 0].copy()
loans["log_loan_amount"] = np.log(loans["loan_amount"])
loans["country_code"] = loans["country_code"].astype(str).str.strip()

gdp_panel = pd.read_csv(OUT_DIR / "country_year_kiva_gdppc.csv")
gdp_panel["country_code"] = gdp_panel["country_code"].astype(str).str.strip()
loans = loans.merge(
    gdp_panel[["country_code", "year", "gdp_pc_const2015", "log_gdp_pc"]].drop_duplicates(),
    on=["country_code", "year"],
    how="left",
)

master = pd.read_csv(OUT_DIR / "country_master_with_finance_and_institutions.csv")
master["country_code"] = master["country_code"].astype(str).str.strip()
z_cols = [c for c in ["institutional_pca1", "institutional_index", "financial_access_index"] if c in master.columns]
loans = loans.merge(master[["country_code"] + z_cols].drop_duplicates(subset=["country_code"]), on="country_code", how="left")

cs = pd.read_csv(REPO_DIR / "data" / "country_stats.csv")
cs["country_code"] = cs["country_code"].astype(str).str.strip()
cs["population"] = pd.to_numeric(cs["population"], errors="coerce")
loans = loans.merge(cs[["country_code", "population"]].drop_duplicates(subset=["country_code"]), on="country_code", how="left")
loans["log_population"] = np.log(loans["population"].where(loans["population"] > 0))

loans["country_year_id"] = loans["country_code"] + "_" + loans["year"].astype(str)
loans["log_relative_loan_size"] = np.log(loans["loan_amount"] / loans["gdp_pc_const2015"])

keep_cols = [
    "loan_id", "country_code", "year", "sector_name",
    "loan_amount", "log_loan_amount", "gdp_pc_const2015", "log_gdp_pc",
    "log_relative_loan_size", "population", "log_population",
    "country_year_id",
] + z_cols
final = loans[keep_cols].copy()
final.to_csv(OUT_DIR / "final_panel_loan_level_augmented_2c.csv", index=False)
print("Saved:", OUT_DIR / "final_panel_loan_level_augmented_2c.csv", final.shape)
print("Missingness:")
print(final.isna().mean().round(4))
print()
print("US share of loans:", (final["country_code"] == "US").mean())
print("Sector counts:")
print(final["sector_name"].value_counts())
