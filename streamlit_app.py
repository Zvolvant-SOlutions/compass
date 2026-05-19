"""Compass — Executive oversight for agile federal delivery.

Streamlit entrypoint. Run with: make demo
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from compass import auth, db
from compass.branding import GLOBAL_CSS, footer_html, header_html
from compass.pages import (
    audit_log as audit_log_page,
)
from compass.pages import (
    clin_summary as clin_summary_page,
)
from compass.pages import (
    command_center as command_center_page,
)
from compass.pages import (
    feature_value as feature_value_page,
)
from compass.pages import (
    hybrid_acceptance as hybrid_acceptance_page,
)
from compass.pages import (
    login as login_page,
)
from compass.pages import (
    readiness as readiness_page,
)
from compass.pages import (
    risks as risks_page,
)
from compass.pages import (
    settings_page,
)
from compass.state import current_page, init_session, navigate

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass


def _navbar(user: auth.User | None) -> None:
    user_label = f"{user.name}" if user else None
    role = user.role if user else None
    st.markdown(header_html(user_label, role), unsafe_allow_html=True)

    if user is None:
        return

    page = current_page()
    items = [
        ("command_center", "Command Center"),
        ("clin_summary", "CLIN Summary"),
        ("readiness", "Readiness"),
        ("feature_value", "Features"),
        ("hybrid_acceptance", "Hybrid Acceptance"),
        ("risks", "Risks"),
        ("settings", "Settings"),
        ("audit_log", "Audit"),
    ]
    cols = st.columns(len(items) + 1)
    for col, (pid, label) in zip(cols[:-1], items, strict=False):
        marker = "• " if page == pid else ""
        if col.button(f"{marker}{label}", key=f"nav_{pid}", use_container_width=True):
            navigate(pid)
    if cols[-1].button("Sign out", key="nav_signout", use_container_width=True):
        auth.logout()
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Compass — by Zvolvant Solutions",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # Ensure schema exists on every startup (Streamlit Cloud cold start).
    db.init_db()
    init_session()

    user = auth.current_user()
    _navbar(user)

    if user is None:
        login_page.render()
        st.markdown(footer_html(), unsafe_allow_html=True)
        return

    page = current_page()
    if page == "command_center":
        command_center_page.render()
    elif page == "clin_summary":
        clin_summary_page.render()
    elif page == "readiness":
        readiness_page.render()
    elif page == "feature_value":
        feature_value_page.render()
    elif page == "hybrid_acceptance":
        hybrid_acceptance_page.render()
    elif page == "risks":
        risks_page.render()
    elif page == "settings":
        settings_page.render()
    elif page == "audit_log":
        audit_log_page.render()
    else:
        command_center_page.render()

    st.markdown(footer_html(), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
