from backend.app.portfolio_backtesting import simulate_portfolio


def test_indian_delivery_cost_model_is_applied_after_share_quantity():
    trades = [{
        "symbol": "AAA", "entry_date": "2025-01-02", "exit_date": "2025-01-03",
        "entry_price": 100.0, "exit_price": 110.0, "stop_price": 95.0,
        "gross_return_pct": 10.0, "net_return_pct": 10.0,
        "average_daily_turnover": 10000000, "cost_bps_per_side": 0,
    }]
    result = simulate_portfolio(
        trades, initial_capital=100000, risk_per_trade_pct=1,
        max_positions=1, cost_model="india_equity_delivery",
        delivery_cost_settings={"slippage_bps_each_side": 0},
    )
    position = result["trades"][0]
    assert position["transaction_costs"]["total_cost"] > 0
    assert position["net_return_pct"] < 10
    assert result["ending_capital"] < 110000
