"""Rule-based trade planning calculations for research; never places orders."""
from __future__ import annotations

from typing import Literal

import pandas as pd

from backend.app.indicators import calculate_indicators
from backend.app.scanners import run_scanner


def build_trade_plan(
    symbol: str,
    data: pd.DataFrame,
    setup: Literal["reversal", "vcp", "momentum"],
    capital: float = 1_000_000,
    risk_per_trade_pct: float = 0.5,
    max_allocation_pct: float = 20.0,
    stop_atr_multiple: float = 1.5,
    hourly_data: pd.DataFrame | None = None,
) -> dict:
    """Build a conditional long plan from completed daily bars.

    Trigger levels use prior bars only. Stops sit below both the recent
    structural low and the ATR-based level, whichever is lower (wider risk).
    This is a planning reference, not a recommendation or execution signal.
    """
    if len(data) < 210:
        raise ValueError("At least 210 daily bars are required")
    if not data.index.is_monotonic_increasing or data.index.has_duplicates:
        raise ValueError("Daily bars must have unique chronological timestamps")
    if capital <= 0 or not 0 < risk_per_trade_pct <= 5:
        raise ValueError("Capital must be positive and risk_per_trade_pct must be >0 and <=5")
    if not 0 < max_allocation_pct <= 100 or not 0 < stop_atr_multiple <= 10:
        raise ValueError("Allocation must be >0 and <=100; stop ATR multiple must be >0 and <=10")

    frame = calculate_indicators(data)
    latest = frame.iloc[-1]
    close = float(latest["close"])
    atr = float(latest["atr_14"])
    if not pd.notna(atr) or atr <= 0:
        raise ValueError("ATR is unavailable for the latest daily candle")

    if setup == "reversal":
        pivot = float(frame["high"].iloc[-6:-1].max())
        trigger_basis = "highest high of prior 5 completed sessions"
    elif setup == "vcp":
        pivot = float(frame["high"].iloc[-56:-1].max())
        trigger_basis = "highest high of prior 55 completed sessions; VCP structure needs chart review"
    else:
        pivot = float(frame["high"].iloc[-21:-1].max())
        trigger_basis = "highest high of prior 20 completed sessions"

    entry = round(pivot * 1.001, 2)
    structural_low = float(frame["low"].tail(10).min())
    atr_stop = entry - stop_atr_multiple * atr
    stop = round(min(structural_low, atr_stop), 2)
    risk_per_share = round(entry - stop, 2)
    if risk_per_share <= 0:
        raise ValueError("Could not calculate a valid stop below the entry trigger")

    risk_budget = capital * risk_per_trade_pct / 100
    allocation_budget = capital * max_allocation_pct / 100
    risk_qty = int(risk_budget // risk_per_share)
    allocation_qty = int(allocation_budget // entry)
    quantity = max(0, min(risk_qty, allocation_qty))
    actual_risk = round(quantity * risk_per_share, 2)
    targets = {
        "target_1_1_5R": round(entry + 1.5 * risk_per_share, 2),
        "target_2_2R": round(entry + 2 * risk_per_share, 2),
        "target_3_3R": round(entry + 3 * risk_per_share, 2),
    }
    scan = run_scanner(setup, symbol, data)
    triggered = close >= entry
    hourly_confirmation = evaluate_hourly_confirmation(hourly_data)
    if triggered:
        status = "trigger_already_crossed"
    elif not scan.passed:
        status = "conditions_not_met"
    elif hourly_confirmation["status"] == "confirmed":
        status = "ready_to_watch"
    elif hourly_confirmation["status"] == "unavailable":
        status = "waiting_for_hourly_data"
    else:
        status = "hourly_confirmation_failed"
    return {
        "symbol": symbol.upper(),
        "setup": setup,
        "as_of": str(frame.index[-1].date()),
        "status": status,
        "scanner": scan.to_dict(),
        "hourly_confirmation": hourly_confirmation,
        "latest_close": round(close, 2),
        "entry_trigger": entry,
        "trigger_basis": trigger_basis,
        "trigger_distance_pct": round((entry / close - 1) * 100, 2),
        "stop_loss": stop,
        "stop_distance_pct": round((entry - stop) / entry * 100, 2),
        "risk_per_share": risk_per_share,
        "targets": targets,
        "reward_risk": {"target_1": 1.5, "target_2": 2.0, "target_3": 3.0},
        "sizing": {
            "capital": round(capital, 2),
            "risk_per_trade_pct": risk_per_trade_pct,
            "risk_budget": round(risk_budget, 2),
            "max_allocation_pct": max_allocation_pct,
            "quantity": quantity,
            "estimated_position_value": round(quantity * entry, 2),
            "estimated_risk": actual_risk,
            "risk_limited_quantity": risk_qty,
            "allocation_limited_quantity": allocation_qty,
        },
        "assumptions": [
            "Uses the latest stored daily candle; confirm it is complete before relying on this plan.",
            "Entry is a conditional stop-entry trigger, not a market order or guaranteed fill.",
            "Stop is the lower of the 10-session structural low and ATR-based stop, so risk may be wider.",
            "Targets are mathematical R-multiples; nearby resistance, gaps, slippage and taxes are not modeled.",
            "VCP output is only a candidate; contraction structure requires manual chart validation.",
            "Hourly confirmation uses completed 1-hour candles only; Yahoo hourly history is limited and may be delayed or incomplete.",
            "No broker connection or order placement is performed.",
        ],
    }


def evaluate_hourly_confirmation(data: pd.DataFrame | None) -> dict:
    """Evaluate short-term trend/momentum on stored hourly candles."""
    if data is None or data.empty:
        return {
            "status": "unavailable",
            "bars_available": 0 if data is None else len(data),
            "required_bars": 60,
            "passed": False,
            "checks": {},
            "failed_conditions": ["hourly_data_unavailable"],
            "note": "Sync hourly candles and rerun; daily setup alone is not multi-timeframe confirmation.",
        }
    if not data.index.is_monotonic_increasing or data.index.has_duplicates:
        raise ValueError("Hourly bars must have unique chronological timestamps")
    if len(data) < 60:
        return {
            "status": "unavailable",
            "bars_available": len(data),
            "required_bars": 60,
            "passed": False,
            "checks": {},
            "failed_conditions": ["insufficient_hourly_history"],
            "note": "At least 60 hourly candles are required for EMA50 and indicator warm-up.",
        }
    frame = calculate_indicators(data)
    latest = frame.iloc[-1]
    checks = {
        "hourly_close_above_ema20": bool(latest["close"] > latest["ema_20"]),
        "hourly_ema20_above_ema50": bool(latest["ema_20"] > latest["ema_50"]),
        "hourly_rsi_50_to_70": bool(50 <= latest["rsi_14"] <= 70),
        "hourly_macd_above_signal": bool(latest["macd"] > latest["signal"]),
        "hourly_plus_di_above_minus_di": bool(latest["plus_di"] > latest["minus_di"]),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "status": "confirmed" if not failed else "not_confirmed",
        "bars_available": len(frame),
        "required_bars": 60,
        "as_of": str(frame.index[-1]),
        "latest_close": round(float(latest["close"]), 2),
        "checks": checks,
        "failed_conditions": failed,
        "passed": not failed,
        "note": "All five hourly trend/momentum checks must pass. Supply completed hourly candles only.",
    }
