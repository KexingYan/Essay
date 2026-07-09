# analysis/build_final_panel.py
# Purpose: Build ONE final country-year panel by merging:
# (1) Kiva country-year outcomes + GDPpc (already created)
# (2) Population (WDI: SP.POP.TOTL) -> to compute per-capita outcomes
# (3) Z variables (financial_access_index, institutional_pca1) from your country_master file (cross-section)
# (4) Poverty robustness (WDI: SI.POV.DDAY; optional nearest-year fill)

import os
import re
import glob
import pandas as pd
import numpy as np

# -------------------------------
# Paths (edit only if your repo path changes)
# -------------------------------
REPO_DIR = r"C:\Users\Klicy\github-classroom\ECO225-2026\eco225-project-KexingYan"
DATA_REPO = os.path.join(REPO_DIR, "data")
OUT_DIR = os.path.join(REPO_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

IN_PANEL = os.path.join(OUT_DIR, "country_year_kiva_gdppc.csv")
OUT_FINAL = os.path.join(OUT_DIR, "final_panel_country_year.csv")

print("Loading base panel:", IN_PANEL)
base = pd.read_csv(IN_PANEL)

# standardize types
base["country_code"] = base["country_code"].astype(str).str.strip()
base["year"] = pd.to_numeric(base["year"], errors="coerce").astype("Int64")

# -------------------------------
# Helper: load WDI-style extract (wide) and convert to long for a given Series Code
# -------------------------------
def load_wdi_series_long(path, series_code, value_name):
    if path.lower().endswith(".csv"):
        raw = pd.read_csv(path)
    else:
        raw = pd.read_excel(path)

    raw.columns = [str(c).strip() for c in raw.columns]

    # defensive: sometimes columns may be slightly different
    for col in ["Series Code", "Country Code", "Country Name"]:
        if col not in raw.columns:
            raise ValueError(f"Column '{col}' not found in {path}. Columns: {raw.columns.tolist()[:20]}")

    raw["Series Code"] = raw["Series Code"].astype(str).str.strip()

    df = raw.loc[raw["Series Code"] == series_code].copy()
    if df.empty:
        raise ValueError(f"Series Code {series_code} not found in {os.path.basename(path)}")

    year_cols = [c for c in df.columns if re.search(r"\[YR\d{4}\]", str(c))]
    if len(year_cols) == 0:
        raise ValueError(f"No year columns like '[YR2014]' found in {os.path.basename(path)}")

    long = df.melt(
        id_vars=["Country Name", "Country Code", "Series Code"],
        value_vars=year_cols,
        var_name="year_col",
        value_name=value_name
    )

    long["year"] = long["year_col"].astype(str).str.extract(r"(\d{4})").astype(float).astype("Int64")

    # WDI missing often ".."
    long[value_name] = pd.to_numeric(long[value_name].replace("..", np.nan), errors="coerce")

    long = long.rename(columns={"Country Code": "iso3", "Country Name": "country_name"})
    long = long[["iso3", "country_name", "year", value_name]].dropna(subset=["iso3", "year"])
    return long

# -------------------------------
# Helper: ISO3 -> ISO2 mapping from your existing country master output
# -------------------------------
def load_iso3_to_iso2_map(repo_dir):
    candidates = [
        os.path.join(repo_dir, "outputs", "country_master_with_finance_and_institutions.csv"),
        os.path.join(repo_dir, "outputs", "country_master_with_finance.csv"),
        os.path.join(repo_dir, "outputs", "country_master.csv"),
    ]
    for p in candidates:
        if os.path.exists(p):
            m = pd.read_csv(p)
            m.columns = [c.lower().strip() for c in m.columns]
            if "iso3" in m.columns and ("country_code" in m.columns or "iso2" in m.columns):
                if "iso2" in m.columns and "country_code" not in m.columns:
                    m = m.rename(columns={"iso2": "country_code"})
                m["iso3"] = m["iso3"].astype(str).str.strip()
                m["country_code"] = m["country_code"].astype(str).str.strip()
                return m[["iso3", "country_code"]].drop_duplicates()
    raise FileNotFoundError("No mapping file found: expected country_master*.csv in outputs/")

iso_map = load_iso3_to_iso2_map(REPO_DIR)

# -------------------------------
# (A) Merge POPULATION (SP.POP.TOTL) from data/wdi.*
# -------------------------------
wdi_candidates = (
    glob.glob(os.path.join(DATA_REPO, "wdi*.xlsx")) +
    glob.glob(os.path.join(DATA_REPO, "wdi*.xls")) +
    glob.glob(os.path.join(DATA_REPO, "wdi*.csv"))
)
if len(wdi_candidates) == 0:
    raise FileNotFoundError(f"No WDI file found in {DATA_REPO}. Expected wdi*.xlsx/xls/csv")

wdi_path = wdi_candidates[0]
print("Using WDI file:", wdi_path)

pop_long = load_wdi_series_long(wdi_path, "SP.POP.TOTL", "population")
print("Population rows:", len(pop_long), "| year range:", int(pop_long["year"].min()), "-", int(pop_long["year"].max()))

# map iso3 -> iso2 to match Kiva
pop_long = pop_long.merge(iso_map, on="iso3", how="left")
pop_long["country_code"] = pop_long["country_code"].astype(str).str.strip()
pop = pop_long.dropna(subset=["country_code"])[["country_code", "year", "population"]].copy()

# merge to base (exact year)
panel = base.merge(pop, on=["country_code", "year"], how="left")
panel["population"] = pd.to_numeric(panel["population"], errors="coerce")
print("Share missing population:", round(float(panel["population"].isna().mean()), 3))

# per-capita outcomes
panel["total_loan_amount"] = pd.to_numeric(panel["total_loan_amount"], errors="coerce")
panel["n_loans"] = pd.to_numeric(panel["n_loans"], errors="coerce")

panel["loan_amount_per_capita"] = panel["total_loan_amount"] / panel["population"]
panel["loans_per_capita"] = panel["n_loans"] / panel["population"]

# log outcomes (avoid log(0))
panel["log_loan_amount_pc"] = np.log(panel["loan_amount_per_capita"].where(panel["loan_amount_per_capita"] > 0))
panel["log_loans_pc"] = np.log(panel["loans_per_capita"].where(panel["loans_per_capita"] > 0))
panel["log_total_loan_amount"] = np.log(panel["total_loan_amount"].where(panel["total_loan_amount"] > 0))

# -------------------------------
# (B) Merge Z (cross-section) from country_master_with_finance_and_institutions.csv
# -------------------------------
z_path = os.path.join(REPO_DIR, "outputs", "country_master_with_finance_and_institutions.csv")
if not os.path.exists(z_path):
    # fallback
    z_path = os.path.join(REPO_DIR, "outputs", "country_master_with_finance.csv")

print("Using Z source:", z_path)
z = pd.read_csv(z_path)
z.columns = [c.lower().strip() for c in z.columns]

# keep the Z columns if they exist
z_keep = ["country_code", "financial_access_index", "institutional_pca1", "institutional_index"]
z_keep = [c for c in z_keep if c in z.columns]
if "country_code" not in z_keep:
    raise ValueError("Z file does not have 'country_code' (ISO2).")

z_sub = z[z_keep].copy()
z_sub["country_code"] = z_sub["country_code"].astype(str).str.strip()
z_sub = z_sub.drop_duplicates(subset=["country_code"])

panel = panel.merge(z_sub, on="country_code", how="left")

# -------------------------------
# (C) Poverty robustness from data/poverty.*
#     Main: SI.POV.DDAY (headcount at $3/day, 2021 PPP)
#     Optional: nearest-year fill within +/- 3 years
# -------------------------------
poverty_candidates = (
    glob.glob(os.path.join(DATA_REPO, "poverty*.xlsx")) +
    glob.glob(os.path.join(DATA_REPO, "poverty*.xls")) +
    glob.glob(os.path.join(DATA_REPO, "poverty*.csv"))
)
if len(poverty_candidates) == 0:
    raise FileNotFoundError(f"No poverty file found in {DATA_REPO}. Expected poverty*.xlsx/xls/csv")

poverty_path = poverty_candidates[0]
print("Using poverty file:", poverty_path)

pov_long = load_wdi_series_long(poverty_path, "SI.POV.DDAY", "poverty_rate_3day")
print("Poverty rows:", len(pov_long), "| year range:", int(pov_long["year"].min()), "-", int(pov_long["year"].max()))

pov_long = pov_long.merge(iso_map, on="iso3", how="left")
pov_long["country_code"] = pov_long["country_code"].astype(str).str.strip()
pov = pov_long.dropna(subset=["country_code"])[["country_code", "year", "poverty_rate_3day"]].copy()

# exact-year merge first
panel = panel.merge(pov, on=["country_code", "year"], how="left")
panel["poverty_rate_3day"] = pd.to_numeric(panel["poverty_rate_3day"], errors="coerce")

# nearest-year fill within +/-3 years (robustness convenience)
def nearest_year_fill(df, value_col, max_gap=3):
    df = df.sort_values(["country_code", "year"]).copy()
    # for each row with missing value, look up nearest year within same country
    out = []
    for cc, g in df.groupby("country_code", sort=False):
        years = g["year"].to_numpy()
        vals = g[value_col].to_numpy()
        filled = vals.copy()

        non_missing_idx = np.where(~pd.isna(vals))[0]
        if len(non_missing_idx) == 0:
            g[value_col + "_filled"] = filled
            g[value_col + "_fill_gap"] = np.nan
            out.append(g)
            continue

        non_missing_years = years[non_missing_idx]
        non_missing_vals = vals[non_missing_idx]

        gaps = np.full(len(g), np.nan, dtype=float)

        for i in range(len(g)):
            if pd.isna(filled[i]):
                # find nearest observed year
                diffs = np.abs(non_missing_years - years[i])
                j = np.argmin(diffs)
                if diffs[j] <= max_gap:
                    filled[i] = non_missing_vals[j]
                    gaps[i] = float(diffs[j])

        g[value_col + "_filled"] = filled
        g[value_col + "_fill_gap"] = gaps
        out.append(g)

    return pd.concat(out, ignore_index=True)

panel = nearest_year_fill(panel, "poverty_rate_3day", max_gap=3)

print("Share missing poverty (exact):", round(float(panel["poverty_rate_3day"].isna().mean()), 3))
print("Share missing poverty (filled +/-3y):", round(float(pd.Series(panel["poverty_rate_3day_filled"]).isna().mean()), 3))

# -------------------------------
# Final cleanup + save
# -------------------------------
# Ensure year is int for merges/regressions
panel["year"] = pd.to_numeric(panel["year"], errors="coerce").astype("Int64")

# Useful “ready” indicators
panel["has_pop"] = (~panel["population"].isna()).astype(int)
panel["has_gdppc"] = (~panel["gdp_pc_const2015"].isna()).astype(int)
panel["has_poverty_exact"] = (~panel["poverty_rate_3day"].isna()).astype(int)
panel["has_poverty_filled"] = (~pd.Series(panel["poverty_rate_3day_filled"]).isna()).astype(int)

# Suggested regression sample (main spec with GDPpc + population so per-capita is defined)
reg_ready = panel.dropna(subset=["log_gdp_pc", "population", "log_total_loan_amount"]).copy()
print("Main regression-ready rows (log_total_loan_amount ~ log_gdp_pc):", len(reg_ready))

panel.to_csv(OUT_FINAL, index=False)
print("Saved final panel:", OUT_FINAL)

# quick peek
print(panel.head(10))