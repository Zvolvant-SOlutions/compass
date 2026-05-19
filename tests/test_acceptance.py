"""Hybrid acceptance state-machine tests."""

from __future__ import annotations

from compass import acceptance


def test_initial_state_is_value_pending():
    s = acceptance.initial_state()
    assert s.stage == "value_pending"
    assert s.payment_status == "held_pending"
    assert s.holdback_pct == 0.30
    assert s.rework_required_yn == 0


def test_technical_acceptance_holds_holdback():
    s = acceptance.initial_state(holdback_pct=0.25)
    after = acceptance.technically_accept(s)
    assert after.stage == "technically_accepted"
    assert after.payment_status == "held_pending"  # only partial released; status stays held
    assert acceptance.payment_release_pct(after) == 0.75  # 1 - holdback


def test_confirm_value_releases_full():
    s = acceptance.technically_accept(acceptance.initial_state())
    after = acceptance.confirm_value(s)
    assert after.stage == "fully_accepted"
    assert after.payment_status == "released"
    assert acceptance.payment_release_pct(after) == 1.0


def test_rework_holds_payment_and_reprioritizes():
    s = acceptance.technically_accept(acceptance.initial_state())
    after = acceptance.require_rework(s, backlog_impact="reprioritize", reason="missing UX")
    assert after.stage == "rework_required"
    assert after.payment_status == "held_pending"
    assert after.backlog_impact == "reprioritize"
    assert after.rework_required_yn == 1
    assert "missing UX" in after.rationale


def test_value_pending_features_release_nothing():
    s = acceptance.initial_state()
    assert acceptance.payment_release_pct(s) == 0.0


def test_rework_features_release_nothing():
    s = acceptance.require_rework(acceptance.initial_state())
    assert acceptance.payment_release_pct(s) == 0.0


def test_terminal_states_dont_revert():
    fully = acceptance.confirm_value(acceptance.technically_accept(acceptance.initial_state()))
    # Hitting technical-accept again on a fully-accepted feature should not flip it back
    after = acceptance.technically_accept(fully)
    assert after.stage == "fully_accepted"


def test_derive_state_round_trip():
    row = {
        "acceptance_stage": "technically_accepted",
        "payment_status": "held_pending",
        "backlog_impact": "continue",
        "holdback_pct": 0.30,
        "rework_required_yn": 0,
    }
    s = acceptance.derive_state(row)
    assert s.stage == "technically_accepted"
    assert s.payment_status == "held_pending"
    assert s.holdback_pct == 0.30
