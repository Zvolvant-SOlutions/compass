"""Daily spend-cap tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def tmp_ledger(tmp_path, monkeypatch):
    import compass.spend_cap as sc

    monkeypatch.setattr(sc, "LEDGER_PATH", tmp_path / "spend.json")
    monkeypatch.setenv("COMPASS_ANTHROPIC_DAILY_USD_CAP", "1.00")
    yield sc


def test_initial_usage_is_zero(tmp_ledger):
    snap = tmp_ledger.usage_today()
    assert snap["spend_usd"] == 0.0
    assert snap["calls"] == 0
    assert snap["cap_usd"] == 1.0


def test_can_spend_when_under_cap(tmp_ledger):
    ok, _ = tmp_ledger.can_spend()
    assert ok is True


def test_record_spend_increments(tmp_ledger):
    tmp_ledger.record_spend(0.25)
    tmp_ledger.record_spend(0.30)
    snap = tmp_ledger.usage_today()
    assert snap["spend_usd"] == pytest.approx(0.55)
    assert snap["calls"] == 2


def test_cap_blocks_new_calls(tmp_ledger):
    tmp_ledger.record_spend(1.20)  # over cap
    ok, reason = tmp_ledger.can_spend()
    assert ok is False
    assert "budget is exhausted" in reason
    assert "$1.00" in reason


def test_default_cap_when_unset(tmp_path, monkeypatch):
    import compass.spend_cap as sc

    monkeypatch.setattr(sc, "LEDGER_PATH", tmp_path / "spend.json")
    monkeypatch.delenv("COMPASS_ANTHROPIC_DAILY_USD_CAP", raising=False)
    assert sc.daily_cap_usd() == sc.DEFAULT_DAILY_USD_CAP


def test_negative_spend_is_noop(tmp_ledger):
    tmp_ledger.record_spend(-0.50)
    tmp_ledger.record_spend(0.0)
    snap = tmp_ledger.usage_today()
    assert snap["spend_usd"] == 0.0
    assert snap["calls"] == 0
