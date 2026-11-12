from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class OHLCVBar(BaseModel):
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open, high, and close")
        return self


class IndicatorRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: Literal["1h", "4h", "1d"] = "1d"
    bars: list[OHLCVBar] = Field(min_length=2, max_length=2000)


class OHLCVImportRequest(BaseModel):
    """Validated OHLCV batch to persist in the local market-data store."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: Literal["1h", "4h", "1d"] = "1d"
    source: str = Field(default="manual", min_length=1, max_length=64)
    bars: list[OHLCVBar] = Field(min_length=1, max_length=10000)


class YahooBatchSyncRequest(BaseModel):
    """Bounded Yahoo Finance batch; omitted symbols means use the CSV universe."""

    symbols: list[str] | None = Field(default=None, max_length=50)
    timeframe: Literal["1h", "1d"] = "1d"
    period: str | None = None

    @model_validator(mode="after")
    def validate_unique_symbols(self):
        if self.symbols is not None:
            normalized = [symbol.strip().upper() for symbol in self.symbols]
            if any(not symbol for symbol in normalized):
                raise ValueError("Symbols cannot be blank")
            if len(normalized) != len(set(normalized)):
                raise ValueError("Symbols must be unique")
        return self


class RankingRequest(IndicatorRequest):
    """Optional context used by the 100-point stock ranking engine."""

    sector_relative_strength_pct: float | None = Field(
        default=None,
        description="Stock/sector relative return advantage in percentage points over a consistent lookback.",
    )
    average_daily_turnover: float | None = Field(
        default=None,
        ge=0,
        description="Average daily traded value in INR. If omitted, estimated from the last 20 daily close * volume values.",
    )


class UniverseScanRequest(BaseModel):
    """Batch scan up to 500 symbols using supplied daily OHLCV history."""

    candidates: list[RankingRequest] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_unique_symbols(self):
        symbols = [candidate.symbol.strip().upper() for candidate in self.candidates]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Candidate symbols must be unique")
        return self


class EODPipelineRequest(BaseModel):
    """Controls one manual end-of-day research pipeline run."""

    sync_market_data: bool = False
    shortlist_limit: int = Field(default=30, ge=1, le=100)

class BacktestRequest(BaseModel):
    """Run a bounded historical backtest for one setup and stored symbols."""

    symbols: list[str] = Field(min_length=1, max_length=50)
    setup: Literal["reversal", "vcp", "momentum"]
    target_pct: float = Field(default=5.0, gt=0, le=50)
    stop_atr_multiple: float = Field(default=1.5, gt=0, le=10)
    max_holding_sessions: int = Field(default=10, ge=1, le=30)
    cost_bps_per_side: float = Field(default=10.0, ge=0, le=500)

    @model_validator(mode="after")
    def validate_unique_symbols(self):
        normalized = [symbol.strip().upper() for symbol in self.symbols]
        if any(not symbol for symbol in normalized):
            raise ValueError("Symbols cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Symbols must be unique")
        return self


class PortfolioBacktestRequest(BaseModel):
    """Portfolio-level simulation settings for stored daily histories."""

    symbols: list[str] = Field(min_length=1, max_length=50)
    setup: Literal["reversal", "vcp", "momentum"]
    initial_capital: float = Field(default=1_000_000, gt=0)
    risk_per_trade_pct: float = Field(default=0.5, gt=0, le=5)
    max_positions: int = Field(default=5, ge=1, le=50)
    target_pct: float = Field(default=5.0, gt=0, le=50)
    stop_atr_multiple: float = Field(default=1.5, gt=0, le=10)
    max_holding_sessions: int = Field(default=10, ge=1, le=30)
    cost_bps_per_side: float = Field(default=10.0, ge=0, le=500)
    train_fraction: float = Field(default=0.7, ge=0.5, le=0.9)
    max_participation_pct: float = Field(
        default=1.0, gt=0, le=10,
        description="Maximum position notional as a percentage of 20-day average daily traded value.",
    )

    @model_validator(mode="after")
    def validate_unique_symbols(self):
        normalized = [symbol.strip().upper() for symbol in self.symbols]
        if any(not symbol for symbol in normalized):
            raise ValueError("Symbols cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Symbols must be unique")
        return self


class TradePlanRequest(BaseModel):
    """Conditional trade-plan settings for one stored daily symbol."""

    symbol: str = Field(min_length=1, max_length=32)
    setup: Literal["reversal", "vcp", "momentum"]
    capital: float = Field(default=1_000_000, gt=0)
    risk_per_trade_pct: float = Field(default=0.5, gt=0, le=5)
    max_allocation_pct: float = Field(default=20.0, gt=0, le=100)
    stop_atr_multiple: float = Field(default=1.5, gt=0, le=10)
