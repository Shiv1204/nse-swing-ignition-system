from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from backend.app.backtesting import backtest_symbol, summarize_trades


def rising_frame(count=240):
    dates = pd.date_range("2024-01-01", periods=count, freq="B", tz="UTC")
    close = [100 + i * 0.15 for i in range(count)]
    return pd.DataFrame({
        "open": [x - 0.1 for x in close],
        "high": [x + 0.5 for x in close],
        "low": [x - 0.5 for x in close],
        "close": close,
        "volume": [200000.0] * count,
    }, index=dates)


def test_metrics_empty_and_profitable_trades():
    assert summarize_trades([])["trade_count"] == 0
    result = summarize_trades([
        {"net_return_pct": 4.0, "r_multiple": 2.0},
        {"net_return_pct": -2.0, "r_multiple": -1.0},
    ])
    assert result["trade_count"] == 2
    assert result["win_rate_pct"] == 50
    assert result["profit_factor"] == 2


def test_backtest_rejects_short_history():
    with pytest.raises(ValueError, match="211"):
        backtest_symbol("ABC", rising_frame(210), "reversal")


def test_backtest_result_has_trade_schema():
    result = backtest_symbol("ABC", rising_frame(), "reversal")
    assert result["setup"] == "reversal"
    assert "trade_count" in result
    for trade in result["trades"]:
        assert trade["entry_date"] >= trade["signal_date"]
        assert trade["exit_reason"] in {"stop", "target", "time"}
        assert trade["holding_sessions"] <= 10


def test_backtest_trade_includes_daily_marks_and_turnover():
    result = backtest_symbol("ABC", rising_frame(), "reversal")
    for trade in result["trades"]:
        assert "average_daily_turnover" in trade
        assert "mark_to_market" in trade
        assert trade["mark_to_market"][-1]["date"] == trade["exit_date"]
