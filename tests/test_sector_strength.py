import pandas as pd

from backend.app.sector_strength import calculate_sector_strength


def make_history(start=100.0, step=1.0):
    close = [start + index * step for index in range(30)]
    index = pd.date_range("2026-01-01", periods=30, freq="B")
    return pd.DataFrame({
        "open": close, "high": [value + 1 for value in close],
        "low": [value - 1 for value in close], "close": close,
        "volume": [100000] * len(close),
    }, index=index)


def test_sector_strength_compares_equal_weight_sector_return_to_nifty():
    constituents = [
        {"symbol": "AAA", "sector": "IT"},
        {"symbol": "BBB", "sector": "IT"},
        {"symbol": "CCC", "sector": "BANK"},
    ]
    histories = {"AAA": make_history(100, 2), "BBB": make_history(100, 1.5), "CCC": make_history(100, 0.2)}
    result = calculate_sector_strength(constituents, histories, make_history(100, 0.5))
    assert "IT" in result["sectors"]
    assert result["sectors"]["IT"]["constituents_used"] == 2
    assert result["sectors"]["IT"]["relative_strength_pct"] > 0
    assert "BANK" not in result["sectors"]


def test_sector_strength_reports_missing_benchmark():
    result = calculate_sector_strength(
        [{"symbol": "AAA", "sector": "IT"}, {"symbol": "BBB", "sector": "IT"}],
        {"AAA": make_history(), "BBB": make_history()},
        None,
    )
    assert result["sectors"] == {}
    assert result["benchmark_return_pct"] is None
