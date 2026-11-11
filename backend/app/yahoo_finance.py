"""Yahoo Finance prototype provider.

This is an unofficial research-data adapter. It is not an exchange feed and
must not be treated as authoritative or guaranteed real-time market data.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

import pandas as pd

from backend.app.schemas import OHLCVBar


class YahooFinanceProvider:
    """Fetch adjusted OHLCV history from Yahoo Finance through yfinance."""

    def __init__(self, history_fetcher: Callable | None = None) -> None:
        # Injection keeps provider behavior testable without network access.
        self._history_fetcher = history_fetcher

    @staticmethod
    def yahoo_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Symbol cannot be blank")
        return normalized if "." in normalized else f"{normalized}.NS"

    def _fetch_history(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        if self._history_fetcher is not None:
            return self._history_fetcher(ticker, period, interval)
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError(
                "Yahoo Finance support requires yfinance. Install project requirements."
            ) from exc

        return yf.Ticker(ticker).history(
            period=period,
            interval=interval,
            auto_adjust=True,
            actions=False,
        )

    def fetch_bars(
        self, symbol: str, timeframe: str = "1d", period: str | None = None
    ) -> list[OHLCVBar]:
        if timeframe == "1d":
            interval = "1d"
            selected_period = period or "5y"
            allowed_periods = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
        elif timeframe == "1h":
            interval = "1h"
            selected_period = period or "60d"
            # Yahoo limits intraday history; use a conservative supported range.
            allowed_periods = {"1mo", "3mo", "6mo", "1y", "2y", "30d", "60d", "730d"}
        else:
            raise ValueError("Yahoo prototype supports 1d and 1h; 4h aggregation is not enabled.")

        if selected_period not in allowed_periods:
            raise ValueError(
                f"Unsupported period '{selected_period}' for {timeframe} data."
            )

        ticker = self.yahoo_symbol(symbol)
        frame = self._fetch_history(ticker, selected_period, interval)
        if frame is None or frame.empty:
            raise ValueError(f"No Yahoo Finance candles returned for {ticker} ({interval}).")

        # Ticker.history returns a single-ticker frame with standard OHLCV columns.
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(frame.columns):
            raise ValueError("Yahoo Finance response is missing required OHLCV columns.")

        bars: list[OHLCVBar] = []
        for timestamp, row in frame.iterrows():
            if pd.isna(row["Open"]) or pd.isna(row["High"]) or pd.isna(row["Low"]) or pd.isna(row["Close"]) or pd.isna(row["Volume"]):
                continue
            candle_time = timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp
            if not isinstance(candle_time, datetime):
                raise ValueError("Yahoo Finance returned an unsupported timestamp value.")
            bars.append(
                OHLCVBar(
                    timestamp=candle_time,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )

        if not bars:
            raise ValueError(f"No valid OHLCV candles returned for {ticker}.")
        return bars
