from backend.app.transaction_costs import estimate_delivery_costs


def test_delivery_costs_include_buy_sell_taxes_and_slippage():
    result = estimate_delivery_costs(100000, 105000)
    assert result["total_cost"] > 0
    assert result["components"]["stt"] > 0
    assert result["components"]["stamp_duty"] > 0
    assert result["components"]["slippage"] > 0
    assert result["effective_cost_bps"] > 0


def test_delivery_costs_support_broker_specific_dp_charge():
    without_dp = estimate_delivery_costs(10000, 11000)
    with_dp = estimate_delivery_costs(10000, 11000, dp_charge_per_sell_order=15.34)
    assert round(with_dp["total_cost"] - without_dp["total_cost"], 2) == 15.34
