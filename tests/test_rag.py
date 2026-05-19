"""RAG threshold tests — verify direction-aware bucketing."""

from __future__ import annotations

import pytest

from compass.rag import DEFAULT_THRESHOLDS, overall_rag, rag_for_kpi, rollup_rag


@pytest.mark.parametrize(
    "kpi,value,expected",
    [
        ("predictability", 0.90, "green"),
        ("predictability", 0.80, "amber"),
        ("predictability", 0.70, "red"),
        ("defect_leakage", 0.04, "green"),
        ("defect_leakage", 0.07, "amber"),
        ("defect_leakage", 0.10, "red"),
        ("cycle_time", 6.0, "green"),
        ("cycle_time", 9.0, "amber"),
        ("cycle_time", 12.0, "red"),
        ("availability", 0.999, "green"),
        ("availability", 0.992, "amber"),
        ("availability", 0.98, "red"),
        ("burn_variance", 0.05, "green"),
        ("burn_variance", 0.12, "amber"),
        ("burn_variance", 0.20, "red"),
    ],
)
def test_rag_for_kpi(kpi, value, expected):
    assert rag_for_kpi(kpi, value) == expected


def test_rag_for_unknown_raises():
    with pytest.raises(KeyError):
        rag_for_kpi("not_a_kpi", 0.5)


def test_overall_rag_buckets():
    assert overall_rag(0.90) == "green"
    assert overall_rag(0.75) == "amber"
    assert overall_rag(0.50) == "red"


def test_rollup_takes_worst():
    assert rollup_rag(["green", "green", "green"]) == "green"
    assert rollup_rag(["green", "amber", "green"]) == "amber"
    assert rollup_rag(["green", "amber", "red"]) == "red"
    assert rollup_rag([]) == "amber"


def test_default_thresholds_complete():
    expected = {
        "predictability",
        "story_completion",
        "defect_leakage",
        "uat_first_pass",
        "cycle_time",
        "availability",
        "burn_variance",
    }
    assert set(DEFAULT_THRESHOLDS.keys()) == expected
