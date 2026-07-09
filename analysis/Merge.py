# ECO225 — Step 1: Load, clean, and merge (country-level master table)
# Run this in VS Code. It will create:
#   outputs/country_master.csv
#   outputs/merge_diagnostics.txt
# ECO225 – Step 1: Load, clean, aggregate, and merge (FINAL)
# Output: outputs/country_master.csv

import os
import pandas as pd
from pathlib import Path
import pycountry

# =========================
# Paths
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("ECO225_DATA_DIR", BASE_DIR / "data"))
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"[step1] Using data directory: {DATA_DIR}")
print(f"[step1] Using output directory: {OUTPUT_DIR}")

# Files
LOANS_FILE = DATA_DIR / "loans.csv"
COUNTRY_STATS_FILE = DATA_DIR / "country_stats.csv"
MPI_FILE = DATA_DIR / "MPI_national.csv"

# =========================
# Load CSVs
# =========================
loans = pd.read_csv(
    LOANS_FILE,
    usecols=["loan_id", "loan_amount", "country_code"]
)

country_stats = pd.read_csv(
    COUNTRY_STATS_FILE,
    usecols=["country_code", "population", "population_below_poverty_line"]
)

mpi = pd.read_csv(MPI_FILE)

print("[debug] loans columns:", loans.columns.tolist())
print("[debug] country_stats columns:", country_stats.columns.tolist())
print("[debug] mpi columns:", mpi.columns.tolist())

# =========================
# Minimal cleaning
# =========================
for df in [loans, country_stats]:
    df["country_code"] = (
        df["country_code"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

loans["loan_amount"] = pd.to_numeric(loans["loan_amount"], errors="coerce")
country_stats["population"] = pd.to_numeric(country_stats["population"], errors="coerce")
country_stats["population_below_poverty_line"] = pd.to_numeric(
    country_stats["population_below_poverty_line"],
    errors="coerce"
)

# =========================
# Aggregate loans to country level (Y)
# =========================
country_loans = (
    loans.dropna(subset=["country_code"])
         .groupby("country_code", as_index=False)
         .agg(
             n_loans=("loan_id", "count"),
             total_loan_amount=("loan_amount", "sum")
         )
)

# =========================
# Construct poverty rate (X)
# =========================
country_stats["poverty_rate"] = (
    pd.to_numeric(country_stats["population_below_poverty_line"], errors="coerce") / 100
)



# =========================
# Merge loans + poverty (ISO2)
# =========================
master = country_loans.merge(
    country_stats,
    on="country_code",
    how="left"
)

# =========================
# ISO2 → ISO3 conversion (KEY FIX)
# =========================
def iso2_to_iso3(x):
    try:
        return pycountry.countries.get(alpha_2=x).alpha_3
    except:
        return None

master["iso3"] = master["country_code"].apply(iso2_to_iso3)

print("[check] non-missing iso3:",
      master["iso3"].notna().sum(), "/", len(master))

# =========================
# Prepare MPI (ISO3)
# =========================
mpi = mpi.rename(columns={"ISO": "iso3"})
mpi["iso3"] = mpi["iso3"].astype(str).str.strip().str.upper()

mpi["MPI Urban"] = pd.to_numeric(mpi["MPI Urban"], errors="coerce")
mpi["MPI Rural"] = pd.to_numeric(mpi["MPI Rural"], errors="coerce")

mpi["urban_rural_gap"] = mpi["MPI Rural"] - mpi["MPI Urban"]

mpi_keep = mpi[["iso3", "urban_rural_gap"]]

# =========================
# Merge MPI (Z)
# =========================
master = master.merge(
    mpi_keep,
    on="iso3",
    how="left"
)

# =========================
# Save output
# =========================
out_file = OUTPUT_DIR / "country_master.csv"
master.to_csv(out_file, index=False)

print(f"[step1] Saved: {out_file}")
print("[step1] Final master shape:", master.shape)
print("[step1] Non-missing poverty_rate:",
      master["poverty_rate"].notna().sum(), "/", len(master))
print("[step1] Non-missing urban_rural_gap:",
      master["urban_rural_gap"].notna().sum(), "/", len(master))

print(master.head())
