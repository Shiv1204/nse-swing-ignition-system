from fastapi import FastAPI, HTTPException

import pandas as pd

from backend.app.config import get_settings
from backend.app.indicators import calculate_indicators
from backend.app.schemas import IndicatorRequest

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Research and decision-support API for NSE swing-trading strategies. "
        "This service does not place live trades."
    ),
    version="0.1.0",
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "running",
        "environment": settings.app_env,
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/v1/indicators", tags=["research"])
def get_indicators(request: IndicatorRequest) -> dict:
    """Calculate baseline indicators for supplied OHLCV bars.

    This endpoint only calculates descriptive market indicators. It does not
    produce buy/sell instructions or submit broker orders.
    """
    bars = sorted(request.bars, key=lambda bar: bar.timestamp)
    if len({bar.timestamp for bar in bars}) != len(bars):
        raise HTTPException(status_code=422, detail="Duplicate bar timestamps are not allowed")

    frame = pd.DataFrame(
        [bar.model_dump(exclude={"timestamp"}) for bar in bars],
        index=pd.DatetimeIndex([bar.timestamp for bar in bars], name="timestamp"),
    )
    result = calculate_indicators(frame)
    latest = result.iloc[-1].replace({float("nan"): None})
    values = {
        key: (None if pd.isna(value) else float(value))
        for key, value in latest.items()
    }
    return {
        "symbol": request.symbol.upper(),
        "timeframe": request.timeframe,
        "bars_received": len(bars),
        "latest": values,
        "note": "Research indicators only; not a trading signal.",
    }
