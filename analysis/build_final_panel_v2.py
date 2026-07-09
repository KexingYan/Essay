# build_final_panel_v2.py
# ------------------------------------------------------------
# Build final country-year panel for ECO225 Project 2:
# Kiva (country-year) + GDPpc (country-year) + Z (institutions) + population (cross-section) + poverty (robustness)
#
# Inputs expected:
#   1) outputs/country_year_kiva_gdppc.csv               (already created by your merge_new.py)
#   2) outputs/country_master_with_finance_and_institutions.csv  (has iso2/iso3 + institutional_pca1, etc.)
#   3) data/country_stats.csv OR D:\ECO225_DATA\country_stats.csv (cross-section with population and iso2/iso3)
#   4) data/poverty.csv (optional robustness; WDI extract with Series Code SI.POV.DDAY)
#
# Output:
#   outputs/final_panel_country_year.csv
# ------------------------------------------------------------

import os
import re
import glob
import pandas as pd
import numpy as np

# -----------------------------
# Paths (EDIT if needed)
# -----------------------------
REPO_DIR = r"C:\Users\Klicy\github-classroom\ECO225-2026\eco225-project-KexingYan"
DATA_DIR_D = r"D:\ECO225_DATA"

BASE_PANEL_PATH = os.path.join(REPO_DIR, "outputs", "country_year_kiva_gdppc.csv")
MASTER_PATH = os.path.join(REPO_DIR, "outputs", "country_master_with_finance_and_institutions.csv")

DATA_REPO_DIR = os.path.join(REPO_DIR, "data")
OUT_DIR = os.path.join(REPO_DIR, "outputs")
OUT_PATH = os.path.join(OUT_DIR, "final_panel_country_year.csv")

os.makedirs(OUT_DIR, exist_ok=True)

# -----------------------------
# Helpers
# -----------------------------
def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def load_any(path: str) -> pd.DataFrame:
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)

def find_first_existing(candidates):
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def wdi_long_from_file(path: str, series_code: str, value_name: str) -> pd.DataFrame:
    """
    Read a WDI extract (csv/xlsx) in the common format:
    Country Name, Country Code, Series Name, Series Code, 1960 [YR1960], ...
    Return long df: iso3, year, <value_name>
    """
    raw = load_any(path)
    raw = norm_cols(raw)

    if "Series Code" not in raw.columns:
        # sometimes headers are slightly different
        raise ValueError(f"'Series Code' column not found in {os.path.basename(path)}")

    raw["Series Code"] = raw["Series Code"].astype(str).str.strip()
    sub = raw.loc[raw["Series Code"] == series_code].copy()
    if sub.empty:
        raise ValueError(f"Series Code {series_code} not found in {os.path.basename(path)}")

    year_cols = [c for c in sub.columns if re.search(r"\[YR\d{4}\]", str(c))]
    if len(year_cols) == 0:
        raise ValueError(f"No year columns like '[YR2014]' found in {os.path.basename(path)}")

    long = sub.melt(
        id_vars=["Country Name", "Country Code", "Series Code"],
        value_vars=year_cols,
        var_name="year_col",
        value_name=value_name
    )
    long["year"] = long["year_col"].str.extract(r"(\d{4})").astype(float).astype("Int64")
    long[value_name] = pd.to_numeric(long[value_name].replace("..", np.nan), errors="coerce")

    long = long.rename(columns={"Country Code": "iso3"})
    long = long[["iso3", "year", value_name]].dropna(subset=["iso3", "year"])
    return long

def nearest_year_merge(left: pd.DataFrame, right: pd.DataFrame, on_keys, year_col="year", max_gap=2):
    """
    Merge left (country-year) with right (country-year but sparse years) using nearest-year match within max_gap.
    Assumes right has unique rows per key-year.
    """
    left = left.copy()
    right = right.copy()

    # ensure year is int
    left[year_col] = pd.to_numeric(left[year_col], errors="coerce").astype("Int64")
    right[year_col] = pd.to_numeric(right[year_col], errors="coerce").astype("Int64")

    # expand right years by +/- max_gap so we can do exact merge
    parts = []
    for g in range(-max_gap, max_gap + 1):
        tmp = right.copy()
        tmp[year_col] = tmp[year_col] + g
        tmp["_gap"] = abs(g)
        parts.append(tmp)
    right_exp = pd.concat(parts, ignore_index=True)

    merged = left.merge(right_exp, on=on_keys + [year_col], how="left")

    # if duplicates due to multiple candidates, keep smallest gap
    if "_gap" in merged.columns:
        merged = merged.sort_values(on_keys + [year_col, "_gap"])
        merged = merged.drop_duplicates(subset=on_keys + [year_col], keep="first")
        merged = merged.drop(columns=["_gap"], errors="ignore")

    return merged

