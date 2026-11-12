import pandas as pd

from backend.app.market_breadth import calculate_market_breadth


def history(start=100.0, step=1.0):
    close = [start + i * step for i in range(220)]
    index = pd.date_range("2025-01-01", periods=len(close), freq="B")
    return pd.DataFrame({
        "open": close, "high": [x + 1 for x in close],
        "low": [x - 1 for x in close], "close": close,
        "volume": [10000] * len(close),
    }, index=index)


def test_market_breadth_calculates_participation():
    result = calculate_market_breadth({"AAA": history(), "BBB": history(200, -0.2)})
    assert result["symbols_available"] == 2
    assert result["above_sma20_pct"] is not None
    assert result["above_sma50_pct"] is not None
    assert result["above_sma200_pct"] is not None
    assert result["advances"] + result["declines"] + result["unchanged"] == 2


def test_market_breadth_reports_empty_coverage():
    result = calculate_market_breadth({"AAA": history().tail(100)})
    assert result["symbols_available"] == 0
    assert result["coverage_pct"] == 0
    assert result["above_sma200_pct"] is None
