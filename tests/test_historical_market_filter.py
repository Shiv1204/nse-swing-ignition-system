import pandas as pd

from backend.app.historical_market_filter import evaluate_historical_market_filter


def rising_history(periods=230):
    close = [100 + i * 0.5 for i in range(periods)]
    index = pd.date_range("2025-01-01", periods=periods, freq="B")
    return pd.DataFrame({
        "open": close, "high": [x + 1 for x in close],
        "low": [x - 1 for x in close], "close": close,
        "volume": [100000] * periods,
    }, index=index)


def test_filter_uses_only_history_available_on_signal_date():
    first = rising_history()
    second = rising_history(231)
    signal_date = str(first.index[-1].date())
    trade = {
        "symbol": "AAA", "signal_date": signal_date, "entry_date": str(second.index[-1].date()),
        "exit_date": str(second.index[-1].date()), "entry_price": 200, "exit_price": 205,
        "stop_price": 195, "net_return_pct": 2.0, "r_multiple": 0.4,
    }
    result = evaluate_historical_market_filter(
        [trade], {"AAA": first, "BBB": first.copy()}, first,
        {"AAA": "IT", "BBB": "IT"}, score_threshold=65, minimum_completeness_pct=80,
    )
    assert result["snapshots_calculated"] == 1
    assert result["trades"][0]["market_intelligence"]["score"] is not None
    assert result["trades"][0]["market_intelligence"]["data_completeness_pct"] == 100
    assert len(result["accepted_trades"]) == 1

def test_filter_uses_point_in_time_members_and_penalizes_missing_histories(tmp_path):
    from backend.app.membership_history import load_membership_history
    membership_file = tmp_path / "members.csv"
    membership_file.write_text(
        "symbol,sector,valid_from,valid_to,source,as_of_date\n"
        "AAA,,2020-01-01,,press_release,2026-11-02\n"
        "BBB,,2020-01-01,,press_release,2026-11-02\n"
        "CCC,,2020-01-01,,press_release,2026-11-02\n",
        encoding="utf-8",
    )
    membership = load_membership_history(membership_file)
    history = rising_history()
    signal_date = str(history.index[-1].date())
    trade = {"symbol": "AAA", "signal_date": signal_date, "entry_date": signal_date, "exit_date": signal_date}
    result = evaluate_historical_market_filter(
        [trade], {"AAA": history, "BBB": history.copy()}, history, {},
        score_threshold=0, minimum_completeness_pct=80, membership_rows=membership,
    )
    intelligence = result["trades"][0]["market_intelligence"]
    assert intelligence["data_completeness_pct"] == 66.67
    assert result["excluded_trades"][0]["reason"] == "insufficient_market_data"
