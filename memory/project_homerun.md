---
name: HomeRun SG project context
description: Key architecture, data sources, and bugs fixed in the HDB prediction frontend
type: project
---

Streamlit HDB flat finder. Prediction model output lives in `backend_predictor_listings/price_predictor/json_outputs/listings_predictions.json` (895 active listings). Amenity distance data lives in `data/final.csv` (1283 rows, different set). Merged on `postal` (deduped).

**Why:** The JSON is the authoritative model output per README_v2.docx; the CSV has precomputed amenity distances needed for scoring.

**How to apply:** `data/load_data.py` now merges both. JSON fields take priority for predictions; CSV provides `train_1_dist_m`, `bus_1_dist_m`, etc.

---

## Bugs fixed (April 2026)

1. **Town case mismatch** — `TOWNS` in `constants.py` had title case ("Tampines") but data is uppercase ("TAMPINES"). Predictor service used exact-case match → 0 results when town selected. Fixed by updating TOWNS to uppercase and normalising `inputs.town` with `.upper().strip()` in `predictor_service.py` and `listings_service.py`.

2. **Wrong scoring pipeline** — `predictor_service.py` used `rec_results["filtered"]` (raw unscored df from `run_recommender`) instead of running `compute_listing_scores`. Cards showed 0% match scores and blank valuation labels. Fixed by removing `run_recommender` and calling `compute_listing_scores` directly.

3. **Missing CI and median fields** — `final.csv` lacked `predicted_price_lower`, `predicted_price_upper`, `median_similar`. Old code hardcoded CI as ±4%. Fixed by loading JSON as primary source.

4. **Amenity score column name mismatch** — `scoring.py` produced `health_score`/`school_score`/`mall_score` but `best_matches.py` looked up `healthcare_score`/`schools_score`/`retail_score`. Fixed by adding aliases in `scoring.py`.

5. **Incomplete TOWNS list** — Was 18 towns (title case); expanded to all 26 towns from the model (uppercase).
