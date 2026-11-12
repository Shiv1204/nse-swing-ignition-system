"""Point-in-time market filter evaluation for historical candidate trades."""
from __future__ import annotations

import pandas as pd

from backend.app.market_breadth import calculate_market_breadth
from backend.app.market_intelligence import calculate_market_intelligence
from backend.app.market_regime import classify_market_regime
from backend.app.sector_strength import calculate_sector_strength
from backend.app.membership_history import members_on_date


def evaluate_historical_market_filter(
    trades: list[dict],
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    sector_by_symbol: dict[str, str],
    score_threshold: int = 65,
    minimum_completeness_pct: float = 80.0,
    membership_rows: list[dict] | None = None,
) -> dict:
    """Attach signal-date market scores; use no candle later than signal date."""
    cache: dict[str, dict] = {}
    evaluated, excluded = [], []
    for trade in trades:
        signal_date = str(pd.Timestamp(trade["signal_date"]).date())
        if signal_date not in cache:
            membership = members_on_date(membership_rows, signal_date) if membership_rows is not None else []
            expected_symbols = [row["symbol"] for row in membership] if membership_rows is not None else list(histories)
            aligned: dict[str, pd.DataFrame] = {}
            for symbol in expected_symbols:
                frame = histories.get(symbol)
                if frame is None:
                    continue
                history = frame.loc[frame.index.date <= pd.Timestamp(signal_date).date()]
                if len(history) and str(history.index[-1].date()) == signal_date:
                    aligned[symbol] = history
            benchmark_history = benchmark.loc[benchmark.index.date <= pd.Timestamp(signal_date).date()]
            regime = None
            if len(benchmark_history) >= 210 and str(benchmark_history.index[-1].date()) == signal_date:
                regime = classify_market_regime(benchmark_history)
            breadth = calculate_market_breadth(aligned, expected_symbols=expected_symbols)
            date_sector_map = {
                row["symbol"]: row.get("sector", "")
                for row in membership
                if row.get("sector")
            } if membership_rows is not None else sector_by_symbol
            constituents = [
                {"symbol": symbol, "sector": date_sector_map[symbol]}
                for symbol in aligned
                if symbol in date_sector_map
            ]
            has_sector_labels = any(
                row.get("sector") and row.get("sector") != "Unclassified"
                for row in constituents
            )
            sectors = (
                calculate_sector_strength(constituents, aligned, benchmark_history)
                if has_sector_labels and len(constituents) >= 2 and len(benchmark_history) >= 21
                and str(benchmark_history.index[-1].date()) == signal_date
                else None
            )
            snapshot = calculate_market_intelligence(regime, breadth, sectors)
            if breadth:
                snapshot["data_completeness_pct"] = min(snapshot["data_completeness_pct"], breadth["coverage_pct"])
            cache[signal_date] = snapshot
        intelligence = cache[signal_date]
        annotated = {**trade, "market_intelligence": intelligence}
        evaluated.append(annotated)
        if intelligence["score"] is None or intelligence["data_completeness_pct"] < minimum_completeness_pct:
            excluded.append({"symbol": trade["symbol"], "signal_date": signal_date, "reason": "insufficient_market_data", "score": intelligence["score"], "data_completeness_pct": intelligence["data_completeness_pct"]})
        elif intelligence["score"] < score_threshold:
            excluded.append({"symbol": trade["symbol"], "signal_date": signal_date, "reason": "below_market_score_threshold", "score": intelligence["score"], "data_completeness_pct": intelligence["data_completeness_pct"]})
    excluded_keys = {(item["symbol"], item["signal_date"]) for item in excluded}
    accepted = [trade for trade in evaluated if (trade["symbol"], str(pd.Timestamp(trade["signal_date"]).date())) not in excluded_keys]
    return {
        "trades": evaluated,
        "accepted_trades": accepted,
        "excluded_trades": excluded,
        "snapshots_calculated": len(cache),
        "score_threshold": score_threshold,
        "minimum_completeness_pct": minimum_completeness_pct,
        "warning": "Point-in-time membership is used when verified membership history is supplied. Breadth coverage is measured against expected members; missing price histories reduce completeness. Without membership history, selected backtest symbols are only a subset proxy.",
    }
