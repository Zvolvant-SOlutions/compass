"""Daily spend cap for Compass's Claude usage.

A coarse $-budget per UTC day. The Story Builder page (and any future
LLM-backed feature) calls ``check_and_reserve()`` before invoking Claude,
and ``record_spend()`` after the call returns with the actual estimated
cost. When today's total exceeds ``COMPASS_ANTHROPIC_DAILY_USD_CAP``, the
next request is politely refused until midnight UTC.

The ledger lives at ``~/.compass/spend.json`` — best-effort, in-container
persistence. For production we'd lift this into Azure SQL alongside the
audit log, but for v1 it's sufficient to make abuse expensive.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_PATH = Path.home() / ".compass" / "spend.json"
LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)

_LOCK = threading.Lock()

DEFAULT_DAILY_USD_CAP = 10.0


def _today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def daily_cap_usd() -> float:
    raw = os.getenv("COMPASS_ANTHROPIC_DAILY_USD_CAP", "").strip()
    if not raw:
        try:
            import streamlit as st  # type: ignore

            if "COMPASS_ANTHROPIC_DAILY_USD_CAP" in st.secrets:
                raw = str(st.secrets["COMPASS_ANTHROPIC_DAILY_USD_CAP"]).strip()
        except Exception:
            pass
    if not raw:
        return DEFAULT_DAILY_USD_CAP
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_DAILY_USD_CAP


def _load() -> dict[str, Any]:
    if not LEDGER_PATH.exists():
        return {}
    try:
        return json.loads(LEDGER_PATH.read_text())
    except Exception:
        return {}


def _save(data: dict[str, Any]) -> None:
    LEDGER_PATH.write_text(json.dumps(data, indent=2))


def usage_today() -> dict[str, Any]:
    """Return today's spend snapshot — {date, spend_usd, calls, cap_usd}."""
    with _LOCK:
        data = _load()
        day = _today_utc()
        entry = data.get(day, {"spend_usd": 0.0, "calls": 0})
        return {
            "date": day,
            "spend_usd": float(entry.get("spend_usd", 0.0)),
            "calls": int(entry.get("calls", 0)),
            "cap_usd": daily_cap_usd(),
        }


def can_spend() -> tuple[bool, str]:
    """Cheap pre-check: True if more spend allowed today; else (False, reason)."""
    snap = usage_today()
    if snap["spend_usd"] >= snap["cap_usd"]:
        return False, (
            f"Today's Compass Anthropic budget is exhausted "
            f"(${snap['spend_usd']:.2f} of ${snap['cap_usd']:.2f} cap). "
            "Try again after midnight UTC, or raise the cap in Streamlit Cloud secrets."
        )
    return True, ""


def record_spend(cost_usd: float) -> None:
    """Add ``cost_usd`` to today's running total."""
    if cost_usd <= 0:
        return
    with _LOCK:
        data = _load()
        day = _today_utc()
        entry = data.get(day, {"spend_usd": 0.0, "calls": 0})
        entry["spend_usd"] = float(entry["spend_usd"]) + float(cost_usd)
        entry["calls"] = int(entry["calls"]) + 1
        data[day] = entry
        _save(data)