# -----------------------------
# 1) Load base panel (Kiva + GDPpc already merged)
# -----------------------------
if not os.path.exists(BASE_PANEL_PATH):
    raise FileNotFoundError(f"Missing base panel: {BASE_PANEL_PATH}")

panel = pd.read_csv(BASE_PANEL_PATH)
panel = norm_cols(panel)

# expected columns
# country_code, year, n_loans, total_loan_amount, gdp_pc_const2015, log_gdp_pc
for c in ["country_code", "year", "n_loans", "total_loan_amount", "log_gdp_pc"]:
    if c not in panel.columns:
        raise ValueError(f"Expected column '{c}' not found in {os.path.basename(BASE_PANEL_PATH)}")

panel["year"] = pd.to_numeric(panel["year"], errors="coerce").astype("Int64")
panel["n_loans"] = pd.to_numeric(panel["n_loans"], errors="coerce")
panel["total_loan_amount"] = pd.to_numeric(panel["total_loan_amount"], errors="coerce")

# add log outcome as main DV option
panel["log_total_loan_amount"] = np.log(panel["total_loan_amount"].where(panel["total_loan_amount"] > 0))

print("Loaded base panel:", len(panel), "rows")
print("Year range:", int(panel["year"].min()), "to", int(panel["year"].max()))

# -----------------------------
# 2) Load Z (institutions / finance master) and attach by iso2 (country_code)
# -----------------------------
if not os.path.exists(MASTER_PATH):
    raise FileNotFoundError(f"Missing master file with Z: {MASTER_PATH}")

master = pd.read_csv(MASTER_PATH)
master = norm_cols(master)
# normalize to lower for easier matching
master.columns = [c.lower() for c in master.columns]

# require iso2 mapping
if "country_code" not in master.columns:
    # sometimes it might be iso2
    if "iso2" in master.columns:
        master = master.rename(columns={"iso2": "country_code"})
    else:
        raise ValueError("Master file must contain country_code (ISO2) or iso2.")

master["country_code"] = master["country_code"].astype(str).str.strip()

# pick Z columns to carry (edit if you want more)
z_cols = []
for cand in ["institutional_pca1", "institutional_index", "financial_access_index"]:
    if cand in master.columns:
        z_cols.append(cand)

if len(z_cols) == 0:
    raise ValueError(
        "Did not find any of these Z columns in master: institutional_pca1, institutional_index, financial_access_index"
    )

z_keep = master[["country_code"] + z_cols].drop_duplicates(subset=["country_code"])
panel = panel.merge(z_keep, on="country_code", how="left")

print("Merged Z columns:", z_cols)
for c in z_cols:
    print(f"Share missing {c}:", round(panel[c].isna().mean(), 3))

# -----------------------------
# 3) Load population (cross-section) from country_stats and merge by ISO2
# -----------------------------
country_stats_candidates = [
    os.path.join(DATA_REPO_DIR, "country_stats.csv"),
    os.path.join(DATA_REPO_DIR, "country_stats.xlsx"),
    os.path.join(DATA_DIR_D, "country_stats.csv"),
    os.path.join(DATA_DIR_D, "country_stats.xlsx"),
]

country_stats_path = find_first_existing(country_stats_candidates)
if country_stats_path is None:
    raise FileNotFoundError(
        "Could not find country_stats.csv/xlsx in repo data/ or D:\\ECO225_DATA."
    )

cs = load_any(country_stats_path)
cs = norm_cols(cs)
cs.columns = [c.lower().strip() for c in cs.columns]

# normalize iso2 column name
if "country_code" not in cs.columns:
    if "iso2" in cs.columns:
        cs = cs.rename(columns={"iso2": "country_code"})
    elif "country co" in cs.columns:
        cs = cs.rename(columns={"country co": "country_code"})
    else:
        # try the exact from screenshot: "country_code"
        pass

if "country_code" not in cs.columns:
    raise ValueError("country_stats must contain an ISO2 column named country_code (or iso2).")

# population column
pop_col = None
for cand in ["population", "pop", "sp.pop.totl"]:
    if cand in cs.columns:
        pop_col = cand
        break
if pop_col is None:
    raise ValueError("country_stats must contain a population column (expected 'population').")

cs["country_code"] = cs["country_code"].astype(str).str.strip()
cs[pop_col] = pd.to_numeric(cs[pop_col], errors="coerce")

