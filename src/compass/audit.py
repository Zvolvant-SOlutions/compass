"""Audit log helpers.

Every mutation of an auditable entity should call ``log()`` with the actor,
the field changed, and the old/new values. Audit rows are immutable; the page
that renders the log shows them chronologically with filters.
"""

from __future__ import annotations

from typing import Any

from . import db
from .auth import User


def log(
    actor: User,
    *,
    entity: str,
    entity_id: int | None,
    action: str,
    field: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    rationale: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO audit_log (actor_email, actor_role, entity, entity_id, action,
                               field, old_value, new_value, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor.email,
            actor.role,
            entity,
            entity_id,
            action,
            field,
            None if old_value is None else str(old_value),
            None if new_value is None else str(new_value),
            rationale,
        ),
    )


def recent(limit: int = 200) -> list[dict[str, Any]]:
    return db.fetch_all(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    )
