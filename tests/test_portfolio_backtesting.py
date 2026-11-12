from backend.app.portfolio_backtesting import chronological_split, simulate_portfolio


def trade(symbol, entry_date, exit_date, ret=4.0, entry=100.0, stop=95.0):
    return {
        "symbol": symbol, "entry_date": entry_date, "exit_date": exit_date,
        "entry_price": entry, "stop_price": stop, "net_return_pct": ret,
    }


def test_position_sizing_respects_risk_and_capital():
    result = simulate_portfolio([
        trade("AAA", "2025-01-02", "2025-01-06"),
        trade("BBB", "2025-01-03", "2025-01-07", ret=-2),
    ], initial_capital=100000, risk_per_trade_pct=0.5, max_positions=5)
    assert result["trade_count"] == 2
    assert result["ending_capital"] > 0
    assert all(t["risk_amount"] <= t["risk_budget"] for t in result["trades"])


def test_max_positions_skips_excess_simultaneous_entries():
    candidates = [
        trade(f"S{i}", "2025-01-02", "2025-01-10")
        for i in range(7)
    ]
    result = simulate_portfolio(candidates, max_positions=5)
    assert result["trade_count"] == 5
    assert result["skipped"]["position_limit"] == 2


def test_chronological_train_test_split():
    candidates = [
        trade("A", "2025-01-02", "2025-01-05"),
        trade("B", "2025-01-03", "2025-01-06"),
        trade("C", "2025-01-04", "2025-01-07"),
        trade("D", "2025-01-05", "2025-01-08"),
    ]
    split = chronological_split(candidates, 0.5)
    assert split["split_date"] == "2025-01-04"
    assert len(split["train"]) == 0
    assert len(split["test"]) == 2
    assert split["boundary_trades_excluded"] == 2


def test_liquidity_cap_limits_position_size_and_daily_curve():
    candidate = trade("LIQ", "2025-01-02", "2025-01-04", ret=3.0)
    candidate["average_daily_turnover"] = 10000.0
    candidate["cost_bps_per_side"] = 10.0
    candidate["mark_to_market"] = [
        {"date": "2025-01-02", "close": 101.0},
        {"date": "2025-01-03", "close": 98.0},
        {"date": "2025-01-04", "close": 103.0},
    ]
    result = simulate_portfolio(
        [candidate], initial_capital=100000, risk_per_trade_pct=0.5,
        max_positions=5, max_participation_pct=1.0,
    )
    assert result["trades"][0]["quantity"] == 1
    assert len(result["equity_curve"]) == 3
    assert result["equity_curve"][1]["date"] == "2025-01-03"
    assert result["equity_curve"][1]["equity"] < result["equity_curve"][0]["equity"]


def test_liquidity_cap_skips_too_small_trade():
    candidate = trade("ILLIQ", "2025-01-02", "2025-01-04")
    candidate["average_daily_turnover"] = 100.0
    result = simulate_portfolio([candidate], max_participation_pct=1.0)
    assert result["trade_count"] == 0
    assert result["skipped"]["liquidity_limit"] == 1


def test_same_day_candidates_are_allocated_by_ranking_score():
    lower = trade("AAA", "2025-02-03", "2025-02-07")
    higher = trade("ZZZ", "2025-02-03", "2025-02-07")
    lower["ranking_score"] = 72
    higher["ranking_score"] = 91
    result = simulate_portfolio([lower, higher], max_positions=1)
    assert result["trade_count"] == 1
    assert result["trades"][0]["symbol"] == "ZZZ"
    assert result["same_day_allocation_priority"] == "ranking_score_descending_then_symbol"
