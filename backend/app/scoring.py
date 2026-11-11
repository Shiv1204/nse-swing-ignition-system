"""Explainable 100-point ranking for daily long-only swing candidates.

Scores are heuristic research rankings, not probabilities of profit. Sector
strength requires an externally supplied benchmark-relative return. Liquidity
uses average daily traded value (close * volume) when not supplied.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from backend.app.indicators import calculate_indicators


WEIGHTS = {
    "trend": 20,
    "momentum": 15,
    "adx_di_strength": 10,
    "relative_volume": 15,
    "breakout_proximity": 15,
    "volatility_contraction": 10,
    "sector_relative_strength": 10,
    "liquidity": 5,
}


@dataclass(frozen=True)
class RankingResult:
    symbol: str
    score: int
    max_score: int
    category_scores: dict[str, int]
    category_max_scores: dict[str, int]
    data_completeness: int
    available_categories: tuple[str, ...]
    unavailable_categories: tuple[str, ...]
    reasons: tuple[str, ...]
    close: float
    average_daily_turnover: float | None
    sector_relative_strength_pct: float | None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["available_categories"] = list(self.available_categories)
        result["unavailable_categories"] = list(self.unavailable_categories)
        result["reasons"] = list(self.reasons)
        return result


def _number(frame: pd.DataFrame, column: str, offset: int = 0) -> float | None:
    pos = len(frame) - 1 - offset
    if pos < 0 or column not in frame:
        return None
    value = frame[column].iloc[pos]
    return None if pd.isna(value) else float(value)


def _score_trend(frame: pd.DataFrame, close: float) -> tuple[int, list[str]]:
    checks = [
        (close > (_number(frame, "sma_50") or float("inf")), 5, "price_above_sma50"),
        ((_number(frame, "sma_50") or 0) > (_number(frame, "sma_150") or float("inf")), 5, "sma50_above_sma150"),
        ((_number(frame, "sma_150") or 0) > (_number(frame, "sma_200") or float("inf")), 5, "sma150_above_sma200"),
        ((_number(frame, "sma_200") or 0) > (_number(frame, "sma_200", 20) or float("inf")), 5, "sma200_rising_20_sessions"),
    ]
    return sum(points for ok, points, _ in checks if ok), [name for ok, _, name in checks if ok]


def rank_stock(
    symbol: str,
    data: pd.DataFrame,
    *,
    sector_relative_strength_pct: float | None = None,
    average_daily_turnover: float | None = None,
) -> RankingResult:
    """Rank one stock from >=210 chronological daily OHLCV bars.

    sector_relative_strength_pct is the stock/sector relative return advantage
    over a chosen lookback, in percentage points. average_daily_turnover is INR.
    """
    if len(data) < 210:
        raise ValueError("At least 210 daily bars are required for ranking")
    if not data.index.is_monotonic_increasing:
        raise ValueError("OHLCV data must be ordered oldest to newest")
    if average_daily_turnover is not None and average_daily_turnover < 0:
        raise ValueError("average_daily_turnover cannot be negative")

    frame = calculate_indicators(data)
    close = _number(frame, "close")
    if close is None or close <= 0:
        raise ValueError("Latest close must be a valid positive number")

    scores: dict[str, int] = {}
    reasons: list[str] = []

    scores["trend"], hits = _score_trend(frame, close)
    reasons.extend(hits)

    rsi_now, rsi_prev = _number(frame, "rsi_14"), _number(frame, "rsi_14", 3)
    macd_hist = _number(frame, "histogram")
    momentum = 0
    if rsi_now is not None and 50 <= rsi_now <= 70:
        momentum += 5
        reasons.append("rsi_in_constructive_50_to_70_zone")
    if macd_hist is not None and macd_hist > 0:
        momentum += 5
        reasons.append("macd_histogram_positive")
    if rsi_now is not None and rsi_prev is not None and rsi_now > rsi_prev:
        momentum += 3
        reasons.append("rsi_rising")
    prev_close = _number(frame, "close", 1)
    if prev_close is not None and close > prev_close:
        momentum += 2
        reasons.append("close_above_previous_session")
    scores["momentum"] = momentum

    adx_now, plus_di, minus_di = (_number(frame, key) for key in ("adx", "plus_di", "minus_di"))
    adx_score = 0
    if adx_now is not None and adx_now >= 20:
        adx_score += 5
        reasons.append("adx_at_least_20")
    if plus_di is not None and minus_di is not None and plus_di > minus_di:
        adx_score += 5
        reasons.append("positive_di_dominant")
    scores["adx_di_strength"] = adx_score

    rvol = _number(frame, "relative_volume_20")
    if rvol is None:
        scores["relative_volume"] = 0
    elif rvol >= 1.5:
        scores["relative_volume"] = 15
        reasons.append("relative_volume_at_least_1_5")
    elif rvol >= 1.2:
        scores["relative_volume"] = 12
    elif rvol >= 1.0:
        scores["relative_volume"] = 8
    elif rvol >= 0.8:
        scores["relative_volume"] = 4
    else:
        scores["relative_volume"] = 0

    prior_high20 = float(frame["high"].iloc[-21:-1].max())
    distance_pct = (prior_high20 - close) / prior_high20 * 100 if prior_high20 else 100
    if close >= prior_high20:
        scores["breakout_proximity"] = 15
        reasons.append("at_or_above_prior_20_session_high")
    elif distance_pct <= 3:
        scores["breakout_proximity"] = 13
    elif distance_pct <= 5:
        scores["breakout_proximity"] = 10
    elif distance_pct <= 8:
        scores["breakout_proximity"] = 7
    elif distance_pct <= 12:
        scores["breakout_proximity"] = 3
    else:
        scores["breakout_proximity"] = 0

    atr_pct = frame["atr_14"] / frame["close"] * 100
    current_atr_pct = _number(pd.DataFrame({"atr_pct": atr_pct}), "atr_pct")
    baseline = float(atr_pct.iloc[-21:-1].median())
    if current_atr_pct is not None and baseline > 0:
        contraction = current_atr_pct / baseline
        scores["volatility_contraction"] = 10 if contraction <= 0.75 else 8 if contraction <= 0.9 else 5 if contraction <= 1.0 else 2 if contraction <= 1.1 else 0
        if contraction <= 0.9:
            reasons.append("atr_percent_contracting")
    else:
        scores["volatility_contraction"] = 0

    if sector_relative_strength_pct is None:
        scores["sector_relative_strength"] = 0
    elif sector_relative_strength_pct >= 3:
        scores["sector_relative_strength"] = 10
        reasons.append("sector_relative_strength_outperformance_3pct")
    elif sector_relative_strength_pct >= 1:
        scores["sector_relative_strength"] = 7
    elif sector_relative_strength_pct > 0:
        scores["sector_relative_strength"] = 4
    else:
        scores["sector_relative_strength"] = 0

    if average_daily_turnover is None:
        average_daily_turnover = float((frame["close"] * frame["volume"]).tail(20).mean())
    turnover_cr = average_daily_turnover / 10_000_000
    scores["liquidity"] = 5 if turnover_cr >= 10 else 4 if turnover_cr >= 5 else 3 if turnover_cr >= 2 else 2 if turnover_cr >= 1 else 0
    if scores["liquidity"] >= 3:
        reasons.append("average_daily_turnover_at_least_2cr")

    available = tuple(name for name in WEIGHTS if name != "sector_relative_strength" or sector_relative_strength_pct is not None)
    unavailable = tuple(name for name in WEIGHTS if name not in available)
    return RankingResult(
        symbol=symbol.upper(),
        score=sum(scores.values()),
        max_score=100,
        category_scores=scores,
        category_max_scores=WEIGHTS.copy(),
        data_completeness=round(sum(WEIGHTS[name] for name in available)),
        available_categories=available,
        unavailable_categories=unavailable,
        reasons=tuple(reasons),
        close=close,
        average_daily_turnover=average_daily_turnover,
        sector_relative_strength_pct=sector_relative_strength_pct,
    )
