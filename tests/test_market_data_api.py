from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.market_data import MarketDataStore

client = TestClient(app)


def test_market_data_import_and_read_endpoints(tmp_path, monkeypatch) -> None:
    store = MarketDataStore(tmp_path / "api-market.db")
    monkeypatch.setattr("backend.app.main.get_market_data_store", lambda: store)

    payload = {
        "symbol": "reliance",
        "timeframe": "1d",
        "source": "test-fixture",
        "bars": [
            {
                "timestamp": datetime(2025, 1, 2, tzinfo=timezone.utc).isoformat(),
                "open": 101,
                "high": 103,
                "low": 100,
                "close": 102,
                "volume": 1200,
            },
            {
                "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                "open": 99,
                "high": 102,
                "low": 98,
                "close": 101,
                "volume": 1000,
            },
        ],
    }

    imported = client.post("/api/v1/market-data/import", json=payload)
    assert imported.status_code == 200
    assert imported.json()["symbol"] == "RELIANCE"
    assert imported.json()["inserted"] == 2
    assert imported.json()["updated"] == 0

    read = client.get("/api/v1/market-data/bars/RELIANCE?timeframe=1d&limit=10")
    assert read.status_code == 200
    body = read.json()
    assert body["bars_returned"] == 2
    assert body["bars"][0]["close"] == 101
    assert body["bars"][1]["close"] == 102


def test_market_data_import_rejects_duplicate_timestamps(tmp_path, monkeypatch) -> None:
    store = MarketDataStore(tmp_path / "api-market.db")
    monkeypatch.setattr("backend.app.main.get_market_data_store", lambda: store)
    bar = {
        "timestamp": "2025-01-01T00:00:00+00:00",
        "open": 100,
        "high": 102,
        "low": 99,
        "close": 101,
        "volume": 1000,
    }
    response = client.post("/api/v1/market-data/import", json={
        "symbol": "TCS",
        "timeframe": "1d",
        "bars": [bar, bar],
    })
    assert response.status_code == 422
