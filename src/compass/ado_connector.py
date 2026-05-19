"""Azure DevOps REST connector.

v1 uses mock data shipped in ``scripts/seed_db.py``. v2 swaps this module's
``fetch_sprints()`` to read from ADO's REST API:

  GET https://dev.azure.com/{ORG}/{PROJECT}/_apis/work/teamsettings/iterations
  GET https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/wiql              (story points)
  GET https://dev.azure.com/{ORG}/{PROJECT}/_apis/test/runs             (UAT pass)

The interface here is the seam: page code calls ``fetch_sprints(clin_code)``
and gets a list of sprint dicts. v1 returns rows from the local DB; v2 will
hit ADO live and (optionally) cache to the DB.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from . import db

logger = logging.getLogger(__name__)


def is_live_ado_configured() -> bool:
    return bool(os.getenv("ADO_PAT") and os.getenv("ADO_ORG") and os.getenv("ADO_PROJECT"))


def fetch_sprints(clin_code: str | None = None) -> list[dict[str, Any]]:
    """Return sprint rows. v1: read from local seeded DB. v2: pull live from ADO."""
    if is_live_ado_configured():
        try:
            return _fetch_sprints_from_ado(clin_code)
        except Exception as exc:
            logger.warning("ADO fetch failed, falling back to local DB: %s", exc)

    query = """
        SELECT s.*, c.code AS clin_code, c.name AS clin_name,
               w.name AS workstream_name, p.name AS project_system_name
        FROM sprint s
        LEFT JOIN clin c ON c.id = s.clin_id
        LEFT JOIN workstream w ON w.id = s.workstream_id
        LEFT JOIN project_system p ON p.id = s.project_system_id
    """
    params: tuple = ()
    if clin_code:
        query += " WHERE c.code = ?"
        params = (clin_code,)
    query += " ORDER BY s.start_date"
    return db.fetch_all(query, params)


def _fetch_sprints_from_ado(clin_code: str | None) -> list[dict[str, Any]]:
    """v2 stub. The actual ADO REST queries land here once a PAT is configured."""
    org = os.environ["ADO_ORG"]
    project = os.environ["ADO_PROJECT"]
    pat = os.environ["ADO_PAT"]

    # Iteration list (sprint windows)
    base = f"https://dev.azure.com/{org}/{project}/_apis"
    auth = ("", pat)  # ADO basic auth uses empty username + PAT as password
    with httpx.Client(timeout=15.0, auth=auth) as client:
        # Get team iterations
        r = client.get(f"{base}/work/teamsettings/iterations?api-version=7.1-preview.1")
        r.raise_for_status()
        # NOTE: This is a stub — the real implementation needs WIQL queries
        # for story points + test runs for UAT first-pass, etc.
        # For v1 we never actually reach this branch because is_live_ado_configured()
        # is False until ADO secrets are set.
        raise NotImplementedError(
            "Live ADO sync is scaffolded but not yet wired. Set ADO_PAT/ORG/PROJECT in "
            "production secrets and complete the WIQL + test-runs queries here."
        )
