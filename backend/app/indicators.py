"""Technical indicators used by the NSE swing-trading research engine.

Input OHLCV must be chronological (oldest row first). Functions return Series
aligned to the input index; warm-up periods are NaN. This module does not
generate trade signals or place orders.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_REQUIRED = {"high", "low", "close", "volume"}


def _validate(data: pd.DataFrame) -> None:
    missing = _REQUIRED.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if data.empty:
        raise ValueError("OHLCV data cannot be empty")
    if not data.index.is_monotonic_increasing:
        raise ValueError("OHLCV data must be ordered oldest to newest")


def sma(series: pd.Series, period: int) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return series.rolling(period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI."""
    if period < 1:
        raise ValueError("period must be >= 1")
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return result.mask((avg_loss == 0) & (avg_gain == 0), 50.0)


def true_range(data: pd.DataFrame) -> pd.Series:
    _validate(data)
    previous_close = data["close"].shift(1)
    ranges = pd.concat(
        [(data["high"] - data["low"]),
         (data["high"] - previous_close).abs(),
         (data["low"] - previous_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return true_range(data).ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()


def adx(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Return ADX, +DI and -DI using Wilder smoothing."""
    if period < 1:
        raise ValueError("period must be >= 1")
    _validate(data)
    up = data["high"].diff()
    down = -data["low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    smooth = lambda s: s.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    smoothed_tr = smooth(true_range(data))
    plus_di = 100 * smooth(plus_dm) / smoothed_tr.replace(0, np.nan)
    minus_di = 100 * smooth(minus_dm) / smoothed_tr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return pd.DataFrame({
        "adx": smooth(dx), "plus_di": plus_di, "minus_di": minus_di
    })


def macd(series: pd.Series, fast_period: int = 12, slow_period: int = 26,
         signal_period: int = 9) -> pd.DataFrame:
    if min(fast_period, slow_period, signal_period) < 1:
        raise ValueError("MACD periods must be >= 1")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")
    line = ema(series, fast_period) - ema(series, slow_period)
    signal = line.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
    return pd.DataFrame({"macd": line, "signal": signal, "histogram": line - signal})


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return volume / sma(volume, period).replace(0, np.nan)


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Append the baseline daily/intraday indicator set to an OHLCV frame."""
    _validate(data)
    result = data.copy()
    result["ema_20"] = ema(result["close"], 20)
    result["ema_50"] = ema(result["close"], 50)
    result["sma_50"] = sma(result["close"], 50)
    result["sma_150"] = sma(result["close"], 150)
    result["sma_200"] = sma(result["close"], 200)
    result["rsi_14"] = rsi(result["close"], 14)
    result["atr_14"] = atr(result, 14)
    result = result.join(adx(result, 14)).join(macd(result["close"]))
    result["relative_volume_20"] = relative_volume(result["volume"], 20)
    return result
