import pandas as pd

from backend.app.historical_market_filter import evaluate_historical_market_filter


def rising_history(periods=230):
    close = [100 + i * 0.5 for i in range(periods)]
    index = pd.date_range("2025-01-01", periods=periods, freq="B")
    return pd.DataFrame({
        "open": close, "high": [x + 1 for x in close],
        "low": [x - 1 for x in close], "close": close,
        "volume": [100000] * periods,
    }, index=index)


def test_filter_uses_only_history_available_on_signal_date():
    first = rising_history()
    second = rising_history(231)
    signal_date = str(first.index[-1].date())
    trade = {
        "symbol": "AAA", "signal_date": signal_date, "entry_date": str(second.index[-1].date()),
        "exit_date": str(second.index[-1].date()), "entry_price": 200, "exit_price": 205,
        "stop_price": 195, "net_return_pct": 2.0, "r_multiple": 0.4,
    }
    result = evaluate_historical_market_filter(
        [trade], {"AAA": first, "BBB": first.copy()}, first,
        {"AAA": "IT", "BBB": "IT"}, score_threshold=65, minimum_completeness_pct=80,
    )
    assert result["snapshots_calculated"] == 1
    assert result["trades"][0]["market_intelligence"]["score"] is not None
    assert result["trades"][0]["market_intelligence"]["data_completeness_pct"] == 100
    assert len(result["accepted_trades"]) == 1
