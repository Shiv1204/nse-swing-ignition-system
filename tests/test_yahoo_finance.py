from datetime import datetime, timezone

import pandas as pd
import pytest

from backend.app.yahoo_finance import YahooFinanceProvider


def fake_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    assert ticker == "RELIANCE.NS"
    assert period == "5y"
    assert interval == "1d"
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [103.0, 104.0],
            "Low": [99.0, 100.0],
            "Close": [102.0, 103.0],
            "Volume": [1000, 1200],
        },
        index=pd.DatetimeIndex(
            [
                datetime(2025, 1, 1, tzinfo=timezone.utc),
                datetime(2025, 1, 2, tzinfo=timezone.utc),
            ]
        ),
    )


def test_provider_maps_nse_symbol_and_normalizes_history() -> None:
    provider = YahooFinanceProvider(history_fetcher=fake_history)
    bars = provider.fetch_bars("reliance")

    assert len(bars) == 2
    assert bars[0].close == 102.0
    assert bars[1].volume == 1200
    assert bars[0].timestamp.tzinfo is not None


def test_provider_preserves_explicit_exchange_suffix() -> None:
    assert YahooFinanceProvider.yahoo_symbol("TCS.NS") == "TCS.NS"


def test_provider_rejects_unsupported_timeframe() -> None:
    provider = YahooFinanceProvider(history_fetcher=fake_history)
    with pytest.raises(ValueError, match="supports 1d and 1h"):
        provider.fetch_bars("RELIANCE", "4h")


def test_provider_rejects_empty_history() -> None:
    provider = YahooFinanceProvider(history_fetcher=lambda *_: pd.DataFrame())
    with pytest.raises(ValueError, match="No Yahoo Finance candles"):
        provider.fetch_bars("RELIANCE")
