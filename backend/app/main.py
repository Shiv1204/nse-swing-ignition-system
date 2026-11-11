from fastapi import FastAPI, HTTPException
import pandas as pd

from backend.app.config import get_settings
from backend.app.indicators import calculate_indicators
from backend.app.scanners import run_scanner
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


def _bars_to_frame(request: IndicatorRequest) -> pd.DataFrame:
    bars = sorted(request.bars, key=lambda bar: bar.timestamp)
    if len({bar.timestamp for bar in bars}) != len(bars):
        raise HTTPException(status_code=422, detail="Duplicate bar timestamps are not allowed")
    return pd.DataFrame(
        [bar.model_dump(exclude={"timestamp"}) for bar in bars],
        index=pd.DatetimeIndex([bar.timestamp for bar in bars], name="timestamp"),
    )


@app.post("/api/v1/indicators", tags=["research"])
def get_indicators(request: IndicatorRequest) -> dict:
    """Calculate descriptive indicators; this is not a trading signal."""
    frame = _bars_to_frame(request)
    result = calculate_indicators(frame)
    latest = result.iloc[-1]
    values = {key: (None if pd.isna(value) else float(value)) for key, value in latest.items()}
    return {
        "symbol": request.symbol.upper(),
        "timeframe": request.timeframe,
        "bars_received": len(request.bars),
        "latest": values,
        "note": "Research indicators only; not a trading signal.",
    }


@app.post("/api/v1/scans/{setup}", tags=["research"])
def scan_setup(setup: str, request: IndicatorRequest) -> dict:
    """Evaluate one daily setup against supplied OHLCV bars.

    Scanner scores are condition-completion percentages, not probabilities
    of profit. Multi-timeframe confirmations and liquidity filters are not
    yet included.
    """
    if setup not in {"reversal", "vcp", "momentum"}:
        raise HTTPException(status_code=404, detail="Unknown setup. Use reversal, vcp, or momentum.")
    if request.timeframe != "1d":
        raise HTTPException(status_code=422, detail="Initial scanner rules require daily bars.")
    frame = _bars_to_frame(request)
    try:
        result = run_scanner(setup, request.symbol, frame)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()
