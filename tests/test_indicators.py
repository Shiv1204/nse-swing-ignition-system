import numpy as np
import pandas as pd
import pytest

from backend.app.indicators import (
    adx, atr, calculate_indicators, ema, macd, relative_volume, rsi, sma,
)


def sample_ohlcv(rows: int = 260) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = pd.Series(np.linspace(100, 180, rows), index=index)
    return pd.DataFrame({
        "open": close - 0.5,
        "high": close + 2.0,
        "low": close - 2.0,
        "close": close,
        "volume": pd.Series(np.full(rows, 100_000.0), index=index),
    })


def test_sma_and_ema() -> None:
    values = pd.Series([1.0, 2.0, 3.0, 4.0])
    assert sma(values, 3).iloc[-1] == pytest.approx(3.0)
    assert ema(values, 2).iloc[-1] == pytest.approx(3.5185, abs=0.001)


def test_rsi_on_persistent_rise() -> None:
    assert rsi(pd.Series(np.arange(1.0, 40.0)), 14).iloc[-1] == pytest.approx(100.0)


def test_atr_is_positive() -> None:
    assert atr(sample_ohlcv(), 14).iloc[-1] > 0


def test_adx_directional_columns() -> None:
    result = adx(sample_ohlcv(), 14)
    assert list(result.columns) == ["adx", "plus_di", "minus_di"]
    assert result["plus_di"].iloc[-1] > result["minus_di"].iloc[-1]


def test_macd_columns() -> None:
    result = macd(sample_ohlcv()["close"])
    assert list(result.columns) == ["macd", "signal", "histogram"]
    assert result["histogram"].notna().any()


def test_relative_volume_at_average_is_one() -> None:
    assert relative_volume(pd.Series([100.0] * 25), 20).iloc[-1] == pytest.approx(1.0)


def test_indicator_bundle() -> None:
    result = calculate_indicators(sample_ohlcv())
    expected = {
        "ema_20", "ema_50", "sma_50", "sma_150", "sma_200",
        "rsi_14", "atr_14", "adx", "plus_di", "minus_di",
        "macd", "signal", "histogram", "relative_volume_20",
    }
    assert expected.issubset(result.columns)
    assert result["sma_200"].notna().any()


def test_missing_columns_raise_error() -> None:
    with pytest.raises(ValueError, match="Missing required columns"):
        atr(pd.DataFrame({"close": [1.0]}))


def test_unsorted_index_is_rejected() -> None:
    with pytest.raises(ValueError, match="oldest to newest"):
        calculate_indicators(sample_ohlcv(5).iloc[::-1])
