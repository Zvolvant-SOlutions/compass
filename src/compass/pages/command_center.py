"""Executive Command Center — top-level CLIN dashboard for COR / executives.

CLIN cards with Acceptance Decision, Weighted Score, KPI strip, Burn vs Plan,
Required COR Action, invoice position, risks summary, and trend chart.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from .. import auth, db
from ..branding import rag_pill, tile_html
from ..kpi import (
    compute_sprint_kpis,
    customer_value_score,
    delivery_performance_score,
    overall_weighted_score,
)
from ..rag import overall_rag


def _clin_rollup(clin_id: int) -> dict:
    sprints = db.fetch_all("SELECT * FROM sprint WHERE clin_id = ? ORDER BY start_date DESC", (clin_id,))
    cv_inputs = (
        db.fetch_one(
            "SELECT * FROM customer_value_input WHERE clin_id = ? ORDER BY id DESC LIMIT 1", (clin_id,)
        )
        or {}
    )
    if not sprints:
        return {"score": 0, "delivery": 0, "customer_value": 0, "burn_variance": 0, "rag": "amber"}

    # Aggregate sprint KPIs across the CLIN's sprints (simple average)
    deliveries: list[float] = []
    burn_variances: list[float] = []
    for s in sprints:
        kpis = compute_sprint_kpis(s)
        deliveries.append(delivery_performance_score(kpis))
        burn_variances.append(kpis.burn_variance_pct)

    delivery = sum(deliveries) / len(deliveries)
    cv = customer_value_score(cv_inputs)
    score = overall_weighted_score(delivery, cv)
    burn_var = sum(burn_variances) / len(burn_variances) if burn_variances else 0.0
    return {
        "score": score,
        "delivery": delivery,
        "customer_value": cv,
        "burn_variance": burn_var,
        "rag": overall_rag(score),
    }


def _trend_chart(clin_id: int) -> None:
    sprints = db.fetch_all(
        "SELECT sprint_number, start_date, committed_points, completed_points, planned_burn_usd, actual_burn_usd "
        "FROM sprint WHERE clin_id = ? ORDER BY start_date",
        (clin_id,),
    )
    if not sprints:
        return
    df = pd.DataFrame(sprints)
    df["predictability"] = df["completed_points"] / df["committed_points"].replace(0, 1)
    fig = px.line(
        df,
        x="sprint_number",
        y="predictability",
        markers=True,
        title=None,
        range_y=[0, 1.05],
    )
    fig.update_traces(line_color="#0B2A4A", marker_color="#C9A227")
    fig.update_layout(
        height=160,
        margin={"t": 4, "b": 4, "l": 0, "r": 0},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={"size": 11},
    )
    fig.update_xaxes(title=None, showgrid=False)
    fig.update_yaxes(title="Predictability", showgrid=True, gridcolor="#E6EAF0")
    st.plotly_chart(fig, use_container_width=True)


def render() -> None:
    user = auth.require_role("READONLY")  # noqa: F841

    st.markdown(
        '<div class="cps-section">'
        "<h2>Executive Command Center</h2>"
        '<p class="lead">Per-CLIN acceptance posture, weighted score, and the action the COR needs to take next.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    clins = db.fetch_all("SELECT * FROM clin ORDER BY code")
    open_risks = db.fetch_all("SELECT * FROM risk_issue WHERE status = 'open'")
    open_risks_by_clin: dict[int, int] = {}
    for r in open_risks:
        cid = r.get("impacted_clin_id") or 0
        open_risks_by_clin[cid] = open_risks_by_clin.get(cid, 0) + 1

    # Top metric strip
    rollups = {c["id"]: _clin_rollup(c["id"]) for c in clins}
    deficient = sum(1 for r in rollups.values() if r["rag"] == "red")
    avg_score = round(100 * sum(r["score"] for r in rollups.values()) / max(len(rollups), 1))
    cols = st.columns(4)
    cols[0].markdown(tile_html("CLINs in scope", str(len(clins))), unsafe_allow_html=True)
    cols[1].markdown(
        tile_html("Avg weighted score", f"{avg_score}", "across all CLINs"), unsafe_allow_html=True
    )
    cols[2].markdown(tile_html("CLINs Deficient", str(deficient), "red status"), unsafe_allow_html=True)
    cols[3].markdown(
        tile_html("Open risks", str(len(open_risks)), "across portfolio"), unsafe_allow_html=True
    )

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    for clin in clins:
        roll = rollups[clin["id"]]
        rag_cls = roll["rag"]
        cols = st.columns([4, 2, 2, 2])
        with cols[0]:
            st.markdown(
                f'<div class="clin-card rag-{rag_cls}">'
                f"<h3>{clin['code']} — {clin['name']}</h3>"
                f'<div class="scope">{clin.get("scope", "")}</div>'
                f'<div style="margin-top:0.4rem">{rag_pill(rag_cls)} '
                f'<span style="color:#48515E; font-size:0.84rem; margin-left:0.5rem">'
                f"COR action: <b>{clin.get('required_cor_action') or 'no action required'}</b></span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        cols[1].markdown(
            tile_html(
                "Weighted score",
                f"{round(100 * roll['score'])}",
                f"Delivery {round(100 * roll['delivery'])} / Value {round(100 * roll['customer_value'])}",
            ),
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            tile_html("Burn variance", f"{round(100 * roll['burn_variance'])}%", "avg across sprints"),
            unsafe_allow_html=True,
        )
        cols[3].markdown(
            tile_html("Open risks", str(open_risks_by_clin.get(clin["id"], 0))),
            unsafe_allow_html=True,
        )
        with st.expander(f"Sprint predictability trend — {clin['code']}"):
            _trend_chart(clin["id"])
