from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from backend.app.config import get_settings
from backend.app.backtesting import backtest_symbol
from backend.app.portfolio_backtesting import chronological_split, simulate_portfolio
from backend.app.historical_market_filter import evaluate_historical_market_filter
from backend.app.trade_planning import build_trade_plan
from backend.app.indicators import calculate_indicators
from backend.app.eod_pipeline import run_eod_pipeline
from backend.app.market_data import MarketDataStore
from backend.app.market_regime import classify_market_regime
from backend.app.scanners import run_scanner
from backend.app.scoring import rank_stock
from backend.app.universe import load_universe
from backend.app.yahoo_finance import YahooFinanceProvider
from backend.app.schemas import (
    BacktestRequest,
    PortfolioBacktestRequest,
    EODPipelineRequest,
    IndicatorRequest,
    OHLCVImportRequest,
    RankingRequest,
    UniverseScanRequest,
    YahooBatchSyncRequest,
    TradePlanRequest,
    MarketRegimeRequest,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
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




@app.post("/api/v1/market-data/sync/{symbol}", tags=["market-data"])
def sync_yahoo_market_data(
    symbol: str,
    timeframe: str = Query(default="1d", pattern="^(1h|1d)$"),
    period: str | None = Query(default=None),
) -> dict:
    """Fetch Yahoo Finance history and upsert it into local storage.

    Re-running this endpoint refreshes overlapping candles and adds new ones.
    Yahoo data is unofficial research data, not an exchange-grade live feed.
    """
    try:
        bars = YahooFinanceProvider().fetch_bars(symbol, timeframe, period)
        result = get_market_data_store().upsert_bars(
            symbol, timeframe, bars, source="yahoo_finance_adjusted"
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "symbol": symbol.upper(),
        "provider_symbol": YahooFinanceProvider.yahoo_symbol(symbol),
        "provider": "yahoo_finance",
        "timeframe": timeframe,
        "bars_received": len(bars),
        **result,
        "note": "Yahoo adjusted historical data is for research; verify quality and rights before operational use.",
    }




@app.get("/api/v1/universe", tags=["universe"])
def read_universe() -> dict:
    """Return the configured, provenance-checked constituent universe."""
    try:
        return load_universe()
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/market-data/sync-universe", tags=["market-data"])
def sync_yahoo_universe(request: YahooBatchSyncRequest) -> dict:
    """Sync at most 50 symbols per request to limit provider load and rate risk."""
    if request.symbols is None:
        try:
            constituents = load_universe()["constituents"]
            symbols = [item["symbol"] for item in constituents]
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        symbols = [symbol.strip().upper() for symbol in request.symbols]

    if not symbols:
        raise HTTPException(status_code=422, detail="At least one symbol is required.")
    if len(symbols) > 50:
        raise HTTPException(status_code=422, detail="Sync is limited to 50 symbols per request.")

    provider = YahooFinanceProvider()
    store = get_market_data_store()
    results = []
    errors = []
    for symbol in symbols:
        try:
            bars = provider.fetch_bars(symbol, request.timeframe, request.period)
            counts = store.upsert_bars(
                symbol, request.timeframe, bars, source="yahoo_finance_adjusted"
            )
            results.append({
                "symbol": symbol,
                "bars_received": len(bars),
                **counts,
            })
        except (ValueError, RuntimeError) as exc:
            errors.append({"symbol": symbol, "error": str(exc)})

    return {
        "provider": "yahoo_finance",
        "timeframe": request.timeframe,
        "symbols_requested": len(symbols),
        "symbols_synced": len(results),
        "symbols_failed": len(errors),
        "results": results,
        "errors": errors,
        "note": "Run in small batches. Yahoo is an unofficial research-data source; requests may be throttled or unavailable.",
    }




@app.post("/api/v1/pipeline/eod", tags=["pipeline"])
def run_end_of_day_pipeline(request: EODPipelineRequest) -> dict:
    """Run daily data checks, ranking, and setup scans for the configured universe."""
    try:
        return run_eod_pipeline(
            store=get_market_data_store(),
            sync_market_data=request.sync_market_data,
            shortlist_limit=request.shortlist_limit,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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



@app.post("/api/v1/market-regime", tags=["market-regime"])
def read_market_regime(request: MarketRegimeRequest) -> dict:
    """Optionally refresh Nifty 50 daily history, then classify market regime."""
    store = get_market_data_store()
    if request.sync_market_data:
        try:
            bars = YahooFinanceProvider().fetch_bars(request.benchmark, "1d", "5y")
            store.upsert_bars(request.benchmark, "1d", bars, source="yahoo_finance_adjusted")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Benchmark sync failed: {exc}") from exc
    bars = store.get_bars(request.benchmark, "1d", limit=1000)
    if not bars:
        raise HTTPException(status_code=404, detail="No benchmark history found. Sync benchmark daily data first.")
    frame = pd.DataFrame(
        [{key: bar[key] for key in ("open", "high", "low", "close", "volume")} for bar in bars],
        index=pd.DatetimeIndex([bar["timestamp"] for bar in bars], name="timestamp"),
    )
    try:
        return classify_market_regime(frame, request.benchmark)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/trade-plan", tags=["trade-planning"])
def create_trade_plan(request: TradePlanRequest) -> dict:
    """Build a conditional entry/stop/target/quantity plan from stored daily bars."""
    bars = get_market_data_store().get_bars(request.symbol, "1d", limit=1000)
    if not bars:
        raise HTTPException(status_code=404, detail="No stored daily candles; sync or import daily history first.")
    frame = pd.DataFrame(
        [{key: bar[key] for key in ("open", "high", "low", "close", "volume")} for bar in bars],
        index=pd.DatetimeIndex([bar["timestamp"] for bar in bars], name="timestamp"),
    )
    hourly_bars = get_market_data_store().get_bars(request.symbol, "1h", limit=500)
    hourly_frame = None
    if hourly_bars:
        hourly_frame = pd.DataFrame(
            [{key: bar[key] for key in ("open", "high", "low", "close", "volume")} for bar in hourly_bars],
            index=pd.DatetimeIndex([bar["timestamp"] for bar in hourly_bars], name="timestamp"),
        )
    try:
        return build_trade_plan(
            request.symbol, frame, request.setup,
            capital=request.capital,
            risk_per_trade_pct=request.risk_per_trade_pct,
            max_allocation_pct=request.max_allocation_pct,
            stop_atr_multiple=request.stop_atr_multiple,
            hourly_data=hourly_frame,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/backtest", tags=["backtesting"])
def run_historical_backtest(request: BacktestRequest) -> dict:
    """Backtest scanner signals against stored daily candles; no orders are placed."""
    store = get_market_data_store()
    results = []
    errors = []
    for symbol in request.symbols:
        try:
            bars = store.get_bars(symbol, "1d", limit=10000)
            if not bars:
                raise ValueError("No stored daily candles; import or sync history first.")
            frame = pd.DataFrame(
                [{key: bar[key] for key in ("open", "high", "low", "close", "volume")} for bar in bars],
                index=pd.DatetimeIndex([bar["timestamp"] for bar in bars], name="timestamp"),
            )
            results.append(backtest_symbol(
                symbol=symbol,
                data=frame,
                setup=request.setup,
                target_pct=request.target_pct,
                stop_atr_multiple=request.stop_atr_multiple,
                max_holding_sessions=request.max_holding_sessions,
                cost_bps_per_side=request.cost_bps_per_side,
            ))
        except (ValueError, KeyError) as exc:
            errors.append({"symbol": symbol.upper(), "error": str(exc)})

    trades = [trade for result in results for trade in result["trades"]]
    from backend.app.backtesting import summarize_trades
    return {
        "setup": request.setup,
        "symbols_requested": len(request.symbols),
        "symbols_backtested": len(results),
        "symbols_failed": len(errors),
        "parameters": {
            "target_pct": request.target_pct,
            "stop_atr_multiple": request.stop_atr_multiple,
            "max_holding_sessions": request.max_holding_sessions,
            "cost_bps_per_side": request.cost_bps_per_side,
            "entry_rule": "next session open after completed daily signal",
            "same_bar_stop_target_rule": "stop first (conservative)",
        },
        "aggregate": summarize_trades(trades),
        "results": results,
        "errors": errors,
        "warning": (
            "Research prototype, not validated performance. Results depend on adjusted OHLCV quality, "
            "survivorship-free historical universe membership, execution assumptions and costs. "
            "Signals are evaluated at close and entered next session open; no live orders are placed."
        ),
    }


@app.post("/api/v1/backtest/portfolio", tags=["backtesting"])
def run_portfolio_backtest(request: PortfolioBacktestRequest) -> dict:
    """Run capital-constrained portfolio simulation with chronological holdout."""
    store = get_market_data_store()
    candidate_trades = []
    errors = []
    histories = {}
    for symbol in request.symbols:
        try:
            bars = store.get_bars(symbol, "1d", limit=10000)
            if not bars:
                raise ValueError("No stored daily candles; import or sync history first.")
            frame = pd.DataFrame(
                [{key: bar[key] for key in ("open", "high", "low", "close", "volume")} for bar in bars],
                index=pd.DatetimeIndex([bar["timestamp"] for bar in bars], name="timestamp"),
            )
            histories[symbol.upper()] = frame
            result = backtest_symbol(
                symbol=symbol, data=frame, setup=request.setup,
                target_pct=request.target_pct,
                stop_atr_multiple=request.stop_atr_multiple,
                max_holding_sessions=request.max_holding_sessions,
                cost_bps_per_side=request.cost_bps_per_side,
            )
            candidate_trades.extend(result["trades"])
        except (ValueError, KeyError) as exc:
            errors.append({"symbol": symbol.upper(), "error": str(exc)})

    split = chronological_split(candidate_trades, request.train_fraction)
    settings_for_sim = {
        "initial_capital": request.initial_capital,
        "risk_per_trade_pct": request.risk_per_trade_pct,
        "max_positions": request.max_positions,
        "max_participation_pct": request.max_participation_pct,
    }
    train = simulate_portfolio(split["train"], **settings_for_sim)
    test = simulate_portfolio(split["test"], **settings_for_sim)

    filtered_comparison = {"status": "disabled"}
    if request.market_filter_enabled:
        benchmark_bars = store.get_bars("^NSEI", "1d", limit=10000)
        if benchmark_bars:
            benchmark_frame = pd.DataFrame(
                [{key: bar[key] for key in ("open", "high", "low", "close", "volume")} for bar in benchmark_bars],
                index=pd.DatetimeIndex([bar["timestamp"] for bar in benchmark_bars], name="timestamp"),
            )
            try:
                universe = load_universe()["constituents"]
                sector_by_symbol = {item["symbol"].upper(): item.get("sector", "Unclassified") for item in universe}
            except (ValueError, FileNotFoundError):
                sector_by_symbol = {}
            evaluation = evaluate_historical_market_filter(
                candidate_trades, histories, benchmark_frame, sector_by_symbol,
                score_threshold=request.market_score_threshold,
                minimum_completeness_pct=request.market_minimum_completeness_pct,
            )
            filtered_split = chronological_split(evaluation["accepted_trades"], request.train_fraction)
            filtered_comparison = {
                "status": "evaluated",
                "score_threshold": request.market_score_threshold,
                "minimum_completeness_pct": request.market_minimum_completeness_pct,
                "snapshots_calculated": evaluation["snapshots_calculated"],
                "trades_excluded": len(evaluation["excluded_trades"]),
                "exclusion_reasons": {
                    "insufficient_market_data": sum(x["reason"] == "insufficient_market_data" for x in evaluation["excluded_trades"]),
                    "below_market_score_threshold": sum(x["reason"] == "below_market_score_threshold" for x in evaluation["excluded_trades"]),
                },
                "train": simulate_portfolio(filtered_split["train"], **settings_for_sim),
                "out_of_sample": simulate_portfolio(filtered_split["test"], **settings_for_sim),
                "warning": evaluation["warning"],
            }
        else:
            filtered_comparison = {
                "status": "unavailable",
                "reason": "No stored ^NSEI daily benchmark history. Sync benchmark history before running the comparison.",
            }
    return {
        "setup": request.setup,
        "symbols_requested": len(request.symbols),
        "symbols_with_usable_history": len(request.symbols) - len(errors),
        "candidate_trades": len(candidate_trades),
        "split_date": split["split_date"],
        "train": train,
        "out_of_sample": test,
        "market_filter_comparison": filtered_comparison,
        "errors": errors,
        "parameters": {
            "initial_capital": request.initial_capital,
            "risk_per_trade_pct": request.risk_per_trade_pct,
            "max_positions": request.max_positions,
            "target_pct": request.target_pct,
            "stop_atr_multiple": request.stop_atr_multiple,
            "max_holding_sessions": request.max_holding_sessions,
            "cost_bps_per_side": request.cost_bps_per_side,
            "train_fraction": request.train_fraction,
            "max_participation_pct": request.max_participation_pct,
            "market_filter_enabled": request.market_filter_enabled,
            "market_score_threshold": request.market_score_threshold,
            "market_minimum_completeness_pct": request.market_minimum_completeness_pct,
            "liquidity_cap_basis": "position notional capped at configured percentage of 20-session average daily traded value before signal date",
            "entry_rule": "next session open after completed daily signal",
        },
        "warning": (
            "Prototype portfolio simulation. Candidate trades are generated independently per symbol "
            "before portfolio allocation. Same-day exits do not release capital for same-day new entries. "
            "Daily equity curve marks open positions using daily close prices; stop/target fills remain modeled "
            "by the single-symbol engine. Liquidity sizing is a coarse traded-value participation cap, not "
            "market-impact simulation. Costs remain a configurable flat basis-point assumption, not a "
            "complete India-specific tax/fee schedule. Corporate actions and point-in-time index membership "
            "are not fully modeled."
        ),
    }
