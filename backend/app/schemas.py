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
