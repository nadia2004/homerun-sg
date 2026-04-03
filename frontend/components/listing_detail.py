"""
frontend/components/listing_detail.py

Fully data-driven listing detail dialog.
Data comes from listings_predictions.json merged with final.csv amenity columns.
"""

import math
import streamlit as st

from backend.utils.formatters import fmt_sgd
from frontend.state.session import record_swipe


# ── Map (uses real lat/lon) ──────────────────────────────────────────────────
def _map_iframe(lat, lon, height: int = 220) -> str:
    if lat is None or lon is None:
        return ""
    src = (
        f"https://www.openstreetmap.org/export/embed.html"
        f"?bbox={lon-0.01},{lat-0.006},{lon+0.01},{lat+0.006}"
        f"&layer=mapnik&marker={lat},{lon}"
    )
    return f'<iframe src="{src}" width="100%" height="{height}" style="border:none;border-radius:12px;"></iframe>'


# ── Helpers ──────────────────────────────────────────────────────────────────
def _distance_score(dist):
    if dist is None or (isinstance(dist, float) and math.isnan(dist)):
        return 40
    if dist <= 300:  return 90
    if dist <= 600:  return 75
    if dist <= 1000: return 60
    return 40


def _proximity_label(dist):
    if dist is None or (isinstance(dist, float) and math.isnan(dist)) or dist > 1500:
        return "Very far"
    if dist > 1000: return "Far"
    if dist > 600:  return "Moderate"
    if dist > 300:  return "Close"
    return "Very close"


def _val_style(diff):
    if diff <= -5:  return "Great Deal",         "#059E87"
    if diff <= 3:   return "Fair Value",          "#2563eb"
    if diff <= 10:  return "Slightly High",       "#d97706"
    return           "Overpriced",                "#dc2626"


def _fmt_nullable_sgd(val):
    """Return formatted SGD or em-dash if null/zero."""
    try:
        v = float(val)
        if v > 0:
            return fmt_sgd(v)
    except (TypeError, ValueError):
        pass
    return "—"


