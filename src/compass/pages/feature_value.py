"""Feature Value Tracker — per-feature value metrics, evidence, acceptance stage, payment status.

This is where PO / PM enter post-release business metrics, COR triggers
Stage 1 / Stage 2 / Rework Required transitions, and everyone sees the
current payment-release picture.
"""

from __future__ import annotations

import streamlit as st

from .. import acceptance, audit, auth, db
from ..branding import rag_pill

STAGE_LABELS = {
    "technically_accepted": "Technically accepted",
    "value_pending": "Value pending",
    "fully_accepted": "Fully accepted",
    "rework_required": "Rework required",
}


def _stage_rag(stage: str) -> str:
    return {
        "fully_accepted": "green",
        "technically_accepted": "amber",
        "value_pending": "amber",
        "rework_required": "red",
    }.get(stage or "", "amber")


def _render_feature(feature: dict, user) -> None:
    state = acceptance.derive_state(feature)
    release_pct = acceptance.payment_release_pct(state)

    cols = st.columns([3, 1, 1, 1])
    cols[0].markdown(
        f"<div style='font-weight:700; color:#0B2A4A'>{feature['feature_code']} — {feature['feature_name']}</div>"
        f"<div style='color:#48515E; font-size:0.86rem'>{feature.get('outcome_statement', '')}</div>",
        unsafe_allow_html=True,
    )
    cols[1].markdown(
        f"**Stage**<br>{rag_pill(_stage_rag(state.stage))} {STAGE_LABELS.get(state.stage, state.stage)}",
        unsafe_allow_html=True,
    )
    cols[2].markdown(
        f"**Payment**<br>{state.payment_status}  ({int(release_pct * 100)}% release)", unsafe_allow_html=True
    )
    cols[3].markdown(f"**Holdback**<br>{int(state.holdback_pct * 100)}%", unsafe_allow_html=True)

    with st.expander("Details & decisions"):
        st.markdown(
            f"- Customer satisfaction: **{feature.get('customer_satisfaction', 0):.0%}**\n"
            f"- Adoption rate: **{feature.get('adoption_rate', 0):.0%}**\n"
            f"- Feature utilization: **{feature.get('feature_utilization', 0):.0%}**\n"
            f"- Rework rate: **{feature.get('rework_rate', 0):.0%}**\n"
            f"- Tangible evidence: {feature.get('tangible_evidence') or '(none yet)'}\n"
            f"- Backlog impact: **{state.backlog_impact}**"
        )

        if auth.can_decide(user):
            c1, c2, c3 = st.columns(3)
            if c1.button("Technically accept", key=f"t_{feature['id']}"):
                new_state = acceptance.technically_accept(state)
                _apply_state(feature, new_state, user, rationale="Technical acceptance — DoD met.")
                st.rerun()
            if c2.button("Confirm value", key=f"v_{feature['id']}"):
                new_state = acceptance.confirm_value(state)
                _apply_state(feature, new_state, user, rationale="Stage 2 value validation passed.")
                st.rerun()
            if c3.button("Require rework", key=f"r_{feature['id']}"):
                new_state = acceptance.require_rework(state, reason="Value validation gap.")
                _apply_state(feature, new_state, user, rationale="Stage 2 value gap — rework triggered.")
                st.rerun()
    st.markdown(
        "<div style='border-bottom:1px solid #E6EAF0; margin:0.4rem 0'></div>", unsafe_allow_html=True
    )


def _apply_state(feature: dict, state: acceptance.AcceptanceState, user, rationale: str) -> None:
    old_stage = feature.get("acceptance_stage")
    db.execute(
        """UPDATE feature_value
           SET acceptance_stage = ?, payment_status = ?, backlog_impact = ?,
               rework_required_yn = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (state.stage, state.payment_status, state.backlog_impact, state.rework_required_yn, feature["id"]),
    )
    audit.log(
        user,
        entity="feature_value",
        entity_id=feature["id"],
        action="decision",
        field="acceptance_stage",
        old_value=old_stage,
        new_value=state.stage,
        rationale=rationale,
    )


def render() -> None:
    user = auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>Feature Value Tracker</h2>"
        '<p class="lead">Each feature shows its outcome, post-release value metrics, evidence, acceptance stage, and payment posture.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    features = db.fetch_all(
        """SELECT f.*, c.code AS clin_code FROM feature_value f
           LEFT JOIN clin c ON c.id = f.clin_id ORDER BY f.feature_code"""
    )
    if not features:
        st.info("No features recorded yet.")
        return

    for f in features:
        _render_feature(f, user)
