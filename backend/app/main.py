from fastapi import FastAPI, HTTPException, Query
import pandas as pd

from backend.app.config import get_settings
from backend.app.indicators import calculate_indicators
from backend.app.market_data import MarketDataStore
from backend.app.scanners import run_scanner
from backend.app.scoring import rank_stock
from backend.app.schemas import (
    IndicatorRequest,
    OHLCVImportRequest,
    RankingRequest,
    UniverseScanRequest,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Research and decision-support API for NSE swing-trading strategies. "
        "This service does not place live trades."
    ),
    version="0.1.0",
)


def get_market_data_store() -> MarketDataStore:
    """Create a lightweight repository handle using the configured database path."""
    return MarketDataStore(settings.database_path)


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


@app.post("/api/v1/market-data/import", tags=["market-data"])
def import_market_data(request: OHLCVImportRequest) -> dict:
    """Persist validated OHLCV bars; repeated timestamps are updated idempotently."""
    try:
        result = get_market_data_store().upsert_bars(
            request.symbol, request.timeframe, request.bars, source=request.source
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "symbol": request.symbol.upper(),
        "timeframe": request.timeframe,
        "bars_received": len(request.bars),
        **result,
    }


@app.get("/api/v1/market-data/bars/{symbol}", tags=["market-data"])
def read_market_data(
    symbol: str,
    timeframe: str = Query(default="1d", pattern="^(1h|4h|1d)$"),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> dict:
    """Return the most recent stored candles in chronological order."""
    store = get_market_data_store()
    bars = store.get_bars(symbol, timeframe, limit=limit)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "bars_returned": len(bars),
        "bars": bars,
    }


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


@app.post("/api/v1/rank", tags=["research"])
def rank_candidate(request: RankingRequest) -> dict:
    """Return an explainable 100-point daily stock ranking."""
    if request.timeframe != "1d":
        raise HTTPException(status_code=422, detail="Initial ranking rules require daily bars.")
    frame = _bars_to_frame(request)
    try:
        result = rank_stock(
            request.symbol,
            frame,
            sector_relative_strength_pct=request.sector_relative_strength_pct,
            average_daily_turnover=request.average_daily_turnover,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


@app.post("/api/v1/universe/scan", tags=["research"])
def scan_universe(request: UniverseScanRequest) -> dict:
    """Rank a supplied stock universe and evaluate all three daily setups."""
    ranked = []
    errors = []
    for candidate in request.candidates:
        if candidate.timeframe != "1d":
            errors.append({"symbol": candidate.symbol.upper(), "error": "Daily bars are required."})
            continue
        try:
            frame = _bars_to_frame(candidate)
            ranking = rank_stock(
                candidate.symbol,
                frame,
                sector_relative_strength_pct=candidate.sector_relative_strength_pct,
                average_daily_turnover=candidate.average_daily_turnover,
            )
            setup_results = {
                setup: run_scanner(setup, candidate.symbol, frame).to_dict()
                for setup in ("reversal", "vcp", "momentum")
            }
            ranked.append({
                "symbol": candidate.symbol.upper(),
                "ranking": ranking.to_dict(),
                "setups": setup_results,
                "passed_setups": [
                    setup for setup, result in setup_results.items() if result["passed"]
                ],
            })
        except (ValueError, HTTPException) as exc:
            errors.append({
                "symbol": candidate.symbol.upper(),
                "error": exc.detail if isinstance(exc, HTTPException) else str(exc),
            })

    ranked.sort(key=lambda item: item["ranking"]["score"], reverse=True)
    for position, item in enumerate(ranked, start=1):
        item["rank_position"] = position

    return {
        "symbols_received": len(request.candidates),
        "symbols_ranked": len(ranked),
        "symbols_rejected": len(errors),
        "results": ranked,
        "errors": errors,
        "note": (
            "Heuristic research ranking only. Results depend on supplied completed "
            "daily bars; scores are not probabilities of profit or trade instructions."
        ),
    }
