import numpy as np
import pandas as pd
import pytest

from backend.app.market_regime import classify_market_regime


def make_trend(count=260, direction=1):
    index = pd.date_range("2024-01-01", periods=count, freq="B")
    close = 20000 + direction * np.arange(count) * 8.0 + np.sin(np.arange(count) / 6) * 20
    return pd.DataFrame({
        "open": close - 5,
        "high": close + 15,
        "low": close - 15,
        "close": close,
        "volume": np.full(count, 1_000_000.0),
    }, index=index)


def test_market_regime_requires_210_sessions():
    with pytest.raises(ValueError, match="210"):
        classify_market_regime(make_trend(100))


def test_market_regime_returns_explainable_fields():
    result = classify_market_regime(make_trend())
    assert result["regime"] in {"bullish", "sideways", "bearish"}
    assert result["benchmark"] == "^NSEI"
    assert len(result["bullish_checks"]) == 5
    assert len(result["bearish_checks"]) == 4
    assert result["suggested_exposure"] in {"normal", "selective", "defensive"}


def test_market_regime_rejects_duplicate_or_unsorted_dates():
    frame = make_trend()
    frame.index = list(frame.index[:-1]) + [frame.index[-2]]
    with pytest.raises(ValueError, match="unique chronological"):
        classify_market_regime(frame)
