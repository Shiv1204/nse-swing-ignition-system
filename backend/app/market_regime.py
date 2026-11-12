"""Broad-market regime classification using a benchmark daily series."""
from __future__ import annotations

import pandas as pd

from backend.app.indicators import calculate_indicators


def classify_market_regime(data: pd.DataFrame, symbol: str = "^NSEI") -> dict:
    """Classify benchmark conditions from completed daily OHLCV bars.

    Rules are transparent heuristics, not predictive probabilities. At least
    210 sessions are required so the 200-session average and its slope exist.
    """
    if len(data) < 210:
        raise ValueError("At least 210 daily benchmark candles are required")
    if not data.index.is_monotonic_increasing or data.index.has_duplicates:
        raise ValueError("Benchmark bars must have unique chronological timestamps")
    frame = calculate_indicators(data)
    latest = frame.iloc[-1]
    close = float(latest["close"])
    sma50 = float(latest["sma_50"])
    sma200 = float(latest["sma_200"])
    prior_sma50 = float(frame["sma_50"].iloc[-21])
    prior_sma200 = float(frame["sma_200"].iloc[-21])
    return_20d = (close / float(frame["close"].iloc[-21]) - 1) * 100
    adx = float(latest["adx"])
    conditions = {
        "close_above_sma50": close > sma50,
        "sma50_above_sma200": sma50 > sma200,
        "sma50_rising_over_20_sessions": sma50 > prior_sma50,
        "sma200_rising_over_20_sessions": sma200 > prior_sma200,
        "positive_20_session_return": return_20d > 0,
    }
    bullish_count = sum(conditions.values())
    bearish_conditions = {
        "close_below_sma200": close < sma200,
        "sma50_below_sma200": sma50 < sma200,
        "sma50_falling_over_20_sessions": sma50 < prior_sma50,
        "negative_20_session_return": return_20d < 0,
    }
    bearish_count = sum(bearish_conditions.values())
    if bullish_count >= 4 and close > sma200:
        regime, exposure = "bullish", "normal"
        rationale = "Benchmark trend and momentum are broadly supportive."
    elif bearish_count >= 3 and close < sma200:
        regime, exposure = "bearish", "defensive"
        rationale = "Benchmark trend is weak; avoid forcing long setups."
    else:
        regime, exposure = "sideways", "selective"
        rationale = "Signals are mixed; require stronger individual-stock confirmation."
    return {
        "benchmark": symbol,
        "as_of": str(frame.index[-1].date()),
        "regime": regime,
        "suggested_exposure": exposure,
        "close": round(close, 2),
        "sma_50": round(sma50, 2),
        "sma_200": round(sma200, 2),
        "return_20_sessions_pct": round(return_20d, 2),
        "adx_14": round(adx, 2),
        "bullish_checks_passed": bullish_count,
        "bullish_checks_total": len(conditions),
        "bullish_checks": conditions,
        "bearish_checks": bearish_conditions,
        "rationale": rationale,
        "methodology": "Bullish: at least 4/5 bullish checks and close>SMA200. Bearish: at least 3/4 bearish checks and close<SMA200. Otherwise sideways.",
        "warning": "Heuristic market filter, not a forecast. Validate benchmark candles and ensure the latest daily candle is complete.",
    }