pop_keep = cs[["country_code", pop_col]].drop_duplicates(subset=["country_code"])
pop_keep = pop_keep.rename(columns={pop_col: "population"})

panel = panel.merge(pop_keep, on="country_code", how="left")
panel["log_population"] = np.log(panel["population"].where(panel["population"] > 0))

print("Using country_stats:", os.path.basename(country_stats_path))
print("Share missing population:", round(panel["population"].isna().mean(), 3))

# -----------------------------
# 4) Poverty robustness (optional): SI.POV.DDAY from data/poverty.*
#    We will do nearest-year match within +/-2 years (because poverty not annual for many countries)
# -----------------------------
poverty_candidates = (
    glob.glob(os.path.join(DATA_REPO_DIR, "poverty*.csv")) +
    glob.glob(os.path.join(DATA_REPO_DIR, "poverty*.xlsx")) +
    glob.glob(os.path.join(DATA_REPO_DIR, "poverty*.xls"))
)

if len(poverty_candidates) > 0:
    poverty_path = poverty_candidates[0]
    print("Found poverty file:", os.path.basename(poverty_path))

    pov_long = wdi_long_from_file(poverty_path, "SI.POV.DDAY", "poverty_rate")

    # need iso3->iso2 mapping: use master (should contain iso3 sometimes) OR infer via your master file
    # easiest: use your existing country_master* which usually has iso3 + country_code
    map_candidates = [
        os.path.join(REPO_DIR, "outputs", "country_master_with_finance_and_institutions.csv"),
        os.path.join(REPO_DIR, "outputs", "country_master_with_finance.csv"),
        os.path.join(REPO_DIR, "outputs", "country_master.csv"),
    ]
    map_path = find_first_existing(map_candidates)
    if map_path is None:
        print("WARNING: no iso3->iso2 mapping file found; skipping poverty merge.")
    else:
        m = pd.read_csv(map_path)
        m = norm_cols(m)
        m.columns = [c.lower().strip() for c in m.columns]

        if "iso3" not in m.columns:
            print("WARNING: mapping file has no iso3; skipping poverty merge.")
        else:
            if "country_code" not in m.columns:
                if "iso2" in m.columns:
                    m = m.rename(columns={"iso2": "country_code"})
                else:
                    print("WARNING: mapping file has no country_code/iso2; skipping poverty merge.")
                    m = None

            if m is not None:
                iso_map = m[["iso3", "country_code"]].drop_duplicates()
                iso_map["iso3"] = iso_map["iso3"].astype(str).str.strip()
                iso_map["country_code"] = iso_map["country_code"].astype(str).str.strip()

                pov_long["iso3"] = pov_long["iso3"].astype(str).str.strip()
                pov_long = pov_long.merge(iso_map, on="iso3", how="left")

                print("Share missing ISO2 in poverty after mapping:", round(pov_long["country_code"].isna().mean(), 3))

                pov_long = pov_long.dropna(subset=["country_code"])
                pov_long = pov_long[["country_code", "year", "poverty_rate"]].drop_duplicates()

                panel = nearest_year_merge(
                    left=panel,
                    right=pov_long,
                    on_keys=["country_code"],
                    year_col="year",
                    max_gap=2
                )

                print("Share missing poverty_rate (nearest-year):", round(panel["poverty_rate"].isna().mean(), 3))
else:
    print("No poverty file found in data/. Skipping poverty merge.")

# -----------------------------
# 5) Clean final columns + save
# -----------------------------
# main analysis vars
keep_cols = [
    "country_code", "year",
    "n_loans", "total_loan_amount", "log_total_loan_amount",
    "log_gdp_pc",
    "population", "log_population",
]

# add Z columns
keep_cols += z_cols

# add poverty if present
if "poverty_rate" in panel.columns:
    keep_cols += ["poverty_rate"]

# keep only what exists
keep_cols = [c for c in keep_cols if c in panel.columns]
final = panel.loc[:, keep_cols].copy()

# ensure numeric types
num_cols = [c for c in final.columns if c not in ["country_code"]]
for c in num_cols:
    final[c] = pd.to_numeric(final[c], errors="coerce")

final = final.sort_values(["country_code", "year"]).reset_index(drop=True)

final.to_csv(OUT_PATH, index=False)
print("--------------------------------------------------")
print("Saved final panel:", OUT_PATH)
print("Final rows:", len(final))
print("Unique countries:", final["country_code"].nunique())
print("Year range:", int(final["year"].min()), "to", int(final["year"].max()))
print("Missingness summary:")
for c in keep_cols:
    if c not in ["country_code", "year"]:
        print(f"  {c}: {round(final[c].isna().mean(), 3)}")