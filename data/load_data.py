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
    Base layer  : final.csv
    Enrichment  : listings_predictions.json

    Since the JSON does not contain address, we merge using shared listing-level
    fields that exist in both sources:
        town, flat_type, floor_area_sqm, lease_commence_date, remaining_lease,
        storey_midpoint, lat, lon, asking_price

    Returns
    -------
    df   : cleaned DataFrame ready for scoring and display
    None : placeholder kept for call-site compatibility
    """
    # ── 1. Load base CSV ──────────────────────────────────────────────────────
    df = pd.read_csv(_CSV_PATH)
    df.columns = df.columns.str.strip()

    # Drop accidental unnamed index columns
    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed")]

    # Standardise postal column name
    if "postal_code" not in df.columns and "postal" in df.columns:
        df["postal_code"] = df["postal"]

    # ── 2. Load JSON enrichment fields ───────────────────────────────────────
    with open(_JSON_PATH) as f:
        jdata = json.load(f)
    jdf = pd.DataFrame(jdata)
    jdf.columns = jdf.columns.str.strip()

    # ── 3. Build merge key from shared columns ───────────────────────────────
    merge_cols = [
        "town",
        "flat_type",
        "floor_area_sqm",
        "lease_commence_date",
        "remaining_lease",
        "storey_midpoint",
        "lat",
        "lon",
        "asking_price",
    ]

    for col in merge_cols:
        if col not in df.columns:
            raise KeyError(f"'{col}' missing in CSV. Columns: {list(df.columns)}")
        if col not in jdf.columns:
            raise KeyError(f"'{col}' missing in JSON. Columns: {list(jdf.columns)}")

    # Normalise strings used in merge
    for col in ["town", "flat_type", "remaining_lease"]:
        df[col] = df[col].astype(str).str.strip()
        jdf[col] = jdf[col].astype(str).str.strip()

    # Normalise numerics used in merge
    numeric_merge_cols = [
        "floor_area_sqm",
        "lease_commence_date",
        "storey_midpoint",
        "lat",
        "lon",
        "asking_price",
    ]
    for col in numeric_merge_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        jdf[col] = pd.to_numeric(jdf[col], errors="coerce")

    df["_merge_key"] = df[merge_cols].astype(str).agg("|".join, axis=1)
    jdf["_merge_key"] = jdf[merge_cols].astype(str).agg("|".join, axis=1)

    # Deduplicate JSON on the merge key (keep first occurrence)
    available_json_cols = [c for c in _JSON_ENRICH_COLS if c in jdf.columns]
    json_enrich = (
        jdf[["_merge_key"] + available_json_cols]
        .drop_duplicates(subset="_merge_key", keep="first")
    )

    # Suffix JSON columns so we can prefer them over CSV for matched rows
    df = df.merge(json_enrich, on="_merge_key", how="left", suffixes=("", "_json"))
    df.drop(columns=["_merge_key"], inplace=True)

    # For matched rows, override CSV predictions with JSON values
    for col in available_json_cols:
        json_col = f"{col}_json"
        if json_col in df.columns:
            mask = df[json_col].notna()
            if col in df.columns:
                df.loc[mask, col] = df.loc[mask, json_col]
            else:
                df[col] = df[json_col]
            df.drop(columns=[json_col], inplace=True)

    # Ensure enrichment-only columns exist even for unmatched rows
    for col in [
        "predicted_price_lower",
        "predicted_price_upper",
        "median_similar",
        "median_months_back",
        "median_sample_size",
        "median_old",
    ]:
        if col not in df.columns:
            df[col] = float("nan")

    # ── 4. Normalise towns to UPPERCASE ──────────────────────────────────────
    df["town"] = df["town"].astype(str).str.strip().str.upper()

    # ── 5. Numeric coercions ─────────────────────────────────────────────────
    df["floor_area_sqm"]  = pd.to_numeric(df["floor_area_sqm"], errors="coerce").fillna(0).round().astype(int)
    df["asking_price"]    = pd.to_numeric(df["asking_price"], errors="coerce").fillna(0)
    df["predicted_price"] = pd.to_numeric(df.get("predicted_price", 0), errors="coerce").fillna(0)
    df["valuation_pct"]   = pd.to_numeric(df.get("valuation_pct", 0), errors="coerce").fillna(0)

    for col in ("predicted_price_lower", "predicted_price_upper", "median_similar", "median_6m_similar"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # remaining_lease is used downstream in numeric comparisons
    df["remaining_lease_display"] = df["remaining_lease"]
    df["remaining_lease"] = (
        df["remaining_lease"]
        .astype(str)
        .str.extract(r"(\d+\.?\d*)")[0]
    )
    df["remaining_lease"] = pd.to_numeric(df["remaining_lease"], errors="coerce")
    df["remaining_lease_years"] = df["remaining_lease"]

    # ── 6. Derived / helper columns ───────────────────────────────────────────
    df["listing_id"] = df.index.astype(str)

    if "storey_midpoint" in df.columns:
        df["storey_range"] = (
            df["storey_midpoint"]
            .fillna(0)
            .astype(float)
            .round()
            .astype(int)
            .astype(str)
        )
    else:
        df["storey_range"] = ""

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    return df, None