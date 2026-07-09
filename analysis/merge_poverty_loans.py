import os
import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


DATA_DIR = Path(os.getenv("ECO225_DATA_DIR", BASE_DIR / "data"))

print(f"Using data directory: {DATA_DIR}")

loans = pd.read_csv(DATA_DIR / "loans.csv")
country_stats = pd.read_csv(DATA_DIR / "country_stats.csv")


# 3. Merge on country_code
merged = loans.merge(
    country_stats,
    on="country_code",
    how="inner"   # very important: only keep countries with stats
)

# 4. Post-merge observation count
print("\nPost-merge size:")
print(f"Merged dataset: {merged.shape[0]} observations")

# 5. Optional sanity checks
print("\nNumber of unique countries after merge:")
print(merged["country_code"].nunique())
