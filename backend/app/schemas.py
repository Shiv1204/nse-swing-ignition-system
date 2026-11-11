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
            raise ValueError("low must be <= open, close, and high")
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
