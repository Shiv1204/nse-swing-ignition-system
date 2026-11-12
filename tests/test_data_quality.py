from datetime import datetime, timezone
from backend.app.data_quality import audit_market_data
from backend.app.market_data import MarketDataStore
from backend.app.schemas import OHLCVBar


def test_audit_reports_missing_symbols_and_insufficient_history(tmp_path):
    store = MarketDataStore(tmp_path / "market.db")
    store.upsert_bars("AAA", "1d", [OHLCVBar(timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc), open=10, high=11, low=9, close=10, volume=100)], source="csv")
    result = audit_market_data(tmp_path / "market.db", expected_symbols=["AAA", "BBB"])
    assert result["symbols_stored"] == 1
    assert result["missing_symbols"] == ["BBB"]
    assert any(item["type"] == "insufficient_history" for item in result["issues"])
    assert result["status"] == "issues_found"


def test_audit_handles_missing_database(tmp_path):
    result = audit_market_data(tmp_path / "missing.db")
    assert result["status"] == "no_database"
