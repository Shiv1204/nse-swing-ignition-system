from backend.app.market_intelligence import calculate_market_intelligence


def test_market_intelligence_scores_bullish_complete_snapshot():
    regime = {"regime": "bullish"}
    breadth = {
        "symbols_available": 450, "above_sma50_pct": 70, "above_sma200_pct": 60,
        "advances": 300, "declines": 100, "new_20_day_highs": 40, "new_20_day_lows": 10,
    }
    sectors = {"sectors": {"IT": {"relative_strength_pct": 2.0}, "BANK": {"relative_strength_pct": -1.0}}}
    result = calculate_market_intelligence(regime, breadth, sectors)
    assert result["score"] == 81
    assert result["status"] == "favorable"
    assert result["data_completeness_pct"] == 100


def test_market_intelligence_discloses_missing_inputs():
    result = calculate_market_intelligence(None, None, None)
    assert result["score"] is None
    assert result["status"] == "unavailable"
    assert result["data_completeness_pct"] == 0


def test_market_intelligence_does_not_overstate_thin_data():
    result = calculate_market_intelligence({"regime": "bullish"}, None, None)
    assert result["score"] == 100
    assert result["status"] == "insufficient_data"
    assert result["data_completeness_pct"] == 40
