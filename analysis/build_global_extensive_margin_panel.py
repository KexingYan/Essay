"""
Phase 2b: build the global country-year panel (including zero-Kiva country-years) used for the
extensive/intensive margin decomposition and PPML in paper_publication_version.ipynb Section 5.3.

Primary path: pull GDP per capita (NY.GDP.PCAP.KD) and population (SP.POP.TOTL) for all WDI-classified
countries (excluding regional/income aggregates) for 2013-2017 via wbdata (live World Bank API).

Kiva country-year totals are built directly from the raw loan-level file (data/loans.csv) rather than
final_panel_country_year.csv, because the latter only contains Kiva-active country-years -- the whole
point of Section 5.3 is to observe country-years where Kiva was NOT active (kiva_active = 0).
"""
import os
import datetime
import pandas as pd
import numpy as np
import wbdata
import country_converter as coco
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_DIR / "outputs"

YEARS = [2013, 2014, 2015, 2016, 2017]

WDI_CACHE = OUT_DIR / "wdi_gdp_pop_2013_2017.csv"

# -----------------------------
# 1) WDI GDP per capita + population, real countries only
# -----------------------------
if WDI_CACHE.exists():
    wdi = pd.read_csv(WDI_CACHE)
    print("Loaded cached WDI panel:", WDI_CACHE, wdi.shape)
else:
    countries_meta = wbdata.get_countries()
    real_iso3 = [c["id"] for c in countries_meta if c.get("region") and c["region"]["value"] != "Aggregates"]
    print("Real (non-aggregate) WDI economies:", len(real_iso3))

    indicators = {"NY.GDP.PCAP.KD": "gdp_pc_const2015", "SP.POP.TOTL": "population"}
    wdi_raw = wbdata.get_dataframe(
        indicators,
        country=real_iso3,
        date=(datetime.datetime(2013, 1, 1), datetime.datetime(2017, 12, 31)),
    ).reset_index()

    # get_dataframe returns country NAME, not iso3 -- rebuild the iso3 key from the country id list
    # by re-querying per-indicator with country codes preserved via wbdata.get_data (safer for merge).
    rows = []
    for iso3 in real_iso3:
        for code, colname in indicators.items():
            try:
                data = wbdata.get_data(code, country=iso3)
            except Exception:
                continue
            if not data:
                continue
            for obs in data:
                year = int(obs["date"])
                if year in YEARS and obs["value"] is not None:
                    rows.append({"iso3": iso3, "year": year, "indicator": colname, "value": float(obs["value"])})
    long_df = pd.DataFrame(rows)
    wdi = long_df.pivot_table(index=["iso3", "year"], columns="indicator", values="value").reset_index()
    wdi.to_csv(WDI_CACHE, index=False)
    print("Fetched and cached WDI panel:", wdi.shape)

wdi["iso3"] = wdi["iso3"].astype(str).str.strip().str.upper()
wdi["year"] = wdi["year"].astype(int)

# -----------------------------
# 2) Kiva country-year aggregates from raw loan-level data
# -----------------------------
loans = pd.read_csv(REPO_DIR / "data" / "loans.csv", usecols=["loan_id", "loan_amount", "country_code", "posted_time"])
loans["posted_time"] = pd.to_datetime(loans["posted_time"], errors="coerce", utc=True)
loans["year"] = loans["posted_time"].dt.year
loans = loans[loans["year"].between(2013, 2017)].copy()
loans["loan_amount"] = pd.to_numeric(loans["loan_amount"], errors="coerce")
loans = loans[loans["loan_amount"] > 0].copy()

kiva_agg = loans.groupby(["country_code", "year"]).agg(
    n_loans=("loan_id", "count"),
    total_loan_amount=("loan_amount", "sum"),
).reset_index()

cc = coco.CountryConverter()
kiva_agg["iso3"] = cc.pandas_convert(kiva_agg["country_code"], src="ISO2", to="ISO3", not_found=None)
unmatched = kiva_agg[kiva_agg["iso3"].isna()]
if len(unmatched):
    print("WARNING: Kiva country codes with no ISO3 match (dropped):", unmatched["country_code"].unique().tolist())
kiva_agg = kiva_agg.dropna(subset=["iso3"]).copy()
kiva_agg["iso3"] = kiva_agg["iso3"].astype(str).str.strip().str.upper()

# -----------------------------
# 3) Outer merge: global WDI skeleton x Kiva aggregates
# -----------------------------
global_panel = wdi.merge(kiva_agg[["iso3", "year", "n_loans", "total_loan_amount"]], on=["iso3", "year"], how="outer")

n_before_gdp_drop = len(global_panel)
missing_gdp_pop = global_panel[global_panel["gdp_pc_const2015"].isna() | global_panel["population"].isna()]
print("Rows dropped for missing GDP or population:", len(missing_gdp_pop), "of", n_before_gdp_drop)
global_panel = global_panel.dropna(subset=["gdp_pc_const2015", "population"]).copy()

global_panel["n_loans"] = global_panel["n_loans"].fillna(0)
global_panel["total_loan_amount"] = global_panel["total_loan_amount"].fillna(0.0)
global_panel["kiva_active"] = (global_panel["n_loans"] > 0).astype(int)

global_panel["log_gdp_pc"] = np.log(global_panel["gdp_pc_const2015"])
global_panel["log_population"] = np.log(global_panel["population"])
global_panel["c_log_gdp_pc"] = global_panel["log_gdp_pc"] - global_panel["log_gdp_pc"].mean()
global_panel["c_log_gdp_pc_sq"] = global_panel["c_log_gdp_pc"] ** 2

# -----------------------------
# 4) Merge in institutional variables for the Kiva-covered subset only (heavily missing globally)
# -----------------------------
master = pd.read_csv(OUT_DIR / "country_master_with_finance_and_institutions.csv")
inst_cols = ["iso3", "institutional_pca1", "institutional_index", "financial_access_index"]
inst_cols = [c for c in inst_cols if c in master.columns]
global_panel = global_panel.merge(master[inst_cols].drop_duplicates(subset=["iso3"]), on="iso3", how="left")

print("Final global panel shape:", global_panel.shape)
print("Countries:", global_panel["iso3"].nunique(), "| Kiva-active country-years:", int(global_panel["kiva_active"].sum()))
print("Kiva-active rate:", round(global_panel["kiva_active"].mean(), 4))

global_panel.to_csv(OUT_DIR / "final_panel_global_extensive.csv", index=False)
print("Saved:", OUT_DIR / "final_panel_global_extensive.csv")