# ── Main dialog ──────────────────────────────────────────────────────────────
@st.dialog("Listing Details", width="large")
def show_listing_detail(listing_id: str, show_actions: bool = True):

    # Find listing across sessions
    row = None
    session_data = None
    for s in st.session_state.get("search_sessions", []):
        df = s["bundle"]["listings_df"]
        match = df[df["listing_id"] == listing_id]
        if not match.empty:
            row = match.iloc[0]
            session_data = s
            break

    if row is None:
        st.error("Listing not found.")
        return

    # ── Core fields ──────────────────────────────────────────────────────────
    asking    = int(row["asking_price"])
    predicted = int(row["predicted_price"])
    diff      = float(row.get("valuation_pct", 0))

    ci_low  = row.get("predicted_price_lower")
    ci_high = row.get("predicted_price_upper")
    try:
        ci_low  = int(ci_low)  if ci_low  is not None and not math.isnan(float(ci_low))  else None
        ci_high = int(ci_high) if ci_high is not None and not math.isnan(float(ci_high)) else None
    except (TypeError, ValueError):
        ci_low = ci_high = None

    town      = str(row.get("town", ""))
    flat_type = str(row.get("flat_type", ""))
    area      = round(float(row.get("floor_area_sqm", 0)))
    storey    = row.get("storey_midpoint", "")
    address   = str(row.get("address", ""))
    lat       = row.get("lat")
    lon       = row.get("lon")
    remaining = row.get("remaining_lease")

    # ── Median fields ────────────────────────────────────────────────────────
    median_similar     = row.get("median_similar")
    median_months_back = row.get("median_months_back")
    median_sample_size = row.get("median_sample_size")
    median_old         = row.get("median_old")

    try:
        median_similar = float(median_similar) if median_similar is not None else None
        if median_similar is not None and math.isnan(median_similar):
            median_similar = None
    except (TypeError, ValueError):
        median_similar = None

    # ── Amenity scores ───────────────────────────────────────────────────────
    mrt_score    = _distance_score(row.get("train_1_dist_m"))
    bus_score    = _distance_score(row.get("bus_1_dist_m"))
    school_score = _distance_score(row.get("school_1_dist_m"))
    hawker_score = _distance_score(row.get("hawker_1_dist_m"))
    retail_score = _distance_score(row.get("mall_1_dist_m"))
    health_score = _distance_score(row.get("polyclinic_1_dist_m"))
    amenity_avg  = (mrt_score + bus_score + school_score + hawker_score + retail_score + health_score) / 6

    value_score   = max(0, min(100, 100 - abs(diff)))
    overall_score = round(value_score * 0.6 + amenity_avg * 0.4, 1)

    val_label, val_color = _val_style(diff)
    sign = "+" if diff >= 0 else ""

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:flex-start;
                margin-bottom:0.5rem;">
        <div>
            <h2 style="margin:0 0 2px;">{town}</h2>
            <p style="margin:0;color:#64748b;font-size:0.9rem;">{address}</p>
            <p style="margin:4px 0 0;color:#64748b;font-size:0.85rem;">
                {flat_type} · {area} sqm · Storey {storey}
                {'· ~' + str(int(float(remaining))) + ' yrs lease' if remaining else ''}
            </p>
        </div>
        <div style="text-align:right;">
            <div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{fmt_sgd(asking)}</div>
            <div style="font-size:0.82rem;color:#94a3b8;margin-top:2px;">
                asking price
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── Price Analysis ───────────────────────────────────────────────────────
    st.markdown("### 💰 Price Analysis")

    # CI range block
    if ci_low is not None and ci_high is not None:
        ci_html = (
            f"<div style='background:#f0fdf4;border:1px solid #86efac;border-radius:10px;"
            f"padding:10px 14px;margin:8px 0;'>"
            f"<div style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.08em;color:#16a34a;margin-bottom:4px;'>95% CI Range</div>"
            f"<div style='font-size:1.05rem;font-weight:800;color:#0f172a;'>"
            f"{fmt_sgd(ci_low)} – {fmt_sgd(ci_high)}</div>"
            f"<div style='font-size:0.72rem;color:#64748b;margin-top:3px;'>"
            f"95% chance the actual sale price falls in this range</div>"
            f"</div>"
        )
    else:
        ci_html = ""

    # Valuation bias note when diff is between +2% and +5%
    bias_note = ""
    if 2 <= diff <= 5:
        bias_note = (
            "<div style='font-size:0.75rem;color:#92400e;background:#fffbeb;"
            "border:1px solid #fcd34d;border-radius:8px;padding:6px 10px;margin-top:6px;'>"
            "⚠️ A +2% to +5% margin is within the model's known upward bias — "
            "this may still represent fair value."
            "</div>"
        )

    st.markdown(f"""
    {ci_html}
    <div style="margin:4px 0;">
        <table style="width:100%;border-collapse:collapse;font-size:0.88rem;">
            <tr>
                <td style="padding:5px 0;color:#64748b;">Asking price</td>
                <td style="padding:5px 0;text-align:right;font-weight:700;">{fmt_sgd(asking)}</td>
            </tr>
            <tr>
                <td style="padding:5px 0;color:#64748b;">Model estimate</td>
                <td style="padding:5px 0;text-align:right;font-weight:700;">{fmt_sgd(predicted)}</td>
            </tr>
            <tr>
                <td style="padding:5px 0;color:#64748b;">Asking vs estimate</td>
                <td style="padding:5px 0;text-align:right;font-weight:800;color:{val_color};">
                    {sign}{diff:.1f}% &nbsp;
                    <span style="background:{val_color};color:#fff;border-radius:6px;
                                 padding:2px 7px;font-size:0.75rem;">{val_label}</span>
                </td>
            </tr>
        </table>
    </div>
    {bias_note}
    """, unsafe_allow_html=True)

    # ── Market Context ───────────────────────────────────────────────────────
    st.markdown("### 📊 Market Context")

    if median_similar is not None and median_similar > 0:
        months_label = ""
        if median_months_back is not None:
            try:
                months_label = f"last {int(float(median_months_back))} months"
            except (TypeError, ValueError):
                pass

        caption = f"Recent median · {flat_type} in {town}"
        if months_label:
            caption += f" · {months_label}"

        st.metric(label=caption, value=fmt_sgd(median_similar))

        if median_old:
            st.warning("Median based on data >12 months old — may not reflect current prices.", icon="⚠️")

        try:
            if median_sample_size is not None and int(median_sample_size) < 20:
                st.caption(f"Based on only {int(median_sample_size)} recent transactions — treat as indicative.")
        except (TypeError, ValueError):
            pass
    else:
        st.caption("No recent comparables — insufficient transactions for this flat type in this town.")

    # ── Match Score ──────────────────────────────────────────────────────────
    st.markdown("### 🎯 Match Score")
    st.progress(int(overall_score), text=f"Overall {overall_score:.0f}%")
    st.caption(f"Value score: {value_score:.0f}  ·  Amenity score: {amenity_avg:.0f}")

    # ── Amenity Breakdown ────────────────────────────────────────────────────
    st.markdown("### 📍 Amenities Nearby")

    amenity_rows = [
        ("🚇 MRT",        row.get("train_1_dist_m"),     mrt_score),
        ("🚌 Bus stop",   row.get("bus_1_dist_m"),        bus_score),
        ("🏫 School",     row.get("school_1_dist_m"),     school_score),
        ("🍜 Hawker",     row.get("hawker_1_dist_m"),     hawker_score),
        ("🛍️ Mall",       row.get("mall_1_dist_m"),       retail_score),
        ("🏥 Polyclinic", row.get("polyclinic_1_dist_m"), health_score),
    ]

    col_a, col_b = st.columns(2)
    for i, (label, dist, score) in enumerate(amenity_rows):
        try:
            dist_val = f"{float(dist):.0f} m" if dist is not None and not math.isnan(float(dist)) else "N/A"
        except (TypeError, ValueError):
            dist_val = "N/A"
        prox = _proximity_label(dist)
        col = col_a if i % 2 == 0 else col_b
        col.metric(label=label, value=dist_val, delta=prox,
                   delta_color="normal" if score >= 75 else "inverse" if score < 50 else "off")

    # ── Map ──────────────────────────────────────────────────────────────────
    st.markdown("### 🗺️ Location")
    map_html = _map_iframe(lat, lon)
    if map_html:
        st.markdown(map_html, unsafe_allow_html=True)
    else:
        st.caption("Location unavailable.")

    # ── Data note ────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:0.70rem;color:#cbd5e1;margin-top:8px;'>"
        "Predictions updated quarterly · Remaining lease is indicative (±1 yr)</div>",
        unsafe_allow_html=True,
    )

    # ── Actions ──────────────────────────────────────────────────────────────
    if show_actions:
        st.divider()
        is_saved  = session_data and listing_id in session_data.get("liked_ids", [])
        is_passed = session_data and listing_id in session_data.get("passed_ids", [])

        col1, col2 = st.columns(2)
        with col1:
            if not is_passed:
                if st.button("✕ Pass", use_container_width=True):
                    record_swipe(session_data["session_id"], listing_id, "left")
                    st.rerun()
            else:
                st.info("Passed")
        with col2:
            if not is_saved:
                if st.button("♥ Save", use_container_width=True, type="primary"):
                    record_swipe(session_data["session_id"], listing_id, "right")
                    st.rerun()
            else:
                st.success("Saved ♥")
