"""Anthropic SDK wrapper for Compass — the same pattern as the NIST tool.

Centralizes lazy client construction, retry with bounded backoff, secret
resolution from env or Streamlit secrets, and a coarse spend estimator so
features that call Claude can surface "you've used $X today" to the user
when needed.
"""

from __future__ import annotations

import json
import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(".env"), override=False)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Approximate token pricing for Sonnet 4.6 (USD per 1M tokens)
PRICE_PER_M_INPUT = 3.0
PRICE_PER_M_OUTPUT = 15.0

_RETRY_BACKOFFS_S: tuple[float, ...] = (1.0, 2.0, 4.0)


def _get_secret(name: str, default: str = "") -> str:
    val = os.getenv(name, "").strip()
    if val:
        return val
    try:
        import streamlit as st  # type: ignore

        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return default


def _is_transient(exc: BaseException) -> bool:
    import anthropic

    if isinstance(
        exc,
        (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        ),
    ):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        status = getattr(exc, "status_code", None)
        return isinstance(status, int) and status >= 500
    return False


def call_with_retry(client: Any, **kwargs: Any) -> Any:
    max_attempts = len(_RETRY_BACKOFFS_S)
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return client.messages.create(**kwargs)
        except Exception as exc:
            if not _is_transient(exc):
                raise
            last_exc = exc
            logger.warning("Claude transient failure %d/%d: %s", attempt + 1, max_attempts, exc)
            if attempt < max_attempts - 1:
                time.sleep(_RETRY_BACKOFFS_S[attempt])
    assert last_exc is not None
    raise last_exc


@lru_cache(maxsize=1)
def _client() -> Any | None:
    key = _get_secret("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        from anthropic import Anthropic

        return Anthropic(api_key=key)
    except Exception as exc:
        logger.warning("anthropic client could not initialize: %s", exc)
        return None


def get_client() -> Any | None:
    return _client()


def is_enabled() -> bool:
    return _client() is not None


def extract_text(response: Any) -> str:
    return "".join(b.text for b in response.content if hasattr(b, "text")).strip()


def extract_json(response: Any) -> dict[str, Any]:
    raw = extract_text(response).strip()
    if raw.startswith("```"):
        first_newline = raw.find("\n")
        if first_newline != -1:
            raw = raw[first_newline + 1 :]
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3].rstrip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found: {raw[:200]!r}")
    return json.loads(raw[start : end + 1])


def estimate_call_cost_usd(response: Any) -> float:
    u = getattr(response, "usage", None)
    if u is None:
        return 0.0
    in_t = getattr(u, "input_tokens", 0) or 0
    out_t = getattr(u, "output_tokens", 0) or 0
    return (in_t * PRICE_PER_M_INPUT + out_t * PRICE_PER_M_OUTPUT) / 1_000_000.0
