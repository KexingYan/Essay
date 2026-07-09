# build_final_panel_loan_level.py
# Build loan-level panel for ECO225 Project 2
# Kiva loans (loan-level) + GDPpc (country-year) + institutions/finance (country-level) + population

import os
import glob
from pathlib import Path
import pandas as pd
import numpy as np

# -----------------------------
# Paths (relative to repo root, portable across machines)
# -----------------------------
REPO_DIR = str(Path(__file__).resolve().parents[1])
DATA_DIR_D = REPO_DIR  # no separate external data drive on this machine; same dir

DATA_REPO_DIR = os.path.join(REPO_DIR, "data")
OUT_DIR = os.path.join(REPO_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

OUT_PATH = os.path.join(OUT_DIR, "final_panel_loan_level.csv")

# existing country-year GDP panel
GDP_PANEL_PATH = os.path.join(REPO_DIR, "outputs", "country_year_kiva_gdppc.csv")

# existing master with institutions
MASTER_PATH = os.path.join(REPO_DIR, "outputs", "country_master_with_finance_and_institutions.csv")

# -----------------------------
# Helpers
# -----------------------------
def norm_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def load_any(path):
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)

def find_first_existing(candidates):
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

# -----------------------------
# 1) Load raw Kiva loans
# -----------------------------
loan_candidates = [
    os.path.join(DATA_REPO_DIR, "loans.csv"),
    os.path.join(DATA_REPO_DIR, "kiva_loans.csv"),
    os.path.join(DATA_REPO_DIR, "kiva.csv"),
    os.path.join(DATA_DIR_D, "loans.csv"),
    os.path.join(DATA_DIR_D, "kiva_loans.csv"),
    os.path.join(DATA_DIR_D, "kiva.csv"),
]

loan_path = find_first_existing(loan_candidates)
if loan_path is None:
    raise FileNotFoundError("Could not find raw loan-level Kiva file (expected loans.csv / kiva_loans.csv).")

loans = load_any(loan_path)
loans = norm_cols(loans)
loans.columns = [c.lower().strip() for c in loans.columns]

print("Using loan file:", loan_path)
print("Raw loan rows:", len(loans))
print("Loan columns:", list(loans.columns))

# expected Kiva columns
# try to detect country code
if "country_code" not in loans.columns:
    if "country code" in loans.columns:
        loans = loans.rename(columns={"country code": "country_code"})
    elif "country" in loans.columns:
        # fallback only if raw loans have country name but not country_code
        pass

# detect date column
date_col = None
for cand in ["posted_time", "date", "funded_time", "planned_expiration_time"]:
    if cand in loans.columns:
        date_col = cand
        break
if date_col is None:
    raise ValueError("Could not find a loan date column such as posted_time/date/funded_time.")

# detect amount column
amt_col = None
for cand in ["loan_amount", "funded_amount"]:
    if cand in loans.columns:
        amt_col = cand
        break
if amt_col is None:
    raise ValueError("Could not find loan amount column (expected loan_amount or funded_amount).")

# parse year
loans[date_col] = pd.to_datetime(loans[date_col], errors="coerce")
loans["year"] = loans[date_col].dt.year.astype("Int64")

# keep analysis years
loans = loans[loans["year"].between(2013, 2017, inclusive="both")].copy()

# clean amount
loans[amt_col] = pd.to_numeric(loans[amt_col], errors="coerce")
loans = loans[loans[amt_col] > 0].copy()
loans["loan_amount"] = loans[amt_col]
loans["log_loan_amount"] = np.log(loans["loan_amount"])

# -----------------------------
# 2) Attach country_code if missing
# -----------------------------
if "country_code" not in loans.columns:
    if "country" not in loans.columns:
        raise ValueError("Raw loans must contain either country_code or country.")
    
    # use master file as mapping if possible
    if not os.path.exists(MASTER_PATH):
        raise FileNotFoundError(f"Missing master file for mapping: {MASTER_PATH}")
    
    master_map = pd.read_csv(MASTER_PATH)
    master_map = norm_cols(master_map)
    master_map.columns = [c.lower().strip() for c in master_map.columns]

    if "country" in master_map.columns and "country_code" in master_map.columns:
        tmp = master_map[["country", "country_code"]].drop_duplicates()
        tmp["country"] = tmp["country"].astype(str).str.strip()
        loans["country"] = loans["country"].astype(str).str.strip()
        loans = loans.merge(tmp, on="country", how="left")
    else:
        raise ValueError("Could not map country names to country_code because master file lacks country and country_code.")

if "country_code" not in loans.columns:
    raise ValueError("country_code is still missing after mapping.")

loans["country_code"] = loans["country_code"].astype(str).str.strip()

# optional loan id
if "id" in loans.columns:
    loans = loans.rename(columns={"id": "loan_id"})
else:
    loans["loan_id"] = np.arange(len(loans)) + 1

