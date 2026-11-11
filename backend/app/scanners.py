"""Explainable long-only swing setup scanners.

These rules are research filters, not investment recommendations. Inputs must
be chronological OHLCV frames with indicators calculated by indicators.py.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd

from backend.app.indicators import calculate_indicators


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    setup: str
    passed: bool
    score: int
    close: float
    reasons: tuple[str, ...]
    failed_conditions: tuple[str, ...]

    def to_dict(self) -> dict:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        result["failed_conditions"] = list(self.failed_conditions)
        return result


def _latest(frame: pd.DataFrame, column: str, offset: int = 0) -> float | None:
    position = len(frame) - 1 - offset
    if position < 0 or column not in frame:
        return None
    value = frame[column].iloc[position]
    return None if pd.isna(value) else float(value)


def _evaluate(symbol: str, setup: str, frame: pd.DataFrame,
              conditions: list[tuple[str, bool]], close: float) -> ScanResult:
    passed = [name for name, ok in conditions if ok]
    failed = [name for name, ok in conditions if not ok]
    score = round(100 * len(passed) / len(conditions)) if conditions else 0
    return ScanResult(
        symbol=symbol.upper(), setup=setup, passed=not failed, score=score,
        close=close, reasons=tuple(passed), failed_conditions=tuple(failed),
    )


def _prepare(symbol: str, data: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    if len(data) < 210:
        raise ValueError("At least 210 chronological bars are required for scanner warm-up")
    frame = calculate_indicators(data)
    close = _latest(frame, "close")
    if close is None or close <= 0:
        raise ValueError("Latest close must be a valid positive number")
    return frame, close


def scan_reversal(symbol: str, data: pd.DataFrame) -> ScanResult:
    """Daily trend-recovery filter. Intraday confirmation is a later stage."""
    frame, close = _prepare(symbol, data)
    prev_close = _latest(frame, "close", 1)
    ema20, ema50 = _latest(frame, "ema_20"), _latest(frame, "ema_50")
    ema20_5 = _latest(frame, "ema_20", 5)
    rsi_now, rsi_3 = _latest(frame, "rsi_14"), _latest(frame, "rsi_14", 3)
    volume_ratio = _latest(frame, "relative_volume_20")
    conditions = [
        ("close_above_ema20", ema20 is not None and close > ema20),
        ("ema20_above_ema50", ema20 is not None and ema50 is not None and ema20 > ema50),
        ("ema20_rising_5_bars", ema20 is not None and ema20_5 is not None and ema20 > ema20_5),
        ("rsi_45_to_65", rsi_now is not None and 45 <= rsi_now <= 65),
        ("rsi_rising_3_bars", rsi_now is not None and rsi_3 is not None and rsi_now > rsi_3),
        ("close_above_previous_close", prev_close is not None and close > prev_close),
        ("relative_volume_at_least_1_2", volume_ratio is not None and volume_ratio >= 1.2),
    ]
    return _evaluate(symbol, "reversal", frame, conditions, close)


def scan_vcp(symbol: str, data: pd.DataFrame) -> ScanResult:
    """Daily VCP candidate filter; contraction structure needs chart review."""
    frame, close = _prepare(symbol, data)
    sma50, sma150, sma200 = (_latest(frame, key) for key in ("sma_50", "sma_150", "sma_200"))
    sma200_20 = _latest(frame, "sma_200", 20)
    rsi_now = _latest(frame, "rsi_14")
    high55 = float(frame["high"].tail(55).max())
    high20 = float(frame["high"].tail(20).max())
    avg_vol5 = float(frame["volume"].tail(5).mean())
    avg_vol20 = float(frame["volume"].tail(20).mean())
    range10 = float(frame["high"].tail(10).max() - frame["low"].tail(10).min())
    conditions = [
        ("close_above_sma50", sma50 is not None and close > sma50),
        ("sma50_above_sma150", sma50 is not None and sma150 is not None and sma50 > sma150),
        ("sma150_above_sma200", sma150 is not None and sma200 is not None and sma150 > sma200),
        ("sma200_rising_20_bars", sma200 is not None and sma200_20 is not None and sma200 > sma200_20),
        ("rsi_above_50", rsi_now is not None and rsi_now > 50),
        ("within_15pct_of_55bar_high", close >= high55 * 0.85),
        ("within_7pct_below_20bar_high", high20 * 0.93 <= close <= high20),
        ("volume_dryup_5_vs_20", avg_vol5 < avg_vol20),
        ("10bar_range_below_12pct", range10 / close < 0.12),
    ]
    return _evaluate(symbol, "vcp_candidate", frame, conditions, close)


def scan_momentum(symbol: str, data: pd.DataFrame) -> ScanResult:
    """Daily momentum breakout filter; only completed bars should be supplied."""
    frame, close = _prepare(symbol, data)
    previous_high20 = float(frame["high"].iloc[-21:-1].max())
    ema20, sma50 = _latest(frame, "ema_20"), _latest(frame, "sma_50")
    rsi_now, adx_now = _latest(frame, "rsi_14"), _latest(frame, "adx")
    plus_di, minus_di = _latest(frame, "plus_di"), _latest(frame, "minus_di")
    volume_ratio = _latest(frame, "relative_volume_20")
    previous_close = _latest(frame, "close", 1)
    conditions = [
        ("close_above_prior_20bar_high", close > previous_high20),
        ("close_above_ema20", ema20 is not None and close > ema20),
        ("ema20_above_sma50", ema20 is not None and sma50 is not None and ema20 > sma50),
        ("rsi_55_to_72", rsi_now is not None and 55 <= rsi_now <= 72),
        ("adx_above_20", adx_now is not None and adx_now > 20),
        ("plus_di_above_minus_di", plus_di is not None and minus_di is not None and plus_di > minus_di),
        ("relative_volume_at_least_1_5", volume_ratio is not None and volume_ratio >= 1.5),
        ("not_extended_over_8pct", previous_close is not None and close < previous_close * 1.08),
    ]
    return _evaluate(symbol, "momentum_breakout", frame, conditions, close)


SCANNERS = {
    "reversal": scan_reversal,
    "vcp": scan_vcp,
    "momentum": scan_momentum,
}


def run_scanner(setup: Literal["reversal", "vcp", "momentum"],
                symbol: str, data: pd.DataFrame) -> ScanResult:
    return SCANNERS[setup](symbol, data)
