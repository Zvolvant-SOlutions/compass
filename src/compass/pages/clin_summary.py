"""CLIN Summary — tabular RAG view with drill-through to sprint detail.

Each row is a CLIN with its per-KPI RAG status; expanding shows the contributing
sprints. CORs can record an acceptance decision from this page.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from .. import audit, auth, db
from ..branding import rag_pill
from ..kpi import compute_sprint_kpis
from ..rag import DEFAULT_THRESHOLDS, rag_for


def _summarize_clin(clin_id: int) -> dict:
    sprints = db.fetch_all("SELECT * FROM sprint WHERE clin_id = ?", (clin_id,))
    if not sprints:
        return {}

    # Average each KPI across the CLIN's sprints
    totals = {
        "predictability": 0,
        "story_completion": 0,
        "defect_leakage": 0,
        "uat_first_pass": 0,
        "cycle_time": 0,
        "availability": 0,
        "burn_variance": 0,
    }
    for s in sprints:
        k = compute_sprint_kpis(s)
        totals["predictability"] += k.sprint_predictability_pct
        totals["story_completion"] += k.story_completion_pct
        totals["defect_leakage"] += k.defect_leakage_pct
        totals["uat_first_pass"] += k.uat_first_pass_pct
        totals["cycle_time"] += k.cycle_time_days
        totals["availability"] += k.availability_pct
        totals["burn_variance"] += k.burn_variance_pct
    n = len(sprints)
    return {k: round(v / n, 4) for k, v in totals.items()}


def render() -> None:
    user = auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>CLIN Summary</h2>"
        '<p class="lead">Per-CLIN RAG across the seven Compass KPIs, with sprint drill-through and acceptance-decision capture.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    clins = db.fetch_all("SELECT * FROM clin ORDER BY code")
    rows = []
    for c in clins:
        summary = _summarize_clin(c["id"])
        if not summary:
            continue
        row = {"CLIN": c["code"], "Name": c["name"]}
        for kpi in DEFAULT_THRESHOLDS:
            val = summary[kpi]
            rag = rag_for(val, DEFAULT_THRESHOLDS[kpi])
            row[kpi] = f"{val:.2%}" if "pct" in kpi or kpi != "cycle_time" else f"{val:.1f}d"
            row[kpi + "_rag"] = rag
        row["Decision"] = c.get("acceptance_decision", "pending")
        rows.append(row)

    if not rows:
        st.info("No sprint data available yet. Run `make seed` then refresh.")
        return

    # Render the table — show value next to a RAG pill in a clean row
    for r in rows:
        with st.container():
            cols = st.columns([2, 3, 1, 1, 1, 1, 1, 1, 1, 2])
            cols[0].markdown(f"**{r['CLIN']}**")
            cols[1].markdown(r["Name"])
            for i, kpi in enumerate(
                [
                    "predictability",
                    "story_completion",
                    "defect_leakage",
                    "uat_first_pass",
                    "cycle_time",
                    "availability",
                    "burn_variance",
                ]
            ):
                cols[2 + i].markdown(
                    rag_pill(r[kpi + "_rag"])
                    + f"<br><span style='font-size:0.78rem;color:#48515E'>{r[kpi]}</span>",
                    unsafe_allow_html=True,
                )
            cols[9].markdown(f"_{r['Decision']}_")

    # Acceptance decision form (COR only)
    if auth.can_decide(user):
        st.markdown(
            '<div class="cps-section"><h2>Record an acceptance decision</h2></div>', unsafe_allow_html=True
        )
        with st.form("acceptance_form"):
            clin_choice = st.selectbox(
                "CLIN",
                options=[c["id"] for c in clins],
                format_func=lambda cid: next(
                    (f"{c['code']} — {c['name']}" for c in clins if c["id"] == cid), str(cid)
                ),
            )
            decision = st.selectbox("Decision", ["accept", "conditional", "reject", "pending"])
            invoice = st.selectbox("Invoice position", ["release", "partial", "hold"])
            required_action = st.text_area(
                "Required COR action / rationale",
                height=80,
                placeholder="e.g., Conditional acceptance — release 70%, hold 30% pending CLIN 003 cycle-time remediation.",
            )
            submit = st.form_submit_button("Record decision", type="primary")
        if submit:
            old = db.fetch_one(
                "SELECT acceptance_decision, invoice_position, required_cor_action FROM clin WHERE id = ?",
                (clin_choice,),
            )
            db.execute(
                "UPDATE clin SET acceptance_decision = ?, invoice_position = ?, required_cor_action = ?, updated_at = ? WHERE id = ?",
                (decision, invoice, required_action, datetime.utcnow().isoformat(), clin_choice),
            )
            audit.log(
                user,
                entity="clin",
                entity_id=clin_choice,
                action="decision",
                field="acceptance_decision",
                old_value=old.get("acceptance_decision") if old else None,
                new_value=decision,
                rationale=required_action,
            )
            st.success("Decision recorded.")
            st.rerun()
