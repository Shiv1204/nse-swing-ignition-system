"""Capital-constrained portfolio simulation with daily mark-to-market equity."""
from __future__ import annotations

import math

from backend.app.transaction_costs import estimate_delivery_costs


def simulate_portfolio(
    trades: list[dict],
    initial_capital: float = 1_000_000.0,
    risk_per_trade_pct: float = 0.5,
    max_positions: int = 5,
    max_participation_pct: float = 1.0,
    cost_model: str = "flat_bps",
    delivery_cost_settings: dict | None = None,
) -> dict:
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    if not 0 < risk_per_trade_pct <= 5:
        raise ValueError("risk_per_trade_pct must be > 0 and <= 5")
    if not 1 <= max_positions <= 50:
        raise ValueError("max_positions must be between 1 and 50")
    if not 0 < max_participation_pct <= 10:
        raise ValueError("max_participation_pct must be > 0 and <= 10")
    if cost_model not in {"flat_bps", "india_equity_delivery"}:
        raise ValueError("Unsupported cost_model")

    ordered = sorted(trades, key=lambda t: (t["entry_date"], t["symbol"]))
    cash = float(initial_capital)
    active = []
    completed = []
    skipped = {
        "position_limit": 0, "insufficient_capital": 0,
        "invalid_risk": 0, "liquidity_limit": 0,
    }

    for candidate in ordered:
        entry_date = candidate["entry_date"]
        still_active = []
        for position in active:
            if position["exit_date"] < entry_date:
                cash += position["deployed"] * (1 + position["net_return_pct"] / 100)
                completed.append(position)
            else:
                still_active.append(position)
        active = still_active

        if len(active) >= max_positions:
            skipped["position_limit"] += 1
            continue

        entry = float(candidate["entry_price"])
        stop = float(candidate["stop_price"])
        risk_per_share = entry - stop
        if risk_per_share <= 0:
            skipped["invalid_risk"] += 1
            continue
        equity = cash + sum(p["deployed"] for p in active)
        risk_budget = equity * risk_per_trade_pct / 100
        qty_by_risk = math.floor(risk_budget / risk_per_share)
        qty_by_cash = math.floor(cash / entry)
        quantity = min(qty_by_risk, qty_by_cash)

        turnover = candidate.get("average_daily_turnover")
        if turnover is not None:
            liquidity_value_cap = float(turnover) * max_participation_pct / 100
            qty_by_liquidity = math.floor(liquidity_value_cap / entry)
            if qty_by_liquidity < 1:
                skipped["liquidity_limit"] += 1
                continue
            quantity = min(quantity, qty_by_liquidity)

        if quantity < 1:
            skipped["insufficient_capital"] += 1
            continue
        deployed = quantity * entry
        net_return_pct = float(candidate["net_return_pct"])
        cost_breakdown = None
        if cost_model == "india_equity_delivery":
            gross_return_pct = float(candidate.get("gross_return_pct", candidate["net_return_pct"]))
            sell_value = quantity * float(candidate["exit_price"])
            cost_breakdown = estimate_delivery_costs(
                deployed, sell_value, **(delivery_cost_settings or {})
            )
            net_return_pct = (sell_value - deployed - cost_breakdown["total_cost"]) / deployed * 100
        cash -= deployed
        active.append({
            **candidate,
            "net_return_pct": round(net_return_pct, 6),
            "quantity": quantity,
            "deployed": deployed,
            "risk_budget": risk_budget,
            "risk_amount": quantity * risk_per_share,
            "transaction_costs": cost_breakdown,
        })

    for position in active:
        cash += position["deployed"] * (1 + position["net_return_pct"] / 100)
        completed.append(position)

    pnl = cash - initial_capital
    winners = [p for p in completed if p["net_return_pct"] > 0]
    losses = [p for p in completed if p["net_return_pct"] < 0]
    gross_win = sum(p["deployed"] * p["net_return_pct"] / 100 for p in winners)
    gross_loss = abs(sum(p["deployed"] * p["net_return_pct"] / 100 for p in losses))

    # Daily equity is cash plus unrealized P&L on positions open at each close.
    dates = sorted({
        mark["date"]
        for position in completed
        for mark in position.get("mark_to_market", [])
    } | {
        position["entry_date"] for position in completed
    } | {
        position["exit_date"] for position in completed
    })
    equity_curve = []
    peak = float(initial_capital)
    max_drawdown = 0.0
    for date in dates:
        equity = float(initial_capital)
        for position in completed:
            if position["exit_date"] <= date:
                equity += position["deployed"] * position["net_return_pct"] / 100
            elif position["entry_date"] <= date:
                marks = [m for m in position.get("mark_to_market", []) if m["date"] <= date]
                mark_price = float(marks[-1]["close"]) if marks else float(position["entry_price"])
                cost_rate = float(position.get("cost_bps_per_side", 10.0)) / 10000
                marked_return = (
                    (mark_price * (1 - cost_rate)) /
                    (float(position["entry_price"]) * (1 + cost_rate)) - 1
                )
                equity += position["deployed"] * marked_return
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0.0)
        equity_curve.append({
            "date": date,
            "equity": round(equity, 2),
            "drawdown_pct": round((peak - equity) / peak * 100 if peak else 0.0, 4),
        })

    return {
        "initial_capital": round(initial_capital, 2),
        "ending_capital": round(cash, 2),
        "net_profit": round(pnl, 2),
        "net_return_pct": round(pnl / initial_capital * 100, 4),
        "trade_count": len(completed),
        "win_rate_pct": round(100 * len(winners) / len(completed), 2) if completed else 0.0,
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss else (999.0 if gross_win else 0.0),
        "max_drawdown_pct": round(max_drawdown * 100, 4),
        "max_positions": max_positions,
        "risk_per_trade_pct": risk_per_trade_pct,
        "max_participation_pct": max_participation_pct,
        "skipped": skipped,
        "equity_curve": equity_curve,
        "trades": completed,
    }


def chronological_split(trades: list[dict], train_fraction: float = 0.7) -> dict:
    if not 0.5 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be between 0.5 and 0.9")
    dates = sorted({trade["entry_date"] for trade in trades})
    if len(dates) < 2:
        return {
            "split_date": None, "train": trades, "test": [],
            "boundary_trades_excluded": 0,
        }
    split_index = min(max(1, int(len(dates) * train_fraction)), len(dates) - 1)
    split_date = dates[split_index]
    train = [t for t in trades if t["entry_date"] < split_date and t["exit_date"] < split_date]
    test = [t for t in trades if t["entry_date"] >= split_date]
    excluded = len(trades) - len(train) - len(test)
    return {
        "split_date": split_date,
        "train": train,
        "test": test,
        "boundary_trades_excluded": excluded,
    }
