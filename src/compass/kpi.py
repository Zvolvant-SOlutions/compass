"""Pure KPI calculations.

Every function here is side-effect free and unit-tested. The contract:
inputs are primitives or dicts of primitives; outputs are floats (rounded to
four decimals) or dataclasses; nothing reaches the database from this module.

Formulas are exactly as specified in the product brief — see docs/KPI_FORMULAS.md
for the spec excerpt this file implements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _safe_div(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return num / den


def round4(x: float) -> float:
    return round(x, 4)


# ---------------------------------------------------------------------------
# Sprint-level KPIs
# ---------------------------------------------------------------------------


def sprint_predictability_pct(committed_points: float, completed_points: float) -> float:
    return round4(_safe_div(completed_points, committed_points))


def story_completion_pct(committed_points: float, completed_points: float) -> float:
    # In the spec these are defined identically; kept as separate functions so
    # we can decouple later (e.g., predictability against forecast vs. completion).
    return round4(_safe_div(completed_points, committed_points))


def defect_leakage_pct(post_release_defects: int, accepted_stories: int) -> float:
    return round4(_safe_div(post_release_defects, accepted_stories))


def uat_first_pass_pct(uat_first_pass_count: int, uat_tests: int) -> float:
    return round4(_safe_div(uat_first_pass_count, uat_tests))


def cycle_time_days(avg_cycle_time_days: float) -> float:
    return round4(avg_cycle_time_days)


def burn_variance_pct(actual_burn_usd: float, planned_burn_usd: float) -> float:
    if planned_burn_usd == 0:
        return 0.0
    return round4(abs(actual_burn_usd - planned_burn_usd) / planned_burn_usd)


def availability_pct(value: float) -> float:
    return round4(value)


@dataclass(frozen=True)
class SprintKpiResult:
    sprint_predictability_pct: float
    story_completion_pct: float
    defect_leakage_pct: float
    uat_first_pass_pct: float
    cycle_time_days: float
    burn_variance_pct: float
    availability_pct: float


def compute_sprint_kpis(sprint: dict[str, Any]) -> SprintKpiResult:
    """Compute every sprint-level KPI from a sprint row dict.

    Expects keys matching the ``sprint`` table columns. Missing numerics
    default to 0 so partial rows still compute defensively.
    """
    return SprintKpiResult(
        sprint_predictability_pct=sprint_predictability_pct(
            sprint.get("committed_points", 0) or 0,
            sprint.get("completed_points", 0) or 0,
        ),
        story_completion_pct=story_completion_pct(
            sprint.get("committed_points", 0) or 0,
            sprint.get("completed_points", 0) or 0,
        ),
        defect_leakage_pct=defect_leakage_pct(
            sprint.get("post_release_defects", 0) or 0,
            sprint.get("accepted_stories", 0) or 0,
        ),
        uat_first_pass_pct=uat_first_pass_pct(
            sprint.get("uat_first_pass_count", 0) or 0,
            sprint.get("uat_tests", 0) or 0,
        ),
        cycle_time_days=cycle_time_days(sprint.get("avg_cycle_time_days", 0) or 0),
        burn_variance_pct=burn_variance_pct(
            sprint.get("actual_burn_usd", 0) or 0,
            sprint.get("planned_burn_usd", 0) or 0,
        ),
        availability_pct=availability_pct(sprint.get("availability_pct", 0) or 0),
    )


# ---------------------------------------------------------------------------
# Customer Value and Overall Weighted Score
# ---------------------------------------------------------------------------

# Weights as specified in the product brief — sum to 1.0
CUSTOMER_VALUE_WEIGHTS = {
    "business_value_rate": 0.25,
    "user_satisfaction": 0.25,
    "adoption_rate": 0.20,
    "rework_rate_inverted": 0.15,  # rework_rate is inverted: 1 - rework_rate
    "feature_utilization": 0.15,
}

DELIVERY_WEIGHT = 0.70
CUSTOMER_VALUE_WEIGHT = 0.30


def customer_value_score(inputs: dict[str, float]) -> float:
    """Compute weighted customer value score in 0..1 from input dimensions.

    Expected keys (each 0..1): business_value_rate, user_satisfaction,
    adoption_rate, rework_rate, feature_utilization.
    """
    bvr = inputs.get("business_value_rate", 0) or 0
    us = inputs.get("user_satisfaction", 0) or 0
    ar = inputs.get("adoption_rate", 0) or 0
    rr = inputs.get("rework_rate", 0) or 0
    fu = inputs.get("feature_utilization", 0) or 0
    score = (
        CUSTOMER_VALUE_WEIGHTS["business_value_rate"] * bvr
        + CUSTOMER_VALUE_WEIGHTS["user_satisfaction"] * us
        + CUSTOMER_VALUE_WEIGHTS["adoption_rate"] * ar
        + CUSTOMER_VALUE_WEIGHTS["rework_rate_inverted"] * (1.0 - rr)
        + CUSTOMER_VALUE_WEIGHTS["feature_utilization"] * fu
    )
    return round4(max(0.0, min(1.0, score)))


# Sub-metric weights inside Delivery Performance. Configurable via Settings table
# in production; defaults below sum to 1.0 across the seven sprint KPIs.
DELIVERY_SUBMETRIC_WEIGHTS = {
    "predictability": 0.18,
    "story_completion": 0.18,
    "defect_leakage_inverted": 0.15,
    "uat_first_pass": 0.16,
    "cycle_time_normalized": 0.12,
    "burn_variance_inverted": 0.11,
    "availability": 0.10,
}


def _normalize_cycle_time(days: float, target_days: float = 7.0, max_days: float = 30.0) -> float:
    """Map cycle time in days to a 0..1 score (high is good)."""
    if days <= target_days:
        return 1.0
    if days >= max_days:
        return 0.0
    return round4(1.0 - (days - target_days) / (max_days - target_days))


def delivery_performance_score(kpis: SprintKpiResult) -> float:
    """Aggregate the seven sprint KPIs into a 0..1 Delivery Performance score."""
    parts = {
        "predictability": kpis.sprint_predictability_pct,
        "story_completion": kpis.story_completion_pct,
        "defect_leakage_inverted": 1.0 - min(1.0, kpis.defect_leakage_pct),
        "uat_first_pass": kpis.uat_first_pass_pct,
        "cycle_time_normalized": _normalize_cycle_time(kpis.cycle_time_days),
        "burn_variance_inverted": 1.0 - min(1.0, kpis.burn_variance_pct),
        "availability": kpis.availability_pct,
    }
    total = sum(DELIVERY_SUBMETRIC_WEIGHTS[k] * v for k, v in parts.items())
    return round4(max(0.0, min(1.0, total)))


def overall_weighted_score(delivery: float, customer_value: float) -> float:
    """70% Delivery + 30% Customer Value."""
    return round4(DELIVERY_WEIGHT * delivery + CUSTOMER_VALUE_WEIGHT * customer_value)
