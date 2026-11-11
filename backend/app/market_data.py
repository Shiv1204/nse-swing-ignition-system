"""Provider-neutral OHLCV persistence and CSV ingestion.

CSV columns: timestamp,open,high,low,close,volume
Timestamps must be ISO-8601. Symbols and timeframe are supplied separately.
This module deliberately does not download data or assume a licensed provider.
"""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from backend.app.schemas import OHLCVBar


class MarketDataStore:
    """Small SQLite repository for normalized OHLCV candles."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ohlcv_bars (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL CHECK(open > 0),
                    high REAL NOT NULL CHECK(high > 0),
                    low REAL NOT NULL CHECK(low > 0),
                    close REAL NOT NULL CHECK(close > 0),
                    volume REAL NOT NULL CHECK(volume >= 0),
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, timeframe, timestamp),
                    CHECK(high >= open AND high >= low AND high >= close),
                    CHECK(low <= open AND low <= high AND low <= close)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time "
                "ON ohlcv_bars(symbol, timeframe, timestamp)"
            )

    def upsert_bars(
        self,
        symbol: str,
        timeframe: str,
        bars: Iterable[OHLCVBar],
        source: str = "manual",
    ) -> dict[str, int]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("Symbol cannot be blank")
        materialized = list(bars)
        timestamps = [bar.timestamp.isoformat() for bar in materialized]
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("Duplicate timestamps are not allowed in one import")

        inserted = updated = 0
        with self._connect() as connection:
            for bar in materialized:
                timestamp = bar.timestamp.isoformat()
                exists = connection.execute(
                    "SELECT 1 FROM ohlcv_bars WHERE symbol=? AND timeframe=? AND timestamp=?",
                    (normalized_symbol, timeframe, timestamp),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO ohlcv_bars
                    (symbol, timeframe, timestamp, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timeframe, timestamp) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume,
                        source=excluded.source, updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        normalized_symbol, timeframe, timestamp, bar.open, bar.high,
                        bar.low, bar.close, bar.volume, source,
                    ),
                )
                if exists:
                    updated += 1
                else:
                    inserted += 1
        return {"inserted": inserted, "updated": updated}

    def get_bars(
        self, symbol: str, timeframe: str, limit: int = 1000
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, open, high, low, close, volume
                FROM (
                    SELECT timestamp, open, high, low, close, volume
                    FROM ohlcv_bars
                    WHERE symbol=? AND timeframe=?
                    ORDER BY timestamp DESC LIMIT ?
                )
                ORDER BY timestamp ASC
                """,
                (symbol.strip().upper(), timeframe, limit),
            ).fetchall()
        return [
            {
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }
            for row in rows
        ]

    def count_bars(self, symbol: str, timeframe: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM ohlcv_bars WHERE symbol=? AND timeframe=?",
                (symbol.strip().upper(), timeframe),
            ).fetchone()
        return int(row["total"])


def import_ohlcv_csv(
    csv_path: str | Path,
    symbol: str,
    timeframe: str,
    store: MarketDataStore,
    source: str = "csv",
) -> dict[str, int]:
    """Validate and import a CSV with timestamp,open,high,low,close,volume columns."""
    bars: list[OHLCVBar] = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must contain columns: {', '.join(sorted(required))}")
        for line_number, row in enumerate(reader, start=2):
            try:
                bars.append(
                    OHLCVBar(
                        timestamp=datetime.fromisoformat(row["timestamp"].strip().replace("Z", "+00:00")),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"Invalid OHLCV data on CSV line {line_number}: {exc}") from exc
    if not bars:
        raise ValueError("CSV contains no OHLCV rows")
    return store.upsert_bars(symbol, timeframe, bars, source=source)
