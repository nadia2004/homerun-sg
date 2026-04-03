# backend/services/recommendation_service.py
import pandas as pd
from data.load_data import load_all_data
from backend.schemas.inputs import UserInputs
from backend.utils.constants import AMENITY_KEYS


def recommend_towns_real(
    inputs: UserInputs,
    df: pd.DataFrame,
    amenity_ranking: list = None,
    amenity_weights: dict = None,
    top_n: int = 5,
) -> pd.DataFrame:
    """
    Aggregate pre-scored listings by town and return the top_n towns.

    Expects `df` to already have `final_score` and `predicted_price` columns
    (i.e. the output of compute_listing_scores from scoring.py).
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["town", "estimated_price", "match_score", "why_it_matches"])

    required = {"town", "final_score", "predicted_price"}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=["town", "estimated_price", "match_score", "why_it_matches"])

    results = []
    for town, grp in df.groupby("town"):
        if grp.empty:
            continue
        results.append({
            "town":             town,
            "estimated_price":  grp["predicted_price"].median(),
            "match_score":      grp["final_score"].median() * 100,   # 0..1 → 0..100
            "count_listings":   len(grp),
        })

    if not results:
        return pd.DataFrame(columns=["town", "estimated_price", "match_score", "why_it_matches"])

    town_df = (
        pd.DataFrame(results)
        .sort_values("match_score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    def _why(row):
        reasons = []
        budget = getattr(inputs, "budget", None)
        if budget and row["estimated_price"] <= budget:
            reasons.append("affordable within budget")
        if row["match_score"] >= 70:
            reasons.append("good amenities nearby")
        if row["count_listings"] >= 5:
            reasons.append("lots of available flats")
        return "Strong overall fit: " + " · ".join(reasons) if reasons else "Good fit overall"

    town_df["why_it_matches"] = town_df.apply(_why, axis=1)

    return town_df[["town", "estimated_price", "match_score", "why_it_matches"]]


def get_top_towns(inputs: UserInputs, top_n: int = 5):
    from backend.utils.scoring import compute_listing_scores
    listings_df, _ = load_all_data()
    scored = compute_listing_scores(
        listings_df,
        budget=getattr(inputs, "budget", None),
        amenity_weights=getattr(inputs, "amenity_weights", None) or {},
    )
    return recommend_towns_real(inputs, df=scored, top_n=top_n)
