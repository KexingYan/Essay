import os
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = os.environ["ECO225_DATA_DIR"]

MASTER_PATH = "outputs/country_master.csv"
WB_PATH = os.path.join(DATA_DIR, "world_bank_data.csv")

# NEW: WGI Excel in your data folder (downloaded from WDI/WGI portal)
# Your screenshot filename: P_Data_Extract_From_World_Development_Indicators.xlsx
WGI_XLSX_PATTERN = "P_Data_Extract_From_World_Develop*.xls*"
WGI_YEAR_COL = "2019 [YR2019]"  # change year here if needed

# Keep your old output + also create a new “combined” output (recommended)
OUT_PATH_FINANCE = "outputs/country_master_with_finance.csv"
OUT_PATH_COMBINED = "outputs/country_master_with_finance_and_institutions.csv"

ACCESS_VARS = ["bank_branches_per_100k", "atms_per_100k", "bank_accounts_per_1000"]

# WGI series we want as institutional quality mechanism
WGI_SERIES = [
    "Rule of Law: Estimate",
    "Government Effectiveness: Estimate",
    "Political Stability and Absence of Violence/Terrorism: Estimate",
]

def safe_zscore(series):
    s = pd.to_numeric(series, errors="coerce")
    mu = s.mean(skipna=True)
    sd = s.std(skipna=True)
    if pd.isna(sd) or sd == 0:
        return pd.Series([np.nan] * len(s), index=s.index)
    return (s - mu) / sd


def pca_first_component_score(X):
    """
    Pure-numpy PCA score for first component.
    X: (n, k) matrix with no missing values.
    Returns scores (n,) normalized to mean 0 sd 1 (optional but nice).
    """
    # center columns
    Xc = X - X.mean(axis=0, keepdims=True)
    # SVD
    # Xc = U S Vt, first PC direction is Vt[0]
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    pc1_dir = Vt[0, :]
    scores = Xc @ pc1_dir

    # standardize scores for interpretability
    scores = (scores - scores.mean()) / (scores.std() if scores.std() != 0 else 1.0)
    return scores


def add_institutional_quality(df):
    """
    Load WGI/WDI governance indicators from Excel and merge into df by iso3.
    Adds:
      - rule_of_law, gov_effectiveness, political_stability
      - institutional_index (z-score average)
      - institutional_pca1 (PC1 score)
    """
    data_dir = Path(DATA_DIR)
    matches = list(data_dir.glob(WGI_XLSX_PATTERN))
    print("\n[WGI] matches =", matches)

    if len(matches) == 0:
        print("[WGI][WARNING] No WGI Excel found. Skipping institutional merge.")
        df["institutional_index"] = np.nan
        df["institutional_pca1"] = np.nan
        return df

    wgi_path = matches[0]
    print("[WGI] Loading:", wgi_path.name)

    # NOTE: requires openpyxl installed for .xlsx
    gov_raw = pd.read_excel(wgi_path)
    gov_raw.columns = gov_raw.columns.str.strip()

    # filter series
    gov = gov_raw[gov_raw["Series Name"].isin(WGI_SERIES)].copy()
    if WGI_YEAR_COL not in gov.columns:
        # show available year cols to debug
        year_like = [c for c in gov.columns if isinstance(c, str) and "[YR" in c]
        raise KeyError(f"[WGI] Year column not found: {WGI_YEAR_COL}. Example year cols: {year_like[:10]}")

    gov = gov[["Country Code", "Series Name", WGI_YEAR_COL]].copy()
    gov[WGI_YEAR_COL] = pd.to_numeric(gov[WGI_YEAR_COL], errors="coerce")

    # pivot to wide
    gov_wide = gov.pivot_table(
        index="Country Code",
        columns="Series Name",
        values=WGI_YEAR_COL,
        aggfunc="first"
    ).reset_index()

    gov_wide = gov_wide.rename(columns={
        "Country Code": "iso3",
        "Rule of Law: Estimate": "rule_of_law",
        "Government Effectiveness: Estimate": "gov_effectiveness",
        "Political Stability and Absence of Violence/Terrorism: Estimate": "political_stability"
    })

    # clean codes
    gov_wide["iso3"] = gov_wide["iso3"].astype(str).str.upper()
    df["iso3"] = df["iso3"].astype(str).str.upper()

    # merge
    df2 = df.merge(gov_wide, on="iso3", how="left")
    print("[WGI] After merge: missing rule_of_law =", df2["rule_of_law"].isna().sum())

    # institutional_index = mean(zscores)
    z_vars = ["rule_of_law", "gov_effectiveness", "political_stability"]
    for v in z_vars:
        df2[v + "_z"] = safe_zscore(df2[v])
    df2["institutional_index"] = df2[[v + "_z" for v in z_vars]].mean(axis=1, skipna=True)

    # PCA1 score (requires complete cases)
    complete = df2.dropna(subset=z_vars).copy()
    if complete.shape[0] < 5:
        print("[WGI][WARNING] Too few complete observations for PCA. institutional_pca1 will be NaN.")
        df2["institutional_pca1"] = np.nan
        return df2

    X = complete[z_vars].to_numpy(dtype=float)
    # compute PCA1 score
    scores = pca_first_component_score(X)
    complete["institutional_pca1"] = scores

    # explained variance ratio (optional, approximate)
    # variance explained by PC1 = (S1^2) / sum(S^2)
    Xc = X - X.mean(axis=0, keepdims=True)
    _, S, _ = np.linalg.svd(Xc, full_matrices=False)
    evr1 = (S[0] ** 2) / np.sum(S ** 2)
    print("[WGI] PCA explained variance (PC1):", evr1)

    df2 = df2.merge(
        complete[["iso3", "institutional_pca1"]],
        on="iso3",
        how="left"
    )

    print("[WGI] Institutional mechanism ready ✅")
    return df2


