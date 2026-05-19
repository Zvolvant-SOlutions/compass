"""KPI formula tests — covers all seven sprint metrics + weighted score."""

from __future__ import annotations

from compass import kpi


def test_predictability():
    assert kpi.sprint_predictability_pct(50, 50) == 1.0
    assert kpi.sprint_predictability_pct(50, 40) == 0.8
    assert kpi.sprint_predictability_pct(0, 10) == 0.0  # zero committed -> 0


def test_defect_leakage():
    assert kpi.defect_leakage_pct(0, 20) == 0.0
    assert kpi.defect_leakage_pct(1, 20) == 0.05
    assert kpi.defect_leakage_pct(5, 0) == 0.0


def test_uat_first_pass():
    assert kpi.uat_first_pass_pct(19, 20) == 0.95
    assert kpi.uat_first_pass_pct(0, 0) == 0.0


def test_burn_variance():
    assert kpi.burn_variance_pct(100, 100) == 0.0
    assert kpi.burn_variance_pct(120, 100) == 0.2
    assert kpi.burn_variance_pct(80, 100) == 0.2  # always |actual - planned| / planned
    assert kpi.burn_variance_pct(0, 0) == 0.0


def test_customer_value_score_inverts_rework():
    inputs = {
        "business_value_rate": 0.8,
        "user_satisfaction": 0.8,
        "adoption_rate": 0.7,
        "rework_rate": 0.1,  # gets inverted -> 0.9
        "feature_utilization": 0.7,
    }
    score = kpi.customer_value_score(inputs)
    # 0.25*0.8 + 0.25*0.8 + 0.20*0.7 + 0.15*(1-0.1) + 0.15*0.7
    expected = 0.20 + 0.20 + 0.14 + 0.135 + 0.105
    assert abs(score - round(expected, 4)) < 0.001


def test_overall_weighted_score_is_70_30():
    assert kpi.overall_weighted_score(1.0, 0.0) == 0.7
    assert kpi.overall_weighted_score(0.0, 1.0) == 0.3
    assert kpi.overall_weighted_score(1.0, 1.0) == 1.0


def test_compute_sprint_kpis_handles_zeroes():
    result = kpi.compute_sprint_kpis({})
    assert result.sprint_predictability_pct == 0.0
    assert result.defect_leakage_pct == 0.0
    assert result.uat_first_pass_pct == 0.0


def test_delivery_performance_score_in_bounds():
    perfect_kpis = kpi.SprintKpiResult(
        sprint_predictability_pct=1.0,
        story_completion_pct=1.0,
        defect_leakage_pct=0.0,
        uat_first_pass_pct=1.0,
        cycle_time_days=5.0,
        burn_variance_pct=0.0,
        availability_pct=1.0,
    )
    assert kpi.delivery_performance_score(perfect_kpis) == 1.0

    worst_kpis = kpi.SprintKpiResult(
        sprint_predictability_pct=0.0,
        story_completion_pct=0.0,
        defect_leakage_pct=1.0,
        uat_first_pass_pct=0.0,
        cycle_time_days=60.0,
        burn_variance_pct=2.0,
        availability_pct=0.0,
    )
    assert kpi.delivery_performance_score(worst_kpis) == 0.0
