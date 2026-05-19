"""Hybrid acceptance state machine.

Encodes the Stage 1 (Technical) → Stage 2 (Value) → Fully Accepted / Rework
workflow described in the product spec, including the holdback-percent rule
that gates payment release until value is confirmed.

This module is pure: it takes a feature dict and returns the next state +
side-effect intent (payment, backlog action). The DB writer in pages/feature_value.py
applies the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Stage = Literal["technically_accepted", "value_pending", "fully_accepted", "rework_required"]
PaymentStatus = Literal["released", "held_pending"]
BacklogImpact = Literal["continue", "reprioritize", "stop"]


@dataclass(frozen=True)
class AcceptanceState:
    stage: Stage
    payment_status: PaymentStatus
    backlog_impact: BacklogImpact
    holdback_pct: float
    rework_required_yn: int  # 0 or 1
    rationale: str


def initial_state(holdback_pct: float = 0.30) -> AcceptanceState:
    """Newly created feature before technical acceptance."""
    return AcceptanceState(
        stage="value_pending",
        payment_status="held_pending",
        backlog_impact="continue",
        holdback_pct=holdback_pct,
        rework_required_yn=0,
        rationale="Feature created; awaiting technical acceptance.",
    )


def technically_accept(
    current: AcceptanceState, *, value_validation_window_days: int = 30
) -> AcceptanceState:
    """Stage 1 — DoD met. Open value validation window. Hold the holdback portion.

    The contractor receives (1 - holdback_pct) of the slice; the rest is held
    until Stage 2 confirms business value.
    """
    if current.stage in {"fully_accepted", "rework_required"}:
        return current  # terminal — no-op
    return AcceptanceState(
        stage="technically_accepted",
        payment_status="held_pending",  # only partial release happens at this stage
        backlog_impact="continue",
        holdback_pct=current.holdback_pct,
        rework_required_yn=0,
        rationale=(
            "Technical acceptance recorded. Value validation window opens; "
            f"{int(current.holdback_pct * 100)}% holdback retained pending Stage 2."
        ),
    )


def confirm_value(current: AcceptanceState) -> AcceptanceState:
    """Stage 2 — business value validated. Release remaining holdback."""
    if current.stage == "rework_required":
        return current  # rework was already triggered — can't shortcut to accepted
    return AcceptanceState(
        stage="fully_accepted",
        payment_status="released",
        backlog_impact="continue",
        holdback_pct=current.holdback_pct,
        rework_required_yn=0,
        rationale="Stage 2 value validation confirmed. Full payment released.",
    )


def require_rework(
    current: AcceptanceState,
    *,
    backlog_impact: BacklogImpact = "reprioritize",
    reason: str = "",
) -> AcceptanceState:
    """Stage 2 found a value gap. Hold payment, flag rework, optionally adjust backlog."""
    rationale = "Rework required: value gap identified."
    if reason:
        rationale += f" {reason}"
    return AcceptanceState(
        stage="rework_required",
        payment_status="held_pending",
        backlog_impact=backlog_impact,
        holdback_pct=current.holdback_pct,
        rework_required_yn=1,
        rationale=rationale,
    )


def derive_state(feature_row: dict) -> AcceptanceState:
    """Reconstruct an ``AcceptanceState`` from a feature_value row dict."""
    return AcceptanceState(
        stage=feature_row.get("acceptance_stage") or "value_pending",
        payment_status=feature_row.get("payment_status") or "held_pending",
        backlog_impact=feature_row.get("backlog_impact") or "continue",
        holdback_pct=float(feature_row.get("holdback_pct") or 0.30),
        rework_required_yn=int(feature_row.get("rework_required_yn") or 0),
        rationale="",
    )


def payment_release_pct(state: AcceptanceState) -> float:
    """How much of this feature's invoice slice should be released today (0..1)."""
    if state.stage == "fully_accepted":
        return 1.0
    if state.stage == "technically_accepted":
        return 1.0 - state.holdback_pct
    # value_pending and rework_required release nothing until decisions land
    return 0.0
