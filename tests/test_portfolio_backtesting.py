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
    assert len(split["train"]) == 2
    assert len(split["test"]) == 2