def main():
    df = pd.read_csv(MASTER_PATH)
    df.columns = df.columns.str.strip()

    # -----------------------
    # Load WB file robustly
    # -----------------------
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1"]
    wb = None
    for enc in encodings:
        try:
            wb = pd.read_csv(WB_PATH, encoding=enc)
            print("Loaded WB file with encoding:", enc)
            break
        except UnicodeDecodeError:
            continue

    if wb is None:
        raise ValueError("Could not read WB CSV with common encodings.")

    wb.columns = wb.columns.str.strip()
    wb = wb.replace("..", np.nan)

    # -----------------------
    # detect year columns
    # -----------------------
    year_cols = [c for c in wb.columns if str(c)[:4].isdigit()]
    wb[year_cols] = wb[year_cols].apply(pd.to_numeric, errors="coerce")

    years = sorted([int(str(c)[:4]) for c in year_cols])
    recent_years = [y for y in years if 2018 <= y <= 2022]
    recent_cols = [c for c in year_cols if int(str(c)[:4]) in recent_years]
    print("Using years:", recent_years)

    wb["avg_value"] = wb[recent_cols].mean(axis=1, skipna=True)

    keep_series = {
        "GFDD.AI.02": "bank_branches_per_100k",
        "GFDD.AI.25": "atms_per_100k",
        "GFDD.AI.01": "bank_accounts_per_1000",
        "GFDD.DI.14": "credit_private_gdp"
    }

    wb = wb[wb["Series Code"].isin(keep_series.keys())].copy()
    wb["variable"] = wb["Series Code"].map(keep_series)

    # -----------------------
    # pivot to country level
    # -----------------------
    wb_country = (
        wb.pivot_table(
            index="Country Code",
            columns="variable",
            values="avg_value",
            aggfunc="first"
        )
        .reset_index()
        .rename(columns={"Country Code": "iso3"})
    )

    wb_country.columns = wb_country.columns.str.strip()

    # -----------------------
    # merge into master
    # -----------------------
    df = df.merge(wb_country, on="iso3", how="left")
    df.columns = df.columns.str.strip()

    # ----------------------------
    # Build Financial Access Index (Z)
    # ----------------------------
    found = [c for c in ACCESS_VARS if c in df.columns]
    missing = [c for c in ACCESS_VARS if c not in df.columns]
    print("\n[DEBUG] ACCESS_VARS found:", found)
    print("[DEBUG] ACCESS_VARS missing:", missing)

    if len(found) == 0:
        df["financial_access_index"] = np.nan
        print("[WARNING] No access vars found. financial_access_index will be all NaN.")
    else:
        z_cols = []
        for c in found:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            df[c + "_z"] = safe_zscore(df[c])
            z_cols.append(c + "_z")
        df["financial_access_index"] = df[z_cols].mean(axis=1, skipna=True)

    print("[DEBUG] financial_access_index coverage:", df["financial_access_index"].notna().mean())

    # Save finance-only
    df.to_csv(OUT_PATH_FINANCE, index=False)
    print("Saved:", OUT_PATH_FINANCE)

    # ----------------------------
    # NEW: add institutional quality mechanism
    # ----------------------------
    df2 = add_institutional_quality(df)

    # Save combined
    df2.to_csv(OUT_PATH_COMBINED, index=False)
    print("Saved:", OUT_PATH_COMBINED)


if __name__ == "__main__":
    main()