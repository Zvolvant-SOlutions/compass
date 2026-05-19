"""Hybrid Acceptance Summary — counts and filters by CLIN / Workstream / Project System."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from .. import auth, db
from ..acceptance import derive_state, payment_release_pct


def render() -> None:
    auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>Hybrid Acceptance Summary</h2>"
        '<p class="lead">Per-stage counts across all in-flight features, plus payment-release roll-up.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    features = db.fetch_all(
        """SELECT f.*, c.code AS clin_code, w.name AS workstream_name
           FROM feature_value f
           LEFT JOIN clin c ON c.id = f.clin_id
           LEFT JOIN workstream w ON w.id = f.workstream_id"""
    )
    if not features:
        st.info("No features yet.")
        return

    # Filters
    clins = sorted({(f["clin_code"] or "—") for f in features})
    workstreams = sorted({(f["workstream_name"] or "—") for f in features})
    c1, c2 = st.columns(2)
    sel_clin = c1.multiselect("CLIN", options=clins, default=clins)
    sel_ws = c2.multiselect("Workstream", options=workstreams, default=workstreams)
    filtered = [
        f
        for f in features
        if (f.get("clin_code") or "—") in sel_clin and (f.get("workstream_name") or "—") in sel_ws
    ]

    counts = {"technically_accepted": 0, "value_pending": 0, "fully_accepted": 0, "rework_required": 0}
    payments = {"released": 0, "held_pending": 0}
    total_held = 0.0
    total_released = 0.0
    for f in filtered:
        state = derive_state(f)
        counts[state.stage] = counts.get(state.stage, 0) + 1
        payments[state.payment_status] = payments.get(state.payment_status, 0) + 1
        release = payment_release_pct(state)
        # Use sprint planned burn as a stand-in invoice slice for the summary;
        # production would model invoice slices per-feature.
        total_released += release
        total_held += 1.0 - release

    cols = st.columns(4)
    labels = {
        "technically_accepted": "Technically accepted",
        "value_pending": "Value pending",
        "fully_accepted": "Fully accepted",
        "rework_required": "Rework required",
    }
    for col, (key, label) in zip(cols, labels.items(), strict=False):
        col.markdown(
            f'<div class="tile"><div class="label">{label}</div>'
            f'<div class="value">{counts.get(key, 0)}</div></div>',
            unsafe_allow_html=True,
        )

    # Stage donut
    df = pd.DataFrame({"Stage": list(labels.values()), "Count": [counts[k] for k in labels]})
    fig = px.pie(
        df,
        names="Stage",
        values="Count",
        hole=0.55,
        color="Stage",
        color_discrete_map={
            "Fully accepted": "#1F8A4C",
            "Technically accepted": "#C9A227",
            "Value pending": "#D6932A",
            "Rework required": "#B0322B",
        },
    )
    fig.update_layout(height=320, margin={"t": 10, "b": 10, "l": 0, "r": 0})
    st.plotly_chart(fig, use_container_width=True)

    # Payment roll-up
    st.markdown(
        '<div class="cps-section"><h2>Payment posture (across selected features)</h2></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    cols[0].markdown(
        f'<div class="tile"><div class="label">Slice released</div>'
        f'<div class="value">{int(100 * total_released / max(1, len(filtered)))}%</div>'
        f'<div class="sub">average across features</div></div>',
        unsafe_allow_html=True,
    )
    cols[1].markdown(
        f'<div class="tile"><div class="label">Slice held</div>'
        f'<div class="value">{int(100 * total_held / max(1, len(filtered)))}%</div>'
        f'<div class="sub">held pending value validation or rework</div></div>',
        unsafe_allow_html=True,
    )
