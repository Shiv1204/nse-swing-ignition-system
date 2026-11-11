import numpy as np
import pandas as pd
import pytest

from backend.app.scoring import WEIGHTS, rank_stock


def make_bars(rows: int = 260) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    close = 100 + np.arange(rows) * 0.25 + np.sin(np.arange(rows) / 4) * 0.5
    return pd.DataFrame({
        "open": close - 0.1,
        "high": close + 0.8,
        "low": close - 0.8,
        "close": close,
        "volume": np.full(rows, 200_000.0),
    }, index=index)


def test_weights_total_100() -> None:
    assert sum(WEIGHTS.values()) == 100


def test_ranking_returns_explainable_category_breakdown() -> None:
    result = rank_stock("test", make_bars(), sector_relative_strength_pct=2.0)
    assert result.symbol == "TEST"
    assert 0 <= result.score <= 100
    assert result.max_score == 100
    assert sum(result.category_scores.values()) == result.score
    assert result.data_completeness == 100
    assert result.unavailable_categories == ()
    assert "trend" in result.category_scores
    assert isinstance(result.reasons, tuple)


def test_missing_sector_data_is_explicit_and_not_assumed_positive() -> None:
    result = rank_stock("test", make_bars())
    assert result.category_scores["sector_relative_strength"] == 0
    assert "sector_relative_strength" in result.unavailable_categories
    assert result.data_completeness == 90


def test_ranking_rejects_insufficient_history() -> None:
    with pytest.raises(ValueError, match="At least 210"):
        rank_stock("short", make_bars(100))


def test_liquidity_can_be_supplied_explicitly() -> None:
    result = rank_stock("test", make_bars(), average_daily_turnover=150_000_000)
    assert result.category_scores["liquidity"] == 5
