# Backend

## Local setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
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

The service exposes health, market-data, indicator, scanner, and ranking endpoints.

## Market data ingestion

The first ingestion iteration is provider-neutral and uses SQLite (Python standard library; no extra database package required). The default database is `data/nsis_market_data.db`; override it with `DATABASE_PATH`.

- `POST /api/v1/market-data/import` — persist a validated OHLCV batch.
- `GET /api/v1/market-data/bars/{symbol}?timeframe=1d&limit=1000` — retrieve stored bars chronologically.

Imports are idempotent: a repeated symbol/timeframe/timestamp updates that candle rather than creating a duplicate. Duplicate timestamps inside one request are rejected. Supported timeframes are `1h`, `4h`, and `1d`.

### CSV format

A CSV must contain these columns:

```csv
timestamp,open,high,low,close,volume
2025-01-01T00:00:00+05:30,100.0,102.0,99.0,101.0,100000
```

Use `import_ohlcv_csv(path, symbol, timeframe, store)` from `backend.app.market_data` to validate and load a CSV into the store. The example file is `data/samples/ohlcv_template.csv`. Timestamps must be ISO-8601 and prices/volume must pass the OHLCV schema checks.

The starter universe file is `data/universe/nse500.csv`. It intentionally contains headers only: populate it from a verified, dated constituent source. Do not treat a current constituent list as historical membership for backtests.

No market data is downloaded automatically in this phase. A provider must be selected and its licensing, API limits, adjustment methodology, and historical coverage verified before scheduled ingestion is enabled.

## Research endpoints

- `POST /api/v1/indicators` — calculate indicators from supplied OHLCV bars.
- `POST /api/v1/scans/{reversal|vcp|momentum}` — evaluate one daily setup.
- `POST /api/v1/rank` — return an explainable 100-point stock ranking for one symbol.
- `POST /api/v1/universe/scan` — rank up to 500 supplied symbols and run reversal, VCP-candidate, and momentum scanners for each symbol.

The ranking weights are trend (20), momentum (15), ADX/DI strength (10), relative volume (15), breakout proximity (15), volatility contraction (10), sector relative strength (10), and liquidity (5). Sector relative strength can be supplied as `sector_relative_strength_pct`; if omitted, its 10 points are marked unavailable and score zero. Liquidity is estimated from the last 20 daily close * volume values unless `average_daily_turnover` (INR) is provided explicitly.

The batch endpoint accepts one daily OHLCV history per symbol (at least 210 bars), sorts results by ranking score, reports each setup's pass/fail status, and returns per-symbol errors for invalid histories.

These are heuristic research scores, not probabilities of profit. No broker connection or live trading is enabled.
