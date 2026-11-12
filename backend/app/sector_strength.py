"""Sector-relative strength from stored constituent and Nifty daily histories."""
from __future__ import annotations

import pandas as pd


def _return_pct(frame: pd.DataFrame, lookback: int) -> float | None:
    if len(frame) <= lookback or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        return None
    start, end = float(frame["close"].iloc[-lookback - 1]), float(frame["close"].iloc[-1])
    if start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def calculate_sector_strength(
    constituents: list[dict],
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame | None,
    lookback: int = 20,
) -> dict:
    """Equal-weight mean constituent return by sector, less Nifty return.

    Uses only sectors with at least two usable constituents. This is a simple
    proxy, not an official sector-index return or investable index series.
    """
    benchmark_return = _return_pct(benchmark, lookback) if benchmark is not None else None
    members: dict[str, list[tuple[str, float]]] = {}
    excluded = 0
    for item in constituents:
        sector = (item.get("sector") or "").strip()
        symbol = item["symbol"].upper()
        frame = histories.get(symbol)
        value = _return_pct(frame, lookback) if frame is not None else None
        if not sector or value is None:
            excluded += 1
            continue
        members.setdefault(sector, []).append((symbol, value))

    sectors: dict[str, dict] = {}
    for sector, values in members.items():
        if len(values) < 2 or benchmark_return is None:
            continue
        average_return = sum(value for _, value in values) / len(values)
        sectors[sector] = {
            "constituents_used": len(values),
            "average_return_pct": round(average_return, 2),
            "nifty_return_pct": round(benchmark_return, 2),
            "relative_strength_pct": round(average_return - benchmark_return, 2),
            "leaders": [
                {"symbol": symbol, "return_pct": round(value, 2)}
                for symbol, value in sorted(values, key=lambda pair: pair[1], reverse=True)[:5]
            ],
        }
    return {
        "lookback_sessions": lookback,
        "benchmark_return_pct": round(benchmark_return, 2) if benchmark_return is not None else None,
        "sectors": sectors,
        "sectors_calculated": len(sectors),
        "constituents_excluded": excluded,
        "methodology": "Equal-weight average of available constituent close-to-close returns minus Nifty 50 return; minimum two constituents per sector.",
        "warning": "Sector proxy uses configured universe members, not official sector indices. Results are incomplete when histories or benchmark data are missing.",
    }
