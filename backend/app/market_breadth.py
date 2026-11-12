"""Market breadth and participation statistics for the configured universe."""
from __future__ import annotations

import pandas as pd


def calculate_market_breadth(histories: dict[str, pd.DataFrame], lookback: int = 20) -> dict:
    """Calculate breadth from available daily histories; report coverage explicitly."""
    eligible = []
    above_20 = above_50 = above_200 = advances = declines = unchanged = new_highs = new_lows = 0
    for symbol, frame in histories.items():
        if len(frame) < 201 or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
            continue
        close = frame["close"].astype(float)
        latest = float(close.iloc[-1])
        sma20 = float(close.tail(20).mean())
        sma50 = float(close.tail(50).mean())
        sma200 = float(close.tail(200).mean())
        previous = float(close.iloc[-2])
        above_20 += latest > sma20
        above_50 += latest > sma50
        above_200 += latest > sma200
        advances += latest > previous
        declines += latest < previous
        unchanged += latest == previous
        prior = frame.iloc[-lookback-1:-1]
        new_highs += latest >= float(prior["high"].max())
        new_lows += latest <= float(prior["low"].min())
        eligible.append(symbol)
    total = len(eligible)
    def pct(value: int) -> float | None:
        return round(value / total * 100, 2) if total else None
    return {
        "as_of": max((str(histories[symbol].index[-1].date()) for symbol in eligible), default=None),
        "symbols_available": total,
        "symbols_with_history": len(histories),
        "coverage_pct": round(total / len(histories) * 100, 2) if histories else 0.0,
        "advances": advances, "declines": declines, "unchanged": unchanged,
        "advance_decline_ratio": round(advances / declines, 2) if declines else (None if not advances else "infinite"),
        "above_sma20": above_20, "above_sma20_pct": pct(above_20),
        "above_sma50": above_50, "above_sma50_pct": pct(above_50),
        "above_sma200": above_200, "above_sma200_pct": pct(above_200),
        "new_20_day_highs": new_highs, "new_20_day_lows": new_lows,
        "high_low_ratio": round(new_highs / new_lows, 2) if new_lows else (None if not new_highs else "infinite"),
        "methodology": "Equal-weight counts from available configured-universe members. 20-day highs/lows compare latest close with prior 20 sessions' high/low.",
        "warning": "Breadth is only as representative as the configured universe and synchronized histories. Different last candle dates can distort comparisons; verify coverage and dates.",
    }
