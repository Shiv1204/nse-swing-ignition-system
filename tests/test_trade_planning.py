import numpy as np
import pandas as pd
import pytest

from backend.app.trade_planning import build_trade_plan, evaluate_hourly_confirmation


def make_bars(rows=260):
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    close = 100 + np.arange(rows) * 0.2 + np.sin(np.arange(rows) / 5)
    return pd.DataFrame({
        "open": close - 0.2,
        "high": close + 0.8,
        "low": close - 0.8,
        "close": close,
        "volume": np.full(rows, 250_000.0),
    }, index=index)


def test_trade_plan_has_entry_stop_targets_and_position_size():
    result = build_trade_plan("abc", make_bars(), "momentum")
    assert result["symbol"] == "ABC"
    assert result["entry_trigger"] > result["stop_loss"]
    assert result["targets"]["target_1_1_5R"] > result["entry_trigger"]
    assert result["targets"]["target_2_2R"] > result["targets"]["target_1_1_5R"]
    assert result["targets"]["target_3_3R"] > result["targets"]["target_2_2R"]
    assert result["sizing"]["quantity"] >= 0
    assert result["sizing"]["estimated_risk"] <= result["sizing"]["risk_budget"]


def test_trade_plan_marks_failed_scanner_conditions():
    result = build_trade_plan("abc", make_bars(), "vcp")
    assert result["scanner"]["setup"] == "vcp_candidate"
    assert result["status"] in {"ready_to_watch", "conditions_not_met", "trigger_already_crossed", "waiting_for_hourly_data", "hourly_confirmation_failed"}


def test_trade_plan_rejects_short_history_and_invalid_risk():
    with pytest.raises(ValueError, match="210"):
        build_trade_plan("abc", make_bars(100), "reversal")
    with pytest.raises(ValueError, match="risk_per_trade_pct"):
        build_trade_plan("abc", make_bars(), "reversal", risk_per_trade_pct=0)


def test_hourly_confirmation_requires_60_bars():
    short = evaluate_hourly_confirmation(make_bars(40))
    assert short["status"] == "unavailable"
    assert short["passed"] is False


def test_hourly_confirmation_reports_all_five_checks():
    result = evaluate_hourly_confirmation(make_bars(100))
    assert result["status"] in {"confirmed", "not_confirmed"}
    assert len(result["checks"]) == 5
    assert result["passed"] == (len(result["failed_conditions"]) == 0)


def test_trade_plan_waits_when_hourly_data_is_missing():
    result = build_trade_plan("abc", make_bars(), "momentum")
    assert result["hourly_confirmation"]["status"] == "unavailable"
    if result["scanner"]["passed"] and result["status"] != "trigger_already_crossed":
        assert result["status"] == "waiting_for_hourly_data"
