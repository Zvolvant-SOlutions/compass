"""Readiness Dashboard — workstream-agnostic readiness signals.

Highlights UAT First-Pass, Defect Leakage, Cycle Time, and Availability per
workstream / project-system so program leads can spot weak spots before
acceptance gates trigger.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from .. import auth, db
from ..branding import rag_pill
from ..kpi import compute_sprint_kpis
from ..rag import DEFAULT_THRESHOLDS, rag_for

READINESS_KPIS = ["uat_first_pass", "defect_leakage", "cycle_time", "availability"]


def render() -> None:
    auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>Readiness Dashboard</h2>"
        '<p class="lead">Quality signals across workstreams — the canary for whether the next acceptance review goes smoothly.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    rows = db.fetch_all(
        """SELECT s.*, w.name AS workstream_name, p.name AS project_system_name, c.code AS clin_code
           FROM sprint s
           LEFT JOIN workstream w ON w.id = s.workstream_id
           LEFT JOIN project_system p ON p.id = s.project_system_id
           LEFT JOIN clin c ON c.id = s.clin_id
           ORDER BY s.start_date DESC"""
    )
    if not rows:
        st.info("No sprint data yet.")
        return

    # Aggregate by workstream
    by_ws: dict[str, dict] = {}
    for r in rows:
        ws = r.get("workstream_name") or "—"
        if ws not in by_ws:
            by_ws[ws] = {k: [] for k in READINESS_KPIS}
        k = compute_sprint_kpis(r)
        by_ws[ws]["uat_first_pass"].append(k.uat_first_pass_pct)
        by_ws[ws]["defect_leakage"].append(k.defect_leakage_pct)
        by_ws[ws]["cycle_time"].append(k.cycle_time_days)
        by_ws[ws]["availability"].append(k.availability_pct)

    table_rows: list[dict] = []
    for ws, vals in by_ws.items():
        row: dict = {"Workstream": ws}
        for kpi in READINESS_KPIS:
            v = sum(vals[kpi]) / max(1, len(vals[kpi]))
            row[kpi] = round(v, 4)
            row[kpi + "_rag"] = rag_for(v, DEFAULT_THRESHOLDS[kpi])
        table_rows.append(row)

    for r in table_rows:
        cols = st.columns([3, 1, 1, 1, 1])
        cols[0].markdown(f"**{r['Workstream']}**")
        for i, kpi in enumerate(READINESS_KPIS):
            val = r[kpi]
            display = f"{val:.1f}d" if kpi == "cycle_time" else f"{val:.2%}"
            cols[1 + i].markdown(
                rag_pill(r[kpi + "_rag"])
                + f"<br><span style='font-size:0.78rem; color:#48515E'>{display}</span>",
                unsafe_allow_html=True,
            )

    # Sprint-level scatter — defect leakage vs predictability
    st.markdown(
        '<div class="cps-section"><h2>Sprint scatter — predictability vs defect leakage</h2></div>',
        unsafe_allow_html=True,
    )
    scatter_data = []
    for r in rows:
        k = compute_sprint_kpis(r)
        scatter_data.append(
            {
                "Sprint": f"S{r['sprint_number']}",
                "CLIN": r.get("clin_code") or "",
                "Predictability": k.sprint_predictability_pct,
                "Defect leakage": k.defect_leakage_pct,
            }
        )
    df = pd.DataFrame(scatter_data)
    fig = px.scatter(
        df,
        x="Predictability",
        y="Defect leakage",
        color="CLIN",
        text="Sprint",
        color_discrete_sequence=["#0B2A4A", "#C9A227", "#1F8A4C", "#B0322B"],
        range_x=[0, 1.05],
        range_y=[0, 0.25],
    )
    fig.update_traces(textposition="top center", marker={"size": 12})
    fig.update_layout(height=420, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(gridcolor="#E6EAF0")
    fig.update_yaxes(gridcolor="#E6EAF0")
    st.plotly_chart(fig, use_container_width=True)
