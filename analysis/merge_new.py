import os
import re
import glob
import pandas as pd
import numpy as np

# ============================================================
# SETTINGS
# ============================================================
DATA_DIR = r"D:\ECO225_DATA"  # Kiva raw file location (your D drive)
REPO_DIR = r"C:\Users\Klicy\github-classroom\ECO225-2026\eco225-project-KexingYan"
DATA_REPO = os.path.join(REPO_DIR, "data")
OUT_DIR = os.path.join(REPO_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

OUT_PATH = os.path.join(OUT_DIR, "country_year_kiva_gdppc.csv")

# ============================================================
# 1) LOAD + AGGREGATE KIVA TO COUNTRY-YEAR
# ============================================================
loans_path = os.path.join(DATA_DIR, "kiva_loans.csv")
if not os.path.exists(loans_path):
    raise FileNotFoundError(f"Kiva file not found: {loans_path}")

print("Using loans file:", loans_path)
loans = pd.read_csv(loans_path)

# Parse time -> year
loans["disbursed_time"] = pd.to_datetime(loans["disbursed_time"], errors="coerce", utc=True)
loans["year"] = loans["disbursed_time"].dt.year

# Numeric amount
loans["loan_amount"] = pd.to_numeric(loans.get("loan_amount"), errors="coerce")

# Keep needed columns
kiva = loans.loc[:, ["id", "country_code", "country", "year", "loan_amount"]].dropna(
    subset=["country_code", "year", "loan_amount"]
).copy()

# Keep only reasonable years (optional; but helps avoid weird NaNs)
kiva["year"] = pd.to_numeric(kiva["year"], errors="coerce").astype("Int64")

country_year = (
    kiva.groupby(["country_code", "year"], as_index=False)
        .agg(
            n_loans=("id", "count"),
            total_loan_amount=("loan_amount", "sum"),
        )
)

print("Kiva year range:", int(country_year["year"].min()), "to", int(country_year["year"].max()))
print("Country-year rows:", len(country_year))

# ============================================================
# 2) LOAD GDP PER CAPITA (WDI EXTRACT) FROM REPO /data
#    Expecting file name like: data/gdp_per_capita.xlsx or .csv
# ============================================================
gdp_candidates = (
    glob.glob(os.path.join(DATA_REPO, "gdp_per_capita*.xlsx")) +
    glob.glob(os.path.join(DATA_REPO, "gdp_per_capita*.xls")) +
    glob.glob(os.path.join(DATA_REPO, "gdp_per_capita*.csv"))
)

if len(gdp_candidates) == 0:
    raise FileNotFoundError(
        f"No GDP file found in {DATA_REPO}. Expected gdp_per_capita*.xlsx/xls/csv"
    )

gdp_path = gdp_candidates[0]
print("Using GDP file:", gdp_path)

if gdp_path.lower().endswith(".csv"):
    gdp_raw = pd.read_csv(gdp_path)
else:
    gdp_raw = pd.read_excel(gdp_path)

gdp_raw.columns = [str(c).strip() for c in gdp_raw.columns]

# Identify required columns
required_cols = ["Country Name", "Country Code", "Series Name", "Series Code"]
missing_req = [c for c in required_cols if c not in gdp_raw.columns]
if missing_req:
    raise ValueError(f"GDP file is missing required columns: {missing_req}")

# WDI year columns look like "2014 [YR2014]"
year_cols = [c for c in gdp_raw.columns if re.search(r"\[YR\d{4}\]", str(c))]
if len(year_cols) == 0:
    raise ValueError("No year columns like '2014 [YR2014]' found in GDP file.")

# Prefer exact WDI code for GDP per capita (constant 2015 US$)
# NY.GDP.PCAP.KD is "GDP per capita (constant 2015 US$)"
gdp_raw["Series Code"] = gdp_raw["Series Code"].astype(str).str.strip()
gdp_raw["Series Name"] = gdp_raw["Series Name"].astype(str).str.strip()

code_target = "NY.GDP.PCAP.KD"
gdp_sub = gdp_raw.loc[gdp_raw["Series Code"] == code_target].copy()

# Fallback: match by Series Name if code not present
if gdp_sub.empty:
    name_pat = r"GDP per capita \(constant 2015 US\$\)"
    gdp_sub = gdp_raw.loc[gdp_raw["Series Name"].str.contains(name_pat, regex=True, na=False)].copy()

if gdp_sub.empty:
    # last fallback: show the unique series codes so you can pick
    uniq_codes = gdp_raw["Series Code"].dropna().unique()[:30]
    raise ValueError(
        "Could not find GDP per capita (constant 2015 US$) in the GDP extract.\n"
        "Expected Series Code = NY.GDP.PCAP.KD, or Series Name containing 'GDP per capita (constant 2015 US$)'.\n"
        f"Example Series Codes in file: {list(uniq_codes)}"
    )

# Melt wide -> long
gdp_long = gdp_sub.melt(
    id_vars=["Country Name", "Country Code", "Series Name", "Series Code"],
    value_vars=year_cols,
    var_name="year_col",
    value_name="gdp_pc_const2015",
)

gdp_long["year"] = gdp_long["year_col"].str.extract(r"(\d{4})")[0]
gdp_long["year"] = pd.to_numeric(gdp_long["year"], errors="coerce").astype("Int64")

gdp_long["gdp_pc_const2015"] = (
    gdp_long["gdp_pc_const2015"]
      .replace("..", np.nan)
)
gdp_long["gdp_pc_const2015"] = pd.to_numeric(gdp_long["gdp_pc_const2015"], errors="coerce")

gdp_long = gdp_long.rename(
    columns={
        "Country Code": "iso3",
        "Country Name": "country_name",
    }
)

gdp_long = gdp_long.dropna(subset=["iso3", "year"]).loc[:, ["iso3", "country_name", "year", "gdp_pc_const2015"]]
print("GDP rows:", len(gdp_long))
print("GDP year range:", int(gdp_long["year"].min()), "to", int(gdp_long["year"].max()))

# ============================================================
# 3) ISO3 -> ISO2 MAPPING (to merge with Kiva country_code)
#    Use your existing master file that already has both.
# ============================================================
map_path = os.path.join(REPO_DIR, "outputs", "country_master_with_finance_and_institutions.csv")
if not os.path.exists(map_path):
    raise FileNotFoundError(f"Mapping file not found: {map_path}")

m = pd.read_csv(map_path)
m.columns = [c.strip().lower() for c in m.columns]

# Expect columns like iso3 and country_code (iso2)
if "iso3" not in m.columns:
    raise ValueError("Mapping file is missing 'iso3' column.")
if "country_code" not in m.columns and "iso2" not in m.columns:
    raise ValueError("Mapping file is missing 'country_code' (ISO2) column.")

if "country_code" not in m.columns and "iso2" in m.columns:
    m = m.rename(columns={"iso2": "country_code"})

m["iso3"] = m["iso3"].astype(str).str.strip()
m["country_code"] = m["country_code"].astype(str).str.strip()

iso_map = m.loc[:, ["iso3", "country_code"]].drop_duplicates()

gdp_long = gdp_long.merge(iso_map, on="iso3", how="left")
print("Share missing ISO2 after mapping:", round(gdp_long["country_code"].isna().mean(), 3))

gdp_kiva = gdp_long.dropna(subset=["country_code"]).loc[:, ["country_code", "year", "gdp_pc_const2015"]].copy()

# ============================================================
# 4) MERGE: Kiva country-year + GDP per capita
# ============================================================
# Ensure year types match (important to avoid MergeError)
country_year["year"] = pd.to_numeric(country_year["year"], errors="coerce").astype("Int64")
gdp_kiva["year"] = pd.to_numeric(gdp_kiva["year"], errors="coerce").astype("Int64")

panel = country_year.merge(gdp_kiva, on=["country_code", "year"], how="left")

# Derived vars for regression
panel["gdp_pc_const2015"] = pd.to_numeric(panel["gdp_pc_const2015"], errors="coerce")
panel.loc[panel["gdp_pc_const2015"] <= 0, "gdp_pc_const2015"] = np.nan
panel["log_gdp_pc"] = np.log(panel["gdp_pc_const2015"])

print("Panel rows:", len(panel))
print("Share missing GDPpc:", round(panel["gdp_pc_const2015"].isna().mean(), 3))
print("Regression-ready rows (GDPpc not missing):", int(panel["log_gdp_pc"].notna().sum()))

panel.to_csv(OUT_PATH, index=False)
print("Saved:", OUT_PATH)