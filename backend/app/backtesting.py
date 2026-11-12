"""Event-driven, long-only daily-bar backtesting for scanner signals.

Signals use completed close t; entry is next session open. Stops/targets are
fixed at entry. If a daily bar touches both, stop is assumed first.
"""
from __future__ import annotations

from typing import Literal

import pandas as pd

from backend.app.indicators import calculate_indicators
from backend.app.scanners import run_scanner
from backend.app.scoring import rank_stock


def backtest_symbol(
    symbol: str,
    data: pd.DataFrame,
    setup: Literal["reversal", "vcp", "momentum"],
    target_pct: float = 5.0,
    stop_atr_multiple: float = 1.5,
    max_holding_sessions: int = 10,
    cost_bps_per_side: float = 10.0,
) -> dict:
    if not 0 < target_pct <= 50:
        raise ValueError("target_pct must be > 0 and <= 50")
    if stop_atr_multiple <= 0 or not 1 <= max_holding_sessions <= 30:
        raise ValueError("Stop multiple must be positive and holding period 1-30 sessions")
    if not 0 <= cost_bps_per_side <= 500:
        raise ValueError("cost_bps_per_side must be between 0 and 500")
    required = {"open", "high", "low", "close", "volume"}
    if required.difference(data.columns):
        raise ValueError("OHLCV data is missing required columns")
    if not data.index.is_monotonic_increasing or data.index.has_duplicates:
        raise ValueError("OHLCV index must be unique and chronological")
    if len(data) < 211:
        raise ValueError("At least 211 daily bars are required for next-session backtesting")

    frame = calculate_indicators(data)
    trades = []
    i = 209
    cost_rate = cost_bps_per_side / 10000.0
    while i < len(frame) - 1:
        history = data.iloc[: i + 1]
        signal = run_scanner(setup, symbol, history)
        atr_value = frame["atr_14"].iloc[i]
        if not signal.passed or pd.isna(atr_value) or atr_value <= 0:
            i += 1
            continue
        ranking = rank_stock(symbol, history)

        entry_i = i + 1
        entry = float(frame["open"].iloc[entry_i])
        stop = entry - stop_atr_multiple * float(atr_value)
        if stop <= 0 or stop >= entry:
            i += 1
            continue
        target = entry * (1 + target_pct / 100.0)
        exit_i = min(entry_i + max_holding_sessions - 1, len(frame) - 1)
        exit_price, exit_reason, actual_exit_i = float(frame["close"].iloc[exit_i]), "time", exit_i

        for j in range(entry_i, exit_i + 1):
            bar = frame.iloc[j]
            low, high, opening = float(bar["low"]), float(bar["high"]), float(bar["open"])
            if low <= stop:
                exit_price = opening if opening <= stop else stop
                exit_reason, actual_exit_i = "stop", j
                break
            if high >= target:
                exit_price, exit_reason, actual_exit_i = target, "target", j
                break

        gross_return = exit_price / entry - 1
        net_return = (exit_price * (1 - cost_rate)) / (entry * (1 + cost_rate)) - 1
        risk_fraction = (entry - stop) / entry
        mark_to_market = [
            {"date": str(frame.index[j]), "close": float(frame["close"].iloc[j])}
            for j in range(entry_i, actual_exit_i + 1)
        ]
        if mark_to_market:
            mark_to_market[-1] = {"date": str(frame.index[actual_exit_i]), "close": exit_price}
        average_daily_turnover = float(
            (data["close"].iloc[max(0, i - 19): i + 1] * data["volume"].iloc[max(0, i - 19): i + 1]).mean()
        )
        trades.append({
            "symbol": symbol.upper(),
            "setup": setup,
            "signal_date": str(frame.index[i]),
            "ranking_score": ranking.score,
            "ranking_band": ranking.rank_band,
            "ranking_data_completeness": ranking.data_completeness,
            "entry_date": str(frame.index[entry_i]),
            "exit_date": str(frame.index[actual_exit_i]),
            "entry_price": round(entry, 4),
            "exit_price": round(exit_price, 4),
            "stop_price": round(stop, 4),
            "target_price": round(target, 4),
            "exit_reason": exit_reason,
            "gross_return_pct": round(gross_return * 100, 4),
            "net_return_pct": round(net_return * 100, 4),
            "r_multiple": round(net_return / risk_fraction, 4),
            "holding_sessions": actual_exit_i - entry_i + 1,
            "average_daily_turnover": round(average_daily_turnover, 2),
            "cost_bps_per_side": cost_bps_per_side,
            "mark_to_market": mark_to_market,
        })
        i = actual_exit_i + 1

    return {"symbol": symbol.upper(), "setup": setup, "trades": trades, **summarize_trades(trades)}


def summarize_trades(trades: list[dict]) -> dict:
    if not trades:
        return {
            "trade_count": 0, "win_rate_pct": 0.0, "average_return_pct": 0.0,
            "average_r": 0.0, "profit_factor": 0.0, "expectancy_r": 0.0,
            "max_drawdown_pct": 0.0, "net_compounded_return_pct": 0.0,
        }
    returns = [t["net_return_pct"] / 100 for t in trades]
    rs = [t["r_multiple"] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    equity, peak, max_dd = 1.0, 1.0, 0.0
    for result in returns:
        equity *= 1 + result
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "trade_count": len(trades),
        "win_rate_pct": round(100 * len(wins) / len(trades), 2),
        "average_return_pct": round(100 * sum(returns) / len(returns), 4),
        "average_r": round(sum(rs) / len(rs), 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (999.0 if gross_profit else 0.0),
        "expectancy_r": round(sum(rs) / len(rs), 4),
        "max_drawdown_pct": round(max_dd * 100, 4),
        "net_compounded_return_pct": round((equity - 1) * 100, 4),
    }
