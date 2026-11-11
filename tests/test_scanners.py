from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.app.scanners import scan_momentum, scan_reversal, scan_vcp


def make_bars(rows: int = 260, drift: float = 0.25) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    close = 100 + np.arange(rows) * drift + np.sin(np.arange(rows) / 4) * 0.5
    return pd.DataFrame({
        "open": close - 0.1,
        "high": close + 0.8,
        "low": close - 0.8,
        "close": close,
        "volume": np.full(rows, 100_000.0),
    }, index=index)


def test_reversal_scanner_returns_explainable_result() -> None:
    result = scan_reversal("test", make_bars())
    assert result.setup == "reversal"
    assert result.symbol == "TEST"
    assert 0 <= result.score <= 100
    assert isinstance(result.reasons, tuple)
    assert isinstance(result.failed_conditions, tuple)
    assert result.passed == (len(result.failed_conditions) == 0)


def test_vcp_scanner_marks_candidate_setup() -> None:
    result = scan_vcp("test", make_bars())
    assert result.setup == "vcp_candidate"
    assert "close_above_sma50" in result.reasons or "close_above_sma50" in result.failed_conditions


def test_momentum_scanner_uses_prior_20_bar_high() -> None:
    data = make_bars()
    result = scan_momentum("test", data)
    assert result.setup == "momentum_breakout"
    assert "close_above_prior_20bar_high" in result.reasons or "close_above_prior_20bar_high" in result.failed_conditions


def test_scanners_reject_insufficient_history() -> None:
    with pytest.raises(ValueError, match="At least 210"):
        scan_reversal("short", make_bars(100))


def test_vcp_candidate_is_not_claimed_as_confirmed_pattern() -> None:
    result = scan_vcp("test", make_bars())
    assert result.setup == "vcp_candidate"
