"""Configurable Indian cash-equity delivery transaction-cost estimate."""
from __future__ import annotations


def estimate_delivery_costs(
    buy_value: float,
    sell_value: float,
    brokerage_pct: float = 0.0,
    brokerage_cap_per_order: float = 20.0,
    exchange_transaction_pct: float = 0.00307,
    stt_pct_each_side: float = 0.1,
    stamp_duty_pct_buy: float = 0.015,
    sebi_pct_each_side: float = 0.0001,
    gst_pct: float = 18.0,
    dp_charge_per_sell_order: float = 0.0,
    slippage_bps_each_side: float = 5.0,
) -> dict:
    """Estimate costs for one buy and one sell; rates are percentages unless named bps."""
    if min(buy_value, sell_value) < 0:
        raise ValueError("Trade values cannot be negative")
    rate_values = {
        "brokerage_pct": brokerage_pct,
        "brokerage_cap_per_order": brokerage_cap_per_order,
        "exchange_transaction_pct": exchange_transaction_pct,
        "stt_pct_each_side": stt_pct_each_side,
        "stamp_duty_pct_buy": stamp_duty_pct_buy,
        "sebi_pct_each_side": sebi_pct_each_side,
        "gst_pct": gst_pct,
        "dp_charge_per_sell_order": dp_charge_per_sell_order,
        "slippage_bps_each_side": slippage_bps_each_side,
    }
    if any(value < 0 for value in rate_values.values()):
        raise ValueError("Cost rates and charges cannot be negative")
    brokerage_buy = min(buy_value * brokerage_pct / 100, brokerage_cap_per_order)
    brokerage_sell = min(sell_value * brokerage_pct / 100, brokerage_cap_per_order)
    transaction = (buy_value + sell_value) * exchange_transaction_pct / 100
    stt = (buy_value + sell_value) * stt_pct_each_side / 100
    stamp = buy_value * stamp_duty_pct_buy / 100
    sebi = (buy_value + sell_value) * sebi_pct_each_side / 100
    gst = (brokerage_buy + brokerage_sell + transaction + sebi) * gst_pct / 100
    slippage = (buy_value + sell_value) * slippage_bps_each_side / 10000
    dp = dp_charge_per_sell_order
    components = {
        "brokerage": brokerage_buy + brokerage_sell,
        "exchange_transaction": transaction,
        "stt": stt,
        "stamp_duty": stamp,
        "sebi": sebi,
        "gst": gst,
        "dp": dp,
        "slippage": slippage,
    }
    return {
        "total_cost": round(sum(components.values()), 2),
        "components": {key: round(value, 2) for key, value in components.items()},
        "buy_value": round(buy_value, 2),
        "sell_value": round(sell_value, 2),
        "effective_cost_bps": round(sum(components.values()) / buy_value * 10000, 2) if buy_value else 0.0,
        "rate_inputs": rate_values,
        "assumptions": (
            "Illustrative NSE cash-equity delivery estimate. Statutory rate defaults are based on NSE's "
            "published levies page and the exchange transaction rate shown on Zerodha's public charges page "
            "as reviewed on 2026-11-12. Confirm the applicable rate, broker plan, exchange, trade date, "
            "rounding and per-order minimums before relying on this estimate. DP charge defaults to zero "
            "because it is broker-specific. Slippage is a configurable model assumption, not an exchange fee."
        ),
        "references": [
            "https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies",
            "https://zerodha.com/charges/",
        ],
    }
