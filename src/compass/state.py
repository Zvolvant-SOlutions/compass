"""Session state helpers for Compass."""

from __future__ import annotations

import streamlit as st


def init_session() -> None:
    defaults = {"page": "command_center"}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def navigate(page: str) -> None:
    st.session_state["page"] = page
    st.rerun()


def current_page() -> str:
    return st.session_state.get("page", "command_center")
