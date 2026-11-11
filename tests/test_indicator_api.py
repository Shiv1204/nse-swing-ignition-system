from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_indicator_endpoint_calculates_values_for_supplied_bars() -> None:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    bars = []
    for index in range(40):
        close = 100 + index
        bars.append({
            "timestamp": (start + timedelta(days=index)).isoformat(),
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 100_000,
        })

    response = client.post("/api/v1/indicators", json={
        "symbol": "reliance",
        "timeframe": "1d",
        "bars": bars,
    })

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "RELIANCE"
    assert body["bars_received"] == 40
    assert body["latest"]["rsi_14"] == 100.0
    assert "atr_14" in body["latest"]
    assert "not a trading signal" in body["note"]


def test_indicator_endpoint_rejects_invalid_timeframe() -> None:
    response = client.post("/api/v1/indicators", json={
        "symbol": "RELIANCE",
        "timeframe": "15m",
        "bars": [],
    })
    assert response.status_code == 422
