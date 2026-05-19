"""Audit log viewer — immutable trail of every mutation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import audit, auth


def render() -> None:
    auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>Audit log</h2>"
        '<p class="lead">Every decision, threshold change, and risk-issue mutation, with actor and rationale.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    rows = audit.recent(limit=500)
    if not rows:
        st.info("No audit events yet.")
        return

    df = pd.DataFrame(rows)
    df = df[
        [
            "ts",
            "actor_email",
            "actor_role",
            "entity",
            "entity_id",
            "action",
            "field",
            "old_value",
            "new_value",
            "rationale",
        ]
    ]
    st.dataframe(df, use_container_width=True, hide_index=True)
