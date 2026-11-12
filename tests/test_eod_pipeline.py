from datetime import datetime, timedelta, timezone

from backend.app.eod_pipeline import run_eod_pipeline
from backend.app.market_data import MarketDataStore
from backend.app.schemas import OHLCVBar


HEADER = "symbol,company_name,sector,exchange,valid_from,valid_to,source,as_of_date\n"
ROW = "RELIANCE,Reliance Industries,Energy,NSE,2026-01-01,,test-fixture,2026-11-10\n"


def make_bars(count: int = 220) -> list[OHLCVBar]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    bars = []
    for index in range(count):
        close = 100 + index * 0.2
        bars.append(OHLCVBar(
            timestamp=start + timedelta(days=index),
            open=close - 0.2,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=200_000,
        ))
    return bars


def test_eod_pipeline_ranks_stored_universe(tmp_path) -> None:
    universe_path = tmp_path / "nse500.csv"
    universe_path.write_text(HEADER + ROW, encoding="utf-8")
    store = MarketDataStore(tmp_path / "market.db")
    store.upsert_bars("RELIANCE", "1d", make_bars())

    result = run_eod_pipeline(
        store=store,
        universe_path=universe_path,
        sync_market_data=False,
    )

    assert result["universe_count"] == 1
    assert result["symbols_ranked"] == 1
    assert result["shortlist_count"] <= 1
    assert result["all_ranked"][0]["symbol"] == "RELIANCE"
    assert set(result["all_ranked"][0]["setups"]) == {"reversal", "vcp", "momentum"}


def test_eod_pipeline_reports_insufficient_history(tmp_path) -> None:
    universe_path = tmp_path / "nse500.csv"
    universe_path.write_text(HEADER + ROW, encoding="utf-8")
    store = MarketDataStore(tmp_path / "market.db")
    store.upsert_bars("RELIANCE", "1d", make_bars(50))

    result = run_eod_pipeline(
        store=store,
        universe_path=universe_path,
        sync_market_data=False,
    )

    assert result["symbols_ranked"] == 0
    assert result["symbols_without_usable_history"] == 1
    assert "210" in result["data_errors"][0]["error"]


def test_eod_pipeline_syncs_when_requested(tmp_path) -> None:
    universe_path = tmp_path / "nse500.csv"
    universe_path.write_text(HEADER + ROW, encoding="utf-8")
    store = MarketDataStore(tmp_path / "market.db")

    class FakeProvider:
        def fetch_bars(self, symbol, timeframe, period):
            assert symbol == "RELIANCE"
            assert timeframe == "1d"
            assert period == "5y"
            return make_bars()

    result = run_eod_pipeline(
        store=store,
        provider=FakeProvider(),
        universe_path=universe_path,
        sync_market_data=True,
    )

    assert result["symbols_synced"] == 1
    assert result["symbols_sync_failed"] == 0
    assert result["symbols_ranked"] == 1


def test_eod_pipeline_discloses_unavailable_market_regime(tmp_path) -> None:
    universe_path = tmp_path / "nse500.csv"
    universe_path.write_text(HEADER + ROW, encoding="utf-8")
    store = MarketDataStore(tmp_path / "market.db")
    store.upsert_bars("RELIANCE", "1d", make_bars())
    result = run_eod_pipeline(store=store, universe_path=universe_path)
    assert result["market_regime"] is None
    assert result["market_regime_filter"]["status"] == "unavailable"
    assert result["market_regime_filter"]["new_long_entries_blocked"] is False
