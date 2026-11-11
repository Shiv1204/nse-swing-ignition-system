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


def test_ranking_endpoint_returns_100_point_breakdown() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for index in range(220):
        close = 100 + index * 0.2
        bars.append({
            "timestamp": (start + timedelta(days=index)).isoformat(),
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 200_000,
        })

    response = client.post("/api/v1/rank", json={
        "symbol": "reliance",
        "timeframe": "1d",
        "bars": bars,
        "sector_relative_strength_pct": 2.0,
    })

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "RELIANCE"
    assert body["max_score"] == 100
    assert body["data_completeness"] == 100
    assert sum(body["category_scores"].values()) == body["score"]
    assert "trend" in body["category_scores"]


def test_universe_scan_ranks_candidates_and_runs_all_setups() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for index in range(220):
        close = 100 + index * 0.2
        bars.append({
            "timestamp": (start + timedelta(days=index)).isoformat(),
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 200_000,
        })

    response = client.post("/api/v1/universe/scan", json={
        "candidates": [
            {"symbol": "RELIANCE", "timeframe": "1d", "bars": bars, "sector_relative_strength_pct": 2.0},
            {"symbol": "TCS", "timeframe": "1d", "bars": bars},
        ]
    })

    assert response.status_code == 200
    body = response.json()
    assert body["symbols_received"] == 2
    assert body["symbols_ranked"] == 2
    assert body["symbols_rejected"] == 0
    assert len(body["results"]) == 2
    assert body["results"][0]["rank_position"] == 1
    assert set(body["results"][0]["setups"]) == {"reversal", "vcp", "momentum"}


def test_universe_scan_rejects_duplicate_symbols() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for index in range(210):
        close = 100 + index * 0.2
        bars.append({
            "timestamp": (start + timedelta(days=index)).isoformat(),
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 200_000,
        })
    candidate = {"symbol": "RELIANCE", "timeframe": "1d", "bars": bars}
    response = client.post("/api/v1/universe/scan", json={
        "candidates": [candidate, candidate]
    })
    assert response.status_code == 422
