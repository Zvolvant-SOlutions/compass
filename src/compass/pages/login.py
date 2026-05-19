"""Login page — bcrypt credentials. Azure AD button is a v2 placeholder.

The demo-credentials list is hidden by default. Set the
``COMPASS_SHOW_DEMO_CREDENTIALS`` env var or Streamlit secret to ``true``
to reveal it (useful for internal walkthroughs; should be off in any
production-facing deploy).
"""

from __future__ import annotations

import os

import streamlit as st

from .. import auth


def _show_demo_credentials() -> bool:
    val = os.getenv("COMPASS_SHOW_DEMO_CREDENTIALS", "").strip().lower()
    if not val:
        try:
            if "COMPASS_SHOW_DEMO_CREDENTIALS" in st.secrets:
                val = str(st.secrets["COMPASS_SHOW_DEMO_CREDENTIALS"]).strip().lower()
        except Exception:
            pass
    return val in {"1", "true", "yes", "on"}


def render() -> None:
    st.markdown(
        "<div style='max-width:420px; margin: 1.5rem auto 0;'>"
        "<h2 style='font-family:DM Serif Display,serif; color:#0B2A4A; margin:0 0 0.4rem'>Sign in</h2>"
        "<p style='color:#48515E; margin:0 0 1rem; font-size:0.92rem'>"
        "Compass is restricted to authorized COR, PM, PO, and auditor accounts. "
        "Contact your program lead if you need access."
        "</p></div>",
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        email = st.text_input("Email", key="login_email", placeholder="you@agency.gov")
        password = st.text_input("Password", key="login_password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        user = auth.authenticate(email, password)
        if user is None:
            st.error("Invalid email or password. Contact your program lead if you've forgotten yours.")
            return
        auth.login(user)
        st.success(f"Signed in as {user.name} ({user.role}).")
        st.rerun()

    if auth.azure_ad_enabled():
        st.markdown("<hr style='margin:1.4rem 0;'>", unsafe_allow_html=True)
        st.caption("Or sign in with your organization account:")
        # v2: trigger Azure AD OAuth here
        st.button("Sign in with Microsoft Entra", disabled=True, help="Coming in v2")

    if _show_demo_credentials():
        with st.expander("Demo credentials (v1)"):
            st.markdown(
                "All passwords are `compass-demo`. Use these to walk through the four role views:\n\n"
                "- `cor@example.gov` — COR (acceptance decisions, threshold overrides)\n"
                "- `pm@example.gov` — Program Manager (data entry, mitigations, risks)\n"
                "- `po@example.gov` — Product Owner (data entry, mitigations, risks)\n"
                "- `auditor@example.gov` — Read-only (dashboards + audit log)"
            )
