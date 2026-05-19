"""Authentication and role-based access.

v1: bcrypt-hashed credentials stored in the ``users`` table. Login is a
Streamlit form; session state holds the logged-in user.

v2 (commented): Azure AD / Entra OAuth. The interface here is shaped so the
``current_user()`` helper switches transparently when ``AZURE_AD_TENANT_ID``
is set — pages keep calling ``require_role()`` regardless of which backend
is actually authenticating.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import bcrypt
import streamlit as st

from . import db

Role = Literal["COR", "PM", "PO", "READONLY"]


@dataclass(frozen=True)
class User:
    id: int
    email: str
    name: str
    role: Role


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def find_user_by_email(email: str) -> User | None:
    row = db.fetch_one(
        "SELECT id, email, name, role, password_hash, active FROM users WHERE email = ? AND active = 1",
        (email.strip().lower(),),
    )
    if not row:
        return None
    return User(id=row["id"], email=row["email"], name=row["name"], role=row["role"])


def authenticate(email: str, password: str) -> User | None:
    row = db.fetch_one(
        "SELECT id, email, name, role, password_hash, active FROM users WHERE email = ? AND active = 1",
        (email.strip().lower(),),
    )
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return User(id=row["id"], email=row["email"], name=row["name"], role=row["role"])


def azure_ad_enabled() -> bool:
    """Return True when Entra OAuth credentials are configured."""
    return bool(os.getenv("AZURE_AD_TENANT_ID") and os.getenv("AZURE_AD_CLIENT_ID"))


def current_user() -> User | None:
    """Return the logged-in user from session state, if any.

    When Azure AD is wired in (v2), this function reads from MSAL's token
    cache instead of session state. The page-level call sites don't change.
    """
    u = st.session_state.get("user")
    if u is None:
        return None
    if isinstance(u, dict):
        return User(id=u["id"], email=u["email"], name=u["name"], role=u["role"])
    return u


def login(user: User) -> None:
    st.session_state["user"] = {"id": user.id, "email": user.email, "name": user.name, "role": user.role}


def logout() -> None:
    st.session_state.pop("user", None)


# ---------------------------------------------------------------------------
# Role gating
# ---------------------------------------------------------------------------

ROLE_RANK: dict[Role, int] = {"READONLY": 0, "PO": 1, "PM": 2, "COR": 3}


def require_role(min_role: Role) -> User:
    """Halt the page with a polite message if the user lacks the required role."""
    user = current_user()
    if user is None:
        st.warning("You must sign in to view this page.")
        st.stop()
    if ROLE_RANK[user.role] < ROLE_RANK[min_role]:  # type: ignore[index]
        st.error(
            f"This action requires the {min_role} role. You are signed in as "
            f"{user.name} ({user.role}). Contact a COR to adjust access."
        )
        st.stop()
    return user


def can_edit(user: User | None) -> bool:
    """True if user is PO/PM/COR (i.e., not read-only)."""
    if user is None:
        return False
    return ROLE_RANK[user.role] >= ROLE_RANK["PO"]  # type: ignore[index]


def can_decide(user: User | None) -> bool:
    """True if user is a COR (acceptance decisions, threshold overrides)."""
    return user is not None and user.role == "COR"
