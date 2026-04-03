import json
from pathlib import Path

import pandas as pd
import streamlit as st

_JSON_PATH = Path("backend_predictor_listings/price_predictor/json_outputs/listings_predictions.json")
_CSV_PATH  = Path("data/final.csv")

# Fields from the JSON that override / enrich the CSV
_JSON_ENRICH_COLS = [
    "predicted_price",
    "predicted_price_lower",
    "predicted_price_upper",
    "valuation_pct",
    "median_similar",
    "median_months_back",
    "median_sample_size",
    "median_old",
]


@st.cache_data
def load_all_data():
    """
    Load the full active HDB listings dataset with predictions and amenity data.

    Strategy
    --------
    Base layer  : final.csv  — 1,283 listings across all flat types (including 4 ROOM
                               and MULTI-GENERATION which are absent from the JSON).
                               Contains all amenity proximity columns.

    Enrichment  : listings_predictions.json  — 895 listings from the latest model run.
                  Provides more accurate predictions, 95% CI bounds, and the full
                  median breakdown (median_similar, median_months_back, etc.).

    Merge key   : address + flat_type  (749 matches; 4-ROOM listings fall back to
                  CSV predicted_price and have null CI / median breakdown columns).

    Returns
    -------
    df   : cleaned DataFrame ready for scoring and display
    None : placeholder kept for call-site compatibility
    """
    # ── 1. Load base CSV ──────────────────────────────────────────────────────
    df = pd.read_csv(_CSV_PATH)
    df.columns = df.columns.str.strip()

    # ── 2. Load JSON enrichment fields ───────────────────────────────────────
    with open(_JSON_PATH) as f:
        jdata = json.load(f)
    jdf = pd.DataFrame(jdata)

    # Build merge key (strip whitespace to avoid phantom mismatches)
    df["_merge_key"]  = df["address"].str.strip()  + "|" + df["flat_type"].str.strip()
    jdf["_merge_key"] = jdf["address"].str.strip()  + "|" + jdf["flat_type"].str.strip()

    # Deduplicate JSON on the merge key (keep first occurrence)
    json_enrich = (
        jdf[["_merge_key"] + _JSON_ENRICH_COLS]
        .drop_duplicates(subset="_merge_key", keep="first")
    )

    # Suffix JSON columns so we can prefer them over CSV for matched rows
    df = df.merge(json_enrich, on="_merge_key", how="left", suffixes=("", "_json"))
    df.drop(columns=["_merge_key"], inplace=True)

    # For matched rows, override CSV predictions with JSON values
    for col in _JSON_ENRICH_COLS:
        json_col = f"{col}_json"
        if json_col in df.columns:
            # Where the JSON value is not null, use it; otherwise keep CSV value
            mask = df[json_col].notna()
            if col in df.columns:
                df.loc[mask, col] = df.loc[mask, json_col]
            else:
                df[col] = df[json_col]
            df.drop(columns=[json_col], inplace=True)

    # Ensure enrichment-only columns exist even for unmatched rows (NaN = not available)
    for col in ["predicted_price_lower", "predicted_price_upper",
                "median_similar", "median_months_back", "median_sample_size", "median_old"]:
        if col not in df.columns:
            df[col] = float("nan")

    # ── 3. Normalise towns to UPPERCASE ──────────────────────────────────────
    df["town"] = df["town"].str.strip().str.upper()

    # ── 4. Numeric coercions ─────────────────────────────────────────────────
    df["floor_area_sqm"]  = pd.to_numeric(df["floor_area_sqm"],  errors="coerce").fillna(0).round().astype(int)
    df["asking_price"]    = pd.to_numeric(df["asking_price"],    errors="coerce").fillna(0)
    df["predicted_price"] = pd.to_numeric(df["predicted_price"], errors="coerce").fillna(0)
    df["valuation_pct"]   = pd.to_numeric(df.get("valuation_pct", 0), errors="coerce").fillna(0)

    for col in ("predicted_price_lower", "predicted_price_upper"):
        df[col] = pd.to_numeric(df[col], errors="coerce")   # stays NaN for 4-ROOM rows

    df["median_similar"] = pd.to_numeric(df["median_similar"], errors="coerce")  # nullable

    # ── 5. Derived / helper columns ───────────────────────────────────────────
    df["listing_id"]   = df.index.astype(str)
    df["storey_range"] = df["storey_midpoint"].fillna(0).astype(float).round().astype(int).astype(str)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    return df, None
