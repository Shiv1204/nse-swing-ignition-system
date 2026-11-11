from datetime import datetime, timedelta, timezone

import pytest

from backend.app.market_data import MarketDataStore, import_ohlcv_csv
from backend.app.schemas import OHLCVBar


def make_bar(day: int, close: float = 101.0) -> OHLCVBar:
    return OHLCVBar(
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day),
        open=100.0,
        high=max(102.0, close),
        low=99.0,
        close=close,
        volume=1000,
    )


def test_store_inserts_updates_and_returns_chronological_bars(tmp_path) -> None:
    store = MarketDataStore(tmp_path / "market.db")
    first = store.upsert_bars("reliance", "1d", [make_bar(1), make_bar(0)])
    assert first == {"inserted": 2, "updated": 0}

    second = store.upsert_bars("RELIANCE", "1d", [make_bar(1, close=103.0)])
    assert second == {"inserted": 0, "updated": 1}

    bars = store.get_bars("reliance", "1d")
    assert len(bars) == 2
    assert bars[0]["timestamp"] < bars[1]["timestamp"]
    assert bars[1]["close"] == 103.0
    assert store.count_bars("RELIANCE", "1d") == 2


def test_store_rejects_duplicate_timestamps_in_one_import(tmp_path) -> None:
    store = MarketDataStore(tmp_path / "market.db")
    with pytest.raises(ValueError, match="Duplicate timestamps"):
        store.upsert_bars("RELIANCE", "1d", [make_bar(0), make_bar(0)])


def test_csv_import_validates_and_persists_rows(tmp_path) -> None:
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2025-01-01T00:00:00+00:00,100,102,99,101,1000\n",
        encoding="utf-8",
    )
    store = MarketDataStore(tmp_path / "market.db")
    result = import_ohlcv_csv(csv_path, "reliance", "1d", store)
    assert result == {"inserted": 1, "updated": 0}
    assert store.get_bars("RELIANCE", "1d")[0]["close"] == 101.0


def test_csv_import_rejects_missing_columns(tmp_path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("date,close\n2025-01-01,100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CSV must contain columns"):
        import_ohlcv_csv(csv_path, "RELIANCE", "1d", MarketDataStore(tmp_path / "market.db"))
