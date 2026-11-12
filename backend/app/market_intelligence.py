"""Consolidated, explainable market intelligence score (research heuristic)."""
from __future__ import annotations


def calculate_market_intelligence(regime: dict | None, breadth: dict | None, sector_strength: dict | None) -> dict:
    """Score regime, breadth and sector participation; normalize for available data."""
    components: list[dict] = []
    def add(name: str, points: float, maximum: float, detail: str, available: bool = True) -> None:
        if available:
            components.append({"name": name, "score": round(points, 2), "max_score": maximum, "detail": detail})

    regime_name = regime.get("regime") if regime else None
    if regime_name:
        points = {"bullish": 40.0, "sideways": 20.0, "bearish": 0.0}.get(regime_name, 0.0)
        add("Market regime", points, 40, f"Nifty 50 regime is {regime_name}.")
    if breadth and breadth.get("symbols_available", 0) > 0:
        above50 = breadth.get("above_sma50_pct")
        above200 = breadth.get("above_sma200_pct")
        if above50 is not None:
            add("Stocks above SMA 50", 20 * float(above50) / 100, 20, f"{above50}% of eligible stocks are above SMA 50.")
        if above200 is not None:
            add("Stocks above SMA 200", 10 * float(above200) / 100, 10, f"{above200}% of eligible stocks are above SMA 200.")
        advances, declines = breadth.get("advances", 0), breadth.get("declines", 0)
        if advances + declines:
            ad_points = 5 if advances > declines else 2.5 if advances == declines else 0
            add("Daily advance / decline", ad_points, 5, f"{advances} advances versus {declines} declines.")
        highs, lows = breadth.get("new_20_day_highs", 0), breadth.get("new_20_day_lows", 0)
        if highs + lows:
            hl_points = 5 if highs > lows else 2.5 if highs == lows else 0
            add("20-day highs / lows", hl_points, 5, f"{highs} new highs versus {lows} new lows.")
    sectors = (sector_strength or {}).get("sectors", {})
    if sectors:
        values = [item.get("relative_strength_pct") for item in sectors.values()]
        values = [float(value) for value in values if value is not None]
        if values:
            outperforming = sum(value > 0 for value in values)
            add("Sector participation", 20 * outperforming / len(values), 20,
                f"{outperforming} of {len(values)} calculated sectors outperform Nifty 50.")

    available_max = sum(item["max_score"] for item in components)
    raw_points = sum(item["score"] for item in components)
    score = round(raw_points / available_max * 100) if available_max else None
    completeness = round(available_max)
    if score is None:
        status, guidance = "unavailable", "Run the EOD pipeline after loading benchmark and constituent history."
    elif available_max < 50:
        status, guidance = "insufficient_data", "Not enough independent market data is available for a reliable snapshot."
    elif score >= 65:
        status, guidance = "favorable", "Market conditions are broadly supportive; still require individual setup and risk checks."
    elif score >= 40:
        status, guidance = "mixed", "Participation is mixed; be selective and demand stronger confirmations."
    else:
        status, guidance = "unfavorable", "Market conditions are weak; avoid forcing new long entries."
    return {
        "score": score,
        "status": status,
        "available_points": round(raw_points, 2),
        "available_max_points": completeness,
        "data_completeness_pct": round(available_max / 100 * 100, 2),
        "components": components,
        "guidance": guidance,
        "methodology": "Heuristic 100-point model: regime 40, breadth 40, sector participation 20. Score is normalized over available components; completeness is reported separately.",
        "warning": "Research-only composite, not a forecast or probability of profit. It does not alter scanner rankings or place/block orders.",
    }
