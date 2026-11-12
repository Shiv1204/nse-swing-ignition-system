"""Read-only OHLCV store audit: provenance, coverage, and basic candle continuity."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path


def audit_market_data(database_path: str | Path, expected_symbols: list[str] | None = None, timeframe: str = "1d") -> dict:
    path = Path(database_path)
    if not path.exists():
        return {"status": "no_database", "database": str(path), "symbols": [], "issues": ["Market-data database does not exist."]}
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT symbol, timeframe, COUNT(*) AS bars, MIN(timestamp) AS first_bar,
                      MAX(timestamp) AS last_bar, COUNT(DISTINCT source) AS source_count,
                      GROUP_CONCAT(DISTINCT source) AS sources
               FROM ohlcv_bars WHERE timeframe=? GROUP BY symbol, timeframe ORDER BY symbol""",
            (timeframe,),
        ).fetchall()
        all_symbols = {row["symbol"] for row in rows}
        details = []
        issues = []
        for row in rows:
            sources = sorted((row["sources"] or "").split(","))
            item = {
                "symbol": row["symbol"], "timeframe": timeframe, "bars": row["bars"],
                "first_bar": row["first_bar"], "last_bar": row["last_bar"],
                "sources": sources, "mixed_sources": row["source_count"] > 1,
            }
            if row["source_count"] > 1:
                item["warning"] = "Multiple providers/adjustment conventions are present for this symbol; do not backtest until reconciled."
                issues.append({"symbol": row["symbol"], "type": "mixed_sources", "sources": sources})
            if row["bars"] < 210 and timeframe == "1d":
                issues.append({"symbol": row["symbol"], "type": "insufficient_history", "bars": row["bars"]})
            details.append(item)
    expected = sorted(set(s.upper() for s in (expected_symbols or [])))
    missing = sorted(set(expected) - all_symbols) if expected else []
    if missing:
        issues.append({"type": "missing_expected_symbols", "count": len(missing), "symbols": missing})
    return {
        "status": "issues_found" if issues else "clean_basic_checks",
        "database": str(path), "timeframe": timeframe,
        "symbols_stored": len(details), "expected_symbols": len(expected) if expected else None,
        "symbols_missing": len(missing), "missing_symbols": missing,
        "bars_total": sum(item["bars"] for item in details),
        "symbols_with_mixed_sources": sum(item["mixed_sources"] for item in details),
        "symbols": details, "issues": issues,
        "checks": ["stored row counts and date ranges", "source provenance consistency", "minimum 210 daily bars", "expected-symbol presence"],
        "limitations": [
            "A clean result is not proof of correct prices or corporate-action adjustment.",
            "Exchange holidays and symbol suspensions are not inferred; calendar-gap checks require an exchange calendar.",
            "This audit cannot establish provider licensing, data completeness, or historical index membership accuracy.",
            "SQLite upserts retain only the latest source label per candle; source mixing is detectable only when different sources coexist across timestamps.",
        ],
    }
