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

A verified provider and dated constituent universe are still required before production or historical performance analysis.


### Yahoo Finance prototype sync

Install `yfinance` through `pip install -r requirements.txt`. The provider maps bare NSE symbols to Yahoo's `.NS` suffix and stores adjusted OHLCV candles in SQLite.

- `POST /api/v1/market-data/sync/RELIANCE?timeframe=1d&period=5y` — fetch daily history and upsert it.
- `POST /api/v1/market-data/sync/RELIANCE?timeframe=1h&period=60d` — fetch hourly history and upsert it.
- Repeat the daily sync after market close to refresh overlapping candles and append newer data.

The initial adapter supports daily and hourly candles. Four-hour bars are intentionally not synthesized yet because aggregation must respect NSE trading sessions and partial final candles. The Yahoo Finance library is an unofficial interface to Yahoo data; availability, coverage, adjustments, rate limits, terms, and redistribution rights can change. Validate imported candles against a trusted source before using them for performance claims or trade decisions. The provider is a prototype and is not a guaranteed real-time feed. Universe sync is deliberately limited to 50 symbols per request to reduce provider load and throttling risk. Repeat requests in batches to cover a 500-stock universe. The constituent CSV remains header-only until populated from the official Nifty 500 constituent download with its source and as-of date; the API rejects empty or unprovenanced lists. Official reference: https://www.nseindia.com/static/products-services/indices-nifty500-index. Historical membership must be maintained separately for point-in-time backtests. No scheduler is enabled.


### Manual end-of-day pipeline

- `POST /api/v1/pipeline/eod` — validate the configured dated universe, optionally sync daily candles, load stored history, calculate the 100-point ranking, run reversal/VCP-candidate/momentum scans, and return a ranked list plus a filtered shortlist.
- Example body: `{"sync_market_data": false, "shortlist_limit": 30}`.
- Set `sync_market_data` to `true` to fetch daily history sequentially from Yahoo Finance before scanning. The pipeline does not schedule itself; invoke it after the NSE session has closed.
- A stock needs at least 210 daily candles. Stocks with missing/insufficient history are reported separately. The shortlist includes stocks with ranking score >=60 and at least one passing setup.
- The endpoint returns all ranked stocks and the shortlist. Sector-relative-strength scoring remains unavailable until sector/benchmark histories are integrated.

This is a manual research pipeline, not a scheduler or trade execution system. It does not guarantee that the latest Yahoo candle is a completed NSE session candle; inspect timestamps and validate source quality. Live orders remain disabled.

## Research endpoints

- `POST /api/v1/indicators` — calculate indicators from supplied OHLCV bars.
- `POST /api/v1/scans/{reversal|vcp|momentum}` — evaluate one daily setup.
- `POST /api/v1/rank` — return an explainable 100-point stock ranking for one symbol.
- `POST /api/v1/universe/scan` — rank up to 500 supplied symbols and run reversal, VCP-candidate, and momentum scanners for each symbol.

The ranking weights are trend (20), momentum (15), ADX/DI strength (10), relative volume (15), breakout proximity (15), volatility contraction (10), sector relative strength (10), and liquidity (5). Sector relative strength can be supplied as `sector_relative_strength_pct`; if omitted, its 10 points are marked unavailable and score zero. Liquidity is estimated from the last 20 daily close * volume values unless `average_daily_turnover` (INR) is provided explicitly.

The batch endpoint accepts one daily OHLCV history per symbol (at least 210 bars), sorts results by ranking score, reports each setup's pass/fail status, and returns per-symbol errors for invalid histories.

These are heuristic research scores, not probabilities of profit. No broker connection or live trading is enabled.


### Historical backtesting (research prototype)

- `POST /api/v1/backtest` — backtest one scanner setup across up to 50 symbols already stored in SQLite.
- Example body: `{"symbols":["RELIANCE","TCS"],"setup":"momentum","target_pct":5,"stop_atr_multiple":1.5,"max_holding_sessions":10,"cost_bps_per_side":10}`.
- Signals are evaluated using the completed daily candle; entry is the next session open. The ATR stop is based on the signal-day ATR and fixed relative to entry. The default profit target is 5%; change it to test other objectives in the 3–8% range.
- A trade exits at stop, target, or the close of the maximum holding session. If stop and target are both touched on one daily candle, stop is assumed first. A gap below the stop exits at the opening price.
- Costs are modeled as configurable basis points per side (default 10 bps each side); this is a placeholder, not a complete India-specific brokerage, STT, exchange, GST, stamp-duty and slippage model. Replace with actual broker/segment charges before relying on results.
- Metrics include win rate, average net return, average R, profit factor, expectancy R, trade-sequence drawdown and compounded return. Overlapping positions for the same symbol/setup are skipped until the prior trade exits.
- This first version evaluates each setup independently and uses the stored adjusted OHLCV data. It does not yet implement portfolio-level capital allocation, concurrent position limits, benchmark comparison, walk-forward optimization, delisted-symbol coverage, point-in-time universe membership, or a complete corporate-action validation process.

**Important:** A backtest result is not evidence that the strategy achieves its target. The NSE 500 CSV remains an empty template until populated from a verified dated source; do not run a claimed NSE 500 historical study with today's constituents substituted for historical membership. Yahoo Finance is an unofficial prototype data source. Validate the data and costs independently, and do not enable live trading based on these prototype results.