# -----------------------------
# 3) Load GDP country-year data
# -----------------------------
if not os.path.exists(GDP_PANEL_PATH):
    raise FileNotFoundError(f"Missing GDP panel: {GDP_PANEL_PATH}")

gdp_panel = pd.read_csv(GDP_PANEL_PATH)
gdp_panel = norm_cols(gdp_panel)
gdp_panel.columns = [c.lower().strip() for c in gdp_panel.columns]

# expected: country_code, year, log_gdp_pc
needed = ["country_code", "year", "log_gdp_pc"]
for c in needed:
    if c not in gdp_panel.columns:
        raise ValueError(f"Missing {c} in GDP panel.")

gdp_keep = gdp_panel[["country_code", "year", "log_gdp_pc"]].drop_duplicates()
gdp_keep["country_code"] = gdp_keep["country_code"].astype(str).str.strip()
gdp_keep["year"] = pd.to_numeric(gdp_keep["year"], errors="coerce").astype("Int64")

loans = loans.merge(gdp_keep, on=["country_code", "year"], how="left")

# -----------------------------
# 4) Load institutions/finance master
# -----------------------------
if not os.path.exists(MASTER_PATH):
    raise FileNotFoundError(f"Missing master file: {MASTER_PATH}")

master = pd.read_csv(MASTER_PATH)
master = norm_cols(master)
master.columns = [c.lower().strip() for c in master.columns]

if "country_code" not in master.columns:
    if "iso2" in master.columns:
        master = master.rename(columns={"iso2": "country_code"})
    else:
        raise ValueError("Master file must contain country_code (or iso2).")

master["country_code"] = master["country_code"].astype(str).str.strip()

z_cols = []
for cand in ["institutional_pca1", "institutional_index", "financial_access_index"]:
    if cand in master.columns:
        z_cols.append(cand)

if len(z_cols) == 0:
    raise ValueError("No Z columns found in master file.")

z_keep = master[["country_code"] + z_cols].drop_duplicates(subset=["country_code"])
loans = loans.merge(z_keep, on="country_code", how="left")

# -----------------------------
# 5) Load population
# -----------------------------
country_stats_candidates = [
    os.path.join(DATA_REPO_DIR, "country_stats.csv"),
    os.path.join(DATA_REPO_DIR, "country_stats.xlsx"),
    os.path.join(DATA_DIR_D, "country_stats.csv"),
    os.path.join(DATA_DIR_D, "country_stats.xlsx"),
]

country_stats_path = find_first_existing(country_stats_candidates)
if country_stats_path is None:
    raise FileNotFoundError("Could not find country_stats file.")

cs = load_any(country_stats_path)
cs = norm_cols(cs)
cs.columns = [c.lower().strip() for c in cs.columns]

if "country_code" not in cs.columns:
    if "iso2" in cs.columns:
        cs = cs.rename(columns={"iso2": "country_code"})
    elif "country co" in cs.columns:
        cs = cs.rename(columns={"country co": "country_code"})

if "country_code" not in cs.columns:
    raise ValueError("country_stats must contain country_code (or iso2).")

pop_col = None
for cand in ["population", "pop", "sp.pop.totl"]:
    if cand in cs.columns:
        pop_col = cand
        break
if pop_col is None:
    raise ValueError("country_stats must contain a population column.")

cs["country_code"] = cs["country_code"].astype(str).str.strip()
cs[pop_col] = pd.to_numeric(cs[pop_col], errors="coerce")

pop_keep = cs[["country_code", pop_col]].drop_duplicates(subset=["country_code"])
pop_keep = pop_keep.rename(columns={pop_col: "population"})
loans = loans.merge(pop_keep, on="country_code", how="left")
loans["log_population"] = np.log(loans["population"].where(loans["population"] > 0))

# -----------------------------
# 6) Final clean
# -----------------------------
loans["country_year_id"] = loans["country_code"].astype(str) + "_" + loans["year"].astype(str)

keep_cols = [
    "loan_id",
    "country_code",
    "year",
    "loan_amount",
    "log_loan_amount",
    "log_gdp_pc",
    "population",
    "log_population",
    "country_year_id"
] + z_cols

keep_cols = [c for c in keep_cols if c in loans.columns]
final = loans[keep_cols].copy()

num_cols = [c for c in final.columns if c not in ["loan_id", "country_code", "country_year_id"]]
for c in num_cols:
    final[c] = pd.to_numeric(final[c], errors="coerce")

final = final.sort_values(["country_code", "year"]).reset_index(drop=True)
final.to_csv(OUT_PATH, index=False)

print("-" * 60)
print("Saved loan-level panel to:", OUT_PATH)
print("Final rows:", len(final))
print("Unique countries:", final["country_code"].nunique())
print("Year range:", int(final["year"].min()), "to", int(final["year"].max()))
print("Missingness:")
for c in final.columns:
    if c not in ["loan_id", "country_code", "country_year_id"]:
        print(f"  {c}: {round(final[c].isna().mean(), 3)}")