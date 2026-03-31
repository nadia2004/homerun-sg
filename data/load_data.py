import pandas as pd
import streamlit as st

@st.cache_data
def load_all_data():
    listings = pd.read_excel("data/active_listings.xlsx")
    amenities = pd.read_csv("data/hdb_amenity_table_full.csv")

    # -------------------------------
    # CLEAN COLUMN NAMES
    # -------------------------------
    listings.columns = listings.columns.str.lower().str.strip()
    amenities.columns = amenities.columns.str.lower().str.strip()

    # -------------------------------
    # RENAME TO MATCH YOUR SYSTEM
    # -------------------------------
    listings = listings.rename(columns={
        "price/value": "asking_price",
        "floor_area (sqft)": "floor_area_sqft",
        "planning_area": "town",
        "property/id": "listing_id",
        "built year": "built_year"
    })

    # -------------------------------
    # CONVERT UNITS
    # -------------------------------
    listings["floor_area_sqm"] = listings["floor_area_sqft"] * 0.092903

    # -------------------------------
    # CREATE FLAT TYPE (VERY IMPORTANT)
    # -------------------------------
    def infer_flat_type(row):
        beds = row.get("bedrooms", 0)
        if beds <= 1:
            return "2 ROOM"
        elif beds == 2:
            return "3 ROOM"
        elif beds == 3:
            return "4 ROOM"
        elif beds == 4:
            return "5 ROOM"
        else:
            return "EXECUTIVE"

    listings["flat_type"] = listings.apply(infer_flat_type, axis=1)

    # -------------------------------
    # ADDRESS CLEANING FOR MERGE
    # -------------------------------
    listings["full_address"] = listings["full_address"].str.lower().str.strip()
    amenities["full_address"] = amenities["full_address"].str.lower().str.strip()

    # -------------------------------
    # MERGE
    # -------------------------------
    df = listings.merge(
        amenities,
        on="full_address",
        how="left"
    )

    df["storey_range"] = df.get("storey_range", "N/A")
    df["recent_median_transacted"] = df["asking_price"]

    return df, amenities