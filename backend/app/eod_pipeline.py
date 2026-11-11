"""End-of-day research pipeline over the configured dated universe."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

from backend.app.market_data import MarketDataStore
from backend.app.scanners import run_scanner
from backend.app.scoring import rank_stock
from backend.app.universe import load_universe
from backend.app.yahoo_finance import YahooFinanceProvider


def run_eod_pipeline(
    store: MarketDataStore,
    provider: YahooFinanceProvider | None = None,
    universe_path: str | Path = "data/universe/nse500.csv",
    sync_market_data: bool = False,
    shortlist_limit: int = 30,
) -> dict:
    """Optionally sync daily bars, then rank and scan all configured constituents.

    Downloads are sequential and intentionally bounded in batches of 50.
    Sector-relative strength is not inferred when benchmark data is unavailable.
    """
    universe = load_universe(universe_path)
    symbols = [item["symbol"] for item in universe["constituents"]]
    provider = provider or YahooFinanceProvider()
    sync_results: list[dict] = []
    sync_errors: list[dict] = []

    if sync_market_data:
        for start in range(0, len(symbols), 50):
            for symbol in symbols[start:start + 50]:
                try:
                    bars = provider.fetch_bars(symbol, "1d", "5y")
                    counts = store.upsert_bars(
                        symbol, "1d", bars, source="yahoo_finance_adjusted"
                    )
                    sync_results.append({
                        "symbol": symbol,
                        "bars_received": len(bars),
                        **counts,
                    })
                except (ValueError, RuntimeError) as exc:
                    sync_errors.append({"symbol": symbol, "error": str(exc)})

    ranked: list[dict] = []
    data_errors: list[dict] = []
    for symbol in symbols:
        bars = store.get_bars(symbol, "1d", limit=1000)
        if len(bars) < 210:
            data_errors.append({
                "symbol": symbol,
                "bars_available": len(bars),
                "error": "Insufficient daily history; at least 210 bars required.",
            })
            continue

        try:
            frame = pd.DataFrame(
                [{key: bar[key] for key in ("open", "high", "low", "close", "volume")} for bar in bars],
                index=pd.DatetimeIndex([bar["timestamp"] for bar in bars], name="timestamp"),
            )
            # Fail closed on non-chronological or duplicate timestamps.
            if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
                raise ValueError("Stored candle timestamps are not strictly chronological.")
            ranking = rank_stock(symbol, frame)
            setups = {
                setup: run_scanner(setup, symbol, frame).to_dict()
                for setup in ("reversal", "vcp", "momentum")
            }
            passed = [name for name, result in setups.items() if result["passed"]]
            ranked.append({
                "symbol": symbol,
                "latest_bar": bars[-1]["timestamp"].isoformat(),
                "bars_available": len(bars),
                "ranking": ranking.to_dict(),
                "setups": setups,
                "passed_setups": passed,
            })
        except (ValueError, KeyError) as exc:
            data_errors.append({"symbol": symbol, "error": str(exc)})

    ranked.sort(
        key=lambda item: (
            item["ranking"]["score"],
            len(item["passed_setups"]),
        ),
        reverse=True,
    )
    for position, item in enumerate(ranked, start=1):
        item["rank_position"] = position

    shortlist = [
        item for item in ranked
        if item["ranking"]["score"] >= 60 and item["passed_setups"]
    ][:shortlist_limit]

    return {
        "universe_count": len(symbols),
        "universe_as_of_date": universe["as_of_date"],
        "universe_source": universe["source"],
        "sync_requested": sync_market_data,
        "symbols_synced": len(sync_results),
        "symbols_sync_failed": len(sync_errors),
        "sync_results": sync_results,
        "sync_errors": sync_errors,
        "symbols_ranked": len(ranked),
        "symbols_without_usable_history": len(data_errors),
        "data_errors": data_errors,
        "shortlist_count": len(shortlist),
        "shortlist": shortlist,
        "all_ranked": ranked,
        "notes": [
            "Research-only output; ranking scores are heuristic and are not probabilities of profit.",
            "Sector-relative-strength points are unavailable until benchmark/sector data is integrated.",
            "Only completed daily candles should be used; verify the latest candle timestamp before acting.",
            "Yahoo Finance is an unofficial data source and may throttle or omit symbols.",
            "No trade orders are placed by this pipeline.",
        ],
    }
