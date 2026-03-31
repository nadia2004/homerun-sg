import numpy as np
import pandas as pd

from backend.utils.constants import TOWNS
from backend.utils.scoring import classify_listing
from backend.schemas.inputs import UserInputs

from data.load_data import load_all_data

def get_active_listings(inputs: UserInputs) -> pd.DataFrame:
    df, _ = load_all_data()

    # --- FILTERING ---
    if inputs.town:
        df = df[df["town"] == inputs.town]

    df = df[df["flat_type"] == inputs.flat_type]

    # Optional: area filter
    df = df[
        (df["floor_area_sqm"] >= inputs.floor_area_sqm - 10) &
        (df["floor_area_sqm"] <= inputs.floor_area_sqm + 10)
    ]

    # --- CLEAN COLUMNS ---
    # align with your old schema
    df = df.rename(columns={
        "price/value": "asking_price"   # adjust if needed
    })

    # --- ADD REQUIRED FIELDS (so rest of pipeline doesn't break) ---
    df["listing_id"] = df.index.astype(str)
    df["listing_url"] = "#"
    df["storey_range"] = df.get("storey_range", "N/A")

    # fallback predicted price (you already compute real one elsewhere)
    df["predicted_price"] = df["asking_price"]

    df["recent_median_transacted"] = df["asking_price"]

    df["asking_vs_predicted_pct"] = 0

    df["valuation_label"] = df.apply(classify_listing, axis=1)

    return df.copy()