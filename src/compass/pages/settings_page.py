"""Settings — configurable KPI thresholds, owned by COR."""

from __future__ import annotations

import streamlit as st

from .. import audit, auth, db


def render() -> None:
    user = auth.require_role("READONLY")

    st.markdown(
        '<div class="cps-section">'
        "<h2>Settings — KPI thresholds</h2>"
        '<p class="lead">Default green / yellow thresholds for each KPI. COR-only edits; changes are audit-logged.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    rows = db.fetch_all("SELECT * FROM settings ORDER BY kpi_name")
    for row in rows:
        with st.container():
            cols = st.columns([2, 1, 1, 1, 1, 1, 2])
            cols[0].markdown(
                f"**{row['kpi_name']}**<br><span style='font-size:0.82rem; color:#48515E'>{row.get('pws_target_text', '')}</span>",
                unsafe_allow_html=True,
            )
            new_green = cols[1].number_input(
                "Green",
                value=float(row["green_threshold"]),
                key=f"g_{row['id']}",
                disabled=not auth.can_decide(user),
                step=0.01,
                format="%.3f",
            )
            new_yellow = cols[2].number_input(
                "Yellow",
                value=float(row["yellow_threshold"]),
                key=f"y_{row['id']}",
                disabled=not auth.can_decide(user),
                step=0.01,
                format="%.3f",
            )
            cols[3].markdown(f"_{row['direction'].replace('_', ' ')}_")
            cols[4].markdown(f"_{row.get('unit') or ''}_")
            cols[5].markdown(f"_{row.get('applies_to') or ''}_")
            if (
                auth.can_decide(user)
                and cols[6].button("Save", key=f"save_{row['id']}")
                and (new_green != row["green_threshold"] or new_yellow != row["yellow_threshold"])
            ):
                db.execute(
                    "UPDATE settings SET green_threshold = ?, yellow_threshold = ? WHERE id = ?",
                    (new_green, new_yellow, row["id"]),
                )
                audit.log(
                    user,
                    entity="settings",
                    entity_id=row["id"],
                    action="update",
                    field=row["kpi_name"],
                    old_value=f"green={row['green_threshold']} yellow={row['yellow_threshold']}",
                    new_value=f"green={new_green} yellow={new_yellow}",
                    rationale="Threshold update",
                )
                st.success("Saved.")
                st.rerun()
