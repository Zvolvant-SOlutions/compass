"""Risks & Issues — open / monitor / closed with priority, mitigation, owner, due date."""

from __future__ import annotations

import streamlit as st

from .. import audit, auth, db
from ..branding import rag_pill

PRIO_RAG = {"high": "red", "medium": "amber", "low": "green"}


def render() -> None:
    user = auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>Risks & Issues</h2>"
        '<p class="lead">Open and monitored risks with priority, owner, mitigation, and due date.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    clins = db.fetch_all("SELECT id, code FROM clin ORDER BY code")
    clin_label = {c["id"]: c["code"] for c in clins}
    workstreams = db.fetch_all("SELECT id, name FROM workstream ORDER BY name")
    ws_label = {w["id"]: w["name"] for w in workstreams}

    if auth.can_edit(user):
        with st.expander("Add a risk / issue"):
            with st.form("add_risk"):
                priority = st.selectbox("Priority", ["high", "medium", "low"])
                text = st.text_area("Description", height=80)
                clin_id = st.selectbox(
                    "Impacted CLIN",
                    options=[None] + [c["id"] for c in clins],
                    format_func=lambda x: clin_label.get(x, "—"),
                )
                ws_id = st.selectbox(
                    "Impacted workstream",
                    options=[None] + [w["id"] for w in workstreams],
                    format_func=lambda x: ws_label.get(x, "—"),
                )
                mitigation = st.text_area("Mitigation", height=70)
                owner = st.selectbox("Owner role", ["COR", "PM", "PO"])
                due = st.date_input("Due date")
                submit = st.form_submit_button("Save", type="primary")
            if submit and text.strip():
                rid = db.execute(
                    """INSERT INTO risk_issue (priority, risk_issue_text, impacted_clin_id, impacted_workstream_id,
                                                status, mitigation, owner_role, due_date)
                       VALUES (?, ?, ?, ?, 'open', ?, ?, ?)""",
                    (priority, text, clin_id, ws_id, mitigation, owner, str(due) if due else None),
                )
                audit.log(
                    user,
                    entity="risk_issue",
                    entity_id=rid,
                    action="create",
                    new_value=text,
                    rationale=f"priority={priority}; owner={owner}",
                )
                st.success("Risk added.")
                st.rerun()

    rows = db.fetch_all(
        "SELECT * FROM risk_issue ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, status"
    )
    for r in rows:
        cols = st.columns([1, 4, 1, 1, 1])
        cols[0].markdown(rag_pill(PRIO_RAG.get(r["priority"], "amber")), unsafe_allow_html=True)
        cols[1].markdown(
            f"**{r['risk_issue_text']}**<br>"
            f"<span style='font-size:0.84rem; color:#48515E'>"
            f"Owner: {r.get('owner_role') or '—'}  ·  "
            f"Mitigation: {r.get('mitigation') or '—'}</span>",
            unsafe_allow_html=True,
        )
        cols[2].markdown(clin_label.get(r.get("impacted_clin_id"), "—"))
        cols[3].markdown(ws_label.get(r.get("impacted_workstream_id"), "—"))
        cols[4].markdown(
            f"_{r['status']}_<br><span style='font-size:0.78rem; color:#48515E'>{r.get('due_date') or '—'}</span>",
            unsafe_allow_html=True,
        )
