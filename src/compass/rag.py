"""RAG (Red / Amber / Green) threshold logic.

A KPI's RAG status is derived from its numeric value and the thresholds in the
Settings table. Direction matters:

  - "high_is_good": value >= green_threshold → green; >= yellow → amber; else red.
  - "low_is_good":  value <= green_threshold → green; <= yellow → amber; else red.

The default thresholds match the product spec:

  Predictability       high_is_good  green ≥ 0.85  yellow ≥ 0.75
  Story Completion     high_is_good  green ≥ 0.90  yellow ≥ 0.80
  Defect Leakage       low_is_good   green ≤ 0.05  yellow ≤ 0.08
  UAT First-Pass       high_is_good  green ≥ 0.95  yellow ≥ 0.90
  Cycle Time (days)    low_is_good   green ≤ 7     yellow ≤ 10
  Availability         high_is_good  green ≥ 0.995 yellow ≥ 0.99
  Burn Variance        low_is_good   green ≤ 0.10  yellow ≤ 0.15
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RAG = Literal["green", "amber", "red"]


@dataclass(frozen=True)
class Threshold:
    green: float
    yellow: float
    direction: Literal["high_is_good", "low_is_good"]


DEFAULT_THRESHOLDS: dict[str, Threshold] = {
    "predictability": Threshold(0.85, 0.75, "high_is_good"),
    "story_completion": Threshold(0.90, 0.80, "high_is_good"),
    "defect_leakage": Threshold(0.05, 0.08, "low_is_good"),
    "uat_first_pass": Threshold(0.95, 0.90, "high_is_good"),
    "cycle_time": Threshold(7.0, 10.0, "low_is_good"),
    "availability": Threshold(0.995, 0.99, "high_is_good"),
    "burn_variance": Threshold(0.10, 0.15, "low_is_good"),
}

# Overall score RAG (independent — applies to the 70/30 weighted score in 0..1)
OVERALL_RAG = Threshold(0.85, 0.70, "high_is_good")


def rag_for(value: float, threshold: Threshold) -> RAG:
    """Apply a single threshold and return red/amber/green."""
    if threshold.direction == "high_is_good":
        if value >= threshold.green:
            return "green"
        if value >= threshold.yellow:
            return "amber"
        return "red"
    # low_is_good
    if value <= threshold.green:
        return "green"
    if value <= threshold.yellow:
        return "amber"
    return "red"


def rag_for_kpi(kpi_name: str, value: float, overrides: dict[str, Threshold] | None = None) -> RAG:
    """Look up the threshold for a named KPI and return its RAG."""
    book = {**DEFAULT_THRESHOLDS, **(overrides or {})}
    if kpi_name not in book:
        raise KeyError(f"Unknown KPI for RAG lookup: {kpi_name!r}")
    return rag_for(value, book[kpi_name])


def overall_rag(weighted_score: float) -> RAG:
    """RAG status for the 70/30 overall weighted score (0..1)."""
    return rag_for(weighted_score, OVERALL_RAG)


def rollup_rag(rag_list: list[RAG]) -> RAG:
    """Worst-case rollup: a single red dominates; otherwise amber dominates green."""
    if not rag_list:
        return "amber"
    if "red" in rag_list:
        return "red"
    if "amber" in rag_list:
        return "amber"
    return "green"
