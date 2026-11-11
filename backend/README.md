# Backend

## Local setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the API documentation.

## Run tests

```bash
pytest
```

The service exposes system health, indicator, scanner, and ranking endpoints.

## Research endpoints

- `POST /api/v1/indicators` — calculate indicators from supplied OHLCV bars.
- `POST /api/v1/scans/{reversal|vcp|momentum}` — evaluate one daily setup.
- `POST /api/v1/rank` — return an explainable 100-point stock ranking for one symbol.
- `POST /api/v1/universe/scan` — rank up to 500 supplied symbols and run reversal, VCP-candidate, and momentum scanners for each symbol.

The ranking weights are trend (20), momentum (15), ADX/DI strength (10), relative volume (15), breakout proximity (15), volatility contraction (10), sector relative strength (10), and liquidity (5). Sector relative strength can be supplied as `sector_relative_strength_pct`; if omitted, its 10 points are marked unavailable and score zero. Liquidity is estimated from the last 20 daily close * volume values unless `average_daily_turnover` (INR) is provided explicitly.

The batch endpoint accepts one daily OHLCV history per symbol (at least 210 bars), sorts results by ranking score, reports each setup's pass/fail status, and returns per-symbol errors for invalid histories. It does not download NSE 500 data automatically; a data source and historical universe membership are a separate upcoming task.

These are heuristic research scores, not probabilities of profit. The ranking endpoint requires at least 210 daily bars. No broker connection or live trading is enabled.
