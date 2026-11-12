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
- The endpoint returns all ranked stocks and the shortlist. Sector-relative-strength scoring uses an equal-weight sector constituent return proxy versus Nifty 50 when at least two sector constituents and benchmark history are available.

This is a manual research pipeline, not a scheduler or trade execution system. It does not guarantee that the latest Yahoo candle is a completed NSE session candle; inspect timestamps and validate source quality. Live orders remain disabled.

## Research endpoints

- `POST /api/v1/indicators` — calculate indicators from supplied OHLCV bars.
- `POST /api/v1/scans/{reversal|vcp|momentum}` — evaluate one daily setup.
- `POST /api/v1/rank` — return an explainable 100-point stock ranking for one symbol.
- `POST /api/v1/universe/scan` — rank up to 500 supplied symbols and run reversal, VCP-candidate, and momentum scanners for each symbol.

The ranking weights are trend (20), momentum (15), ADX/DI strength (10), relative volume (15), breakout proximity (15), volatility contraction (10), sector relative strength (10), and liquidity (5). Sector relative strength can be supplied as `sector_relative_strength_pct`; the EOD pipeline now calculates it from configured sector constituents versus Nifty 50 over 20 sessions. The calculation is an equal-weight proxy, not an official sector index return. If unavailable, its 10 points are marked unavailable and score zero. Liquidity is estimated from the last 20 daily close * volume values unless `average_daily_turnover` (INR) is provided explicitly.

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


### Portfolio-level backtesting

- `POST /api/v1/backtest/portfolio` — combines candidate trades across up to 50 symbols, then applies a shared capital pool.
- Example: `{"symbols":["RELIANCE","TCS","INFY"],"setup":"momentum","initial_capital":1000000,"risk_per_trade_pct":0.5,"max_positions":5,"target_pct":5,"stop_atr_multiple":1.5,"max_holding_sessions":10,"cost_bps_per_side":10,"train_fraction":0.7,"max_participation_pct":1.0}`.
- Position quantity is capped by risk budget, available cash, and (when turnover data is present) a liquidity limit: position notional cannot exceed the configured percentage of the symbol's 20-session average daily traded value before the signal date. Default participation cap is 1%; this is a coarse capacity guard, not a market-impact model. Fractional shares are not used.
- The chronological holdout split is based on entry dates. Trades that cross the split boundary are excluded from both periods to avoid training-period positions leaking into the out-of-sample period. Train and out-of-sample portfolios each start with the configured initial capital.
- Every historical signal stores its point-in-time 100-point stock ranking, ranking band, and ranking-data completeness. On a shared entry date, the portfolio allocator prioritizes higher ranking scores; symbol order is only the deterministic tie-breaker. Sector relative strength is unavailable in this per-symbol historical ranking call, so the ranking completeness reflects that missing category.
- The response includes a daily mark-to-market equity curve and peak-to-trough drawdown using daily close marks for open positions; exit-day marks use the modeled stop/target/time exit price.
- `cost_model` defaults to `india_equity_delivery`. The estimate reports component totals and exact rate inputs for brokerage, exchange transaction charges, STT, stamp duty, SEBI fees, GST, DP charges, and modeled slippage. All delivery charge assumptions are configurable in the request. `flat_bps` remains available for sensitivity analysis.
- Defaults currently use NSE equity-delivery statutory levies (STT 0.1% each side, stamp duty 0.015% buy side, SEBI fee 0.0001% each side, GST 18%) and the NSE transaction-charge rate shown on the broker's public schedule (0.00307%). Brokerage defaults to zero, DP to zero, and slippage to 5 bps each side; set brokerage and DP for the actual broker/account. Rates and broker plans can change; this is not a historical effective-date fee engine.
- The liquidity cap does not model order-book depth or market impact. The simulator still assumes one buy and one sell for each position, simplified fee rounding, and no corporate-action tax treatment. Corporate actions and point-in-time index membership also require independent validation.


### Conditional trade setup and risk plan

- `POST /api/v1/trade-plan` — calculate a conditional entry trigger, ATR/structure stop, 1.5R/2R/3R targets, and risk-based share quantity for one symbol already stored in SQLite.
- Example body: `{"symbol":"RELIANCE","setup":"momentum","capital":1000000,"risk_per_trade_pct":0.5,"max_allocation_pct":20,"stop_atr_multiple":1.5}`.
- Reversal uses the prior 5-session high as its trigger basis; momentum uses the prior 20-session high; VCP uses the prior 55-session high and must be manually chart-validated. A small buffer is added to the pivot.
- The stop is placed below both the 10-session structural low and the ATR-based level (the lower of the two), which deliberately chooses the wider risk. Quantity is limited by both the risk budget and maximum capital allocation.
- Status distinguishes a setup whose scanner conditions pass, one whose conditions fail, and a trigger already crossed by the latest close. If already crossed, do not chase; wait for a fresh setup/retest and reassess.
- This is a conditional research plan only. It does not verify an executable order-book price, nearby resistance, gaps, slippage, complete Indian charges, or whether the last stored candle is complete. Targets are arithmetic R-multiples, not forecasts. No orders are placed.


### Daily + hourly confirmation

- The trade-plan endpoint also reads stored `1h` candles for the same symbol and checks short-term trend/momentum alignment.
- Hourly confirmation requires at least 60 completed hourly candles and checks: close above EMA20, EMA20 above EMA50, RSI between 50 and 70, MACD above signal, and +DI above -DI.
- Sync prototype hourly history with `POST /api/v1/market-data/sync/RELIANCE?timeframe=1h&period=60d`, then rerun `POST /api/v1/trade-plan`.
- If hourly candles are missing or fewer than 60, the plan reports `waiting_for_hourly_data` when the daily scanner passes. If any hourly condition fails, it reports `hourly_confirmation_failed`. A daily trigger already crossed remains flagged separately.
- Yahoo hourly history is limited, unofficial and may be delayed or incomplete. Use completed NSE-session candles only; this is a filter, not proof of future price direction. No orders are placed.


### Nifty 50 market regime filter

- `POST /api/v1/market-regime` with `{"benchmark":"^NSEI","sync_market_data":true}` downloads Nifty 50 daily history from the Yahoo prototype adapter, stores it, and returns an explainable regime classification.
- The classifier requires at least 210 daily candles and evaluates close vs SMA50/SMA200, moving-average slopes, 20-session return, and ADX.
- Bullish: at least 4 of 5 bullish checks pass and close is above SMA200. Bearish: at least 3 of 4 bearish checks pass and close is below SMA200. Otherwise sideways.
- The EOD pipeline reads stored `^NSEI` history. In a bearish regime it blocks new long candidates from the shortlist; in a sideways regime it raises the shortlist score threshold from 60 to 70. When benchmark history is unavailable, the pipeline clearly reports that the regime filter is unavailable and retains the legacy score threshold.
- Refresh the benchmark from the dashboard's Market Regime panel before running the EOD scan. The Nifty benchmark ticker is stored as `^NSEI`; the Yahoo adapter maps it directly without adding the NSE equity suffix.
- This is a transparent heuristic risk filter, not a market forecast. It does not modify individual stock ranking scores or close existing positions. Verify benchmark candle dates/completeness and provider quality; no orders are placed.


### Nifty 50 market regime filter

- `POST /api/v1/market-regime` with `{"benchmark":"^NSEI","sync_market_data":true}` downloads Nifty 50 daily history from the Yahoo prototype adapter, stores it, and returns an explainable regime classification.
- The classifier requires at least 210 daily candles and evaluates close vs SMA50/SMA200, moving-average slopes, 20-session return, and ADX.
- Bullish: at least 4 of 5 bullish checks pass and close is above SMA200. Bearish: at least 3 of 4 bearish checks pass and close is below SMA200. Otherwise sideways.
- The EOD pipeline reads stored `^NSEI` history. In a bearish regime it blocks new long candidates from the shortlist; in a sideways regime it raises the shortlist score threshold from 60 to 70. When benchmark history is unavailable, the pipeline clearly reports that the regime filter is unavailable and retains the legacy score threshold.
- Refresh the benchmark from the dashboard's Market Regime panel before running the EOD scan. The Nifty benchmark ticker is stored as `^NSEI`; the Yahoo adapter maps it directly without adding the NSE equity suffix.
- This is a transparent heuristic risk filter, not a market forecast. It does not modify individual stock ranking scores or close existing positions. Verify benchmark candle dates/completeness and provider quality; no orders are placed.


### Sector strength and rotation

The EOD pipeline calculates 20-session returns for configured universe constituents, groups them by the sector column in `data/universe/nse500.csv`, and compares each sector's equal-weight average return with Nifty 50. Sectors require at least two constituents with usable histories. Sector relative strength (percentage-point outperformance) is passed into the existing 10-point stock ranking component. The dashboard displays the strongest available sectors and their leading constituents after an EOD scan.

This is a constituent-based proxy, not an official sector-index series. It can be biased by incomplete universe membership, missing histories, and asynchronous last candle dates. It is not available until the Nifty benchmark and relevant stock candles are stored. The method does not imply predictive performance; validate it in out-of-sample portfolio backtests before relying on it.


### Market breadth and participation

The EOD pipeline reports breadth for configured universe constituents with at least 201 daily candles: advances/declines, the percentage above 20/50/200-day simple moving averages, and new 20-session highs/lows. The dashboard displays these metrics alongside sector strength and the Nifty 50 regime. This is equal-weight constituent breadth, not an official exchange advance/decline series. Coverage and candle dates matter: missing symbols or mismatched last dates can distort the snapshot. Breadth is currently informational and does not independently block trades or alter ranking scores.


### Consolidated market intelligence score

The EOD pipeline returns a 0–100 market intelligence score and a status (favorable, mixed, unfavorable, insufficient_data, or unavailable). The transparent weighting is: Nifty 50 regime 40 points; breadth 40 points (stocks above SMA 50 and SMA 200, daily advances/declines, and 20-session highs/lows); sector participation 20 points (share of calculated sectors outperforming Nifty 50). The score is normalized over available components, and data completeness is reported separately. A score based on fewer than 50 available points is marked insufficient_data. This is a research heuristic only; it does not alter stock rankings, shortlist rules, or order execution.


### Historical market-filter validation

The portfolio backtest can compare the same candidate trades with and without the consolidated market filter. For each signal date, the filter builds a snapshot using only selected-symbol daily histories and the stored Nifty 50 benchmark available through that date; trades below the configured market score or minimum data-completeness threshold are excluded. The response reports baseline and filtered train/out-of-sample portfolio metrics, excluded counts, and snapshot coverage. This first implementation uses only the selected backtest symbols for historical breadth and a currently configured sector map; it is not full point-in-time NSE 500 breadth or sector membership. Sync Nifty 50 history first. Treat the comparison as exploratory until tested on a larger, survivorship-bias-controlled universe with realistic costs and independent validation.


### Point-in-time NSE 500 membership and expanded validation

`data/universe/nse500_membership_history.csv` is the interval-based membership source for historical validation. Required columns are `symbol,sector,valid_from,valid_to,source,as_of_date,source_url`. Each row represents one continuous membership interval; `valid_to` is blank for an open interval. Overlapping intervals for a symbol are rejected. Add one row per symbol per membership interval, preserving the effective date and source URL. The repository intentionally ships only a header template: no historical membership has been fabricated.

The portfolio backtest accepts up to 500 symbols. To run a meaningful point-in-time comparison, import daily OHLCV for the constituents needed across the full test period, sync the Nifty 50 benchmark, and populate the dated membership file. Historical membership must be verified against exchange/index-provider snapshots and reconstitution notices. A current constituent CSV alone is not a point-in-time dataset. Third-party reconstructions can help bootstrap research but require independent audit for missing changes, ticker/ISIN migrations, delistings, mergers, and interval dates.

When membership history is present, each signal-date market snapshot selects only members active on that date, uses price histories ending on that date, and measures available breadth against the expected constituent count. Missing member histories reduce the market-data completeness percentage. Without the membership file, the result falls back to selected backtest symbols and explicitly remains a subset proxy. The filtered and baseline portfolios use the same out-of-sample split date so their holdout periods are comparable.

### Indian equity delivery cost model

Portfolio simulation defaults to `india_equity_delivery` rather than a flat basis-point deduction. It estimates per-position costs after share quantity is known: brokerage (configurable, default zero), exchange transaction charge (default 0.00307%), STT (0.1% on buy and sell), stamp duty (0.015% buy side), SEBI charge (0.0001% each side), GST (18% on brokerage, exchange and SEBI charges), optional broker-specific DP sell charge (default zero), and configurable slippage (default 5 bps each side). Each simulated position reports a component breakdown. These defaults are illustrative and must be checked against the selected broker, exchange, order type, and fee schedule effective on the trade date; the current defaults are not a historical tax engine. Flat-bps mode remains available for sensitivity analysis.

Reference fee schedule: [Zerodha charges](https://zerodha.com/charges/). The project does not assume Zerodha is the chosen broker. In particular, DP fees are broker-specific and are not included unless configured. The estimate does not yet model fee-rule changes by effective date, taxes on corporate actions, market impact, or all rounding/minimum-charge details.


A membership inspection endpoint is available at `GET /api/v1/universe/membership?as_of_date=YYYY-MM-DD`. It returns the members active on the requested date and the number of source intervals loaded. It returns a validation error when the membership file is missing, empty, or malformed.

### NSE historical daily OHLCV import

The backend can import official NSE cash-market bhavcopy files after you download them from NSE's historical reports portal. NSE's UDiFF common bhavcopy replaced the older cash-market bhavcopy format from 8 July 2024; the importer supports both UDiFF ZIP/CSV and legacy CSV headers. It filters to cash-market (CM), stock (STK) and equity (EQ) rows, then stores daily OHLCV by symbol.

Official source: [NSE All Reports — Equities](https://www.nseindia.com/all-reports). Choose the date and download **CM-UDiFF Common Bhavcopy Final (zip)** for dates from 8 July 2024 onward. For earlier dates, use the legacy CM bhavcopy CSV/ZIP where available. NSE notes the legacy CM bhavcopy formats were discontinued from 8 July 2024. [NSE report catalogue](https://www.nseindia.com/all-reports).

Single file:
```bash
python -m scripts.import_nse_bhavcopy /path/to/BhavCopy_NSE_CM_0_0_0_20250102_F_0000.csv.zip
```

Folder of downloaded daily ZIPs:
```bash
python -m scripts.import_nse_bhavcopy /path/to/nse_bhavcopies --directory --pattern "*.zip"
```

Use --pattern "*.csv" for extracted CSVs. The importer is idempotent and reports imported symbols, dates, rows and rejected records. It does not download files automatically or bypass NSE access controls. For a 2020–2026 history, download the daily bhavcopies in manageable yearly/monthly batches and retain the original files and retrieval notes.

**Corporate-action warning:** NSE bhavcopy OHLC is raw exchange data. Splits, bonuses, rights, mergers and symbol/ISIN changes must be reconciled before calculating long-history returns. The project must not mix raw NSE bars with auto-adjusted Yahoo bars for the same instrument. Store the source and adjustment methodology with each research dataset.

### Point-in-time membership source adapter

A candidate public reconstruction is [aditya-jha/nse-historical-membership](https://github.com/aditya-jha/nse-historical-membership). Its data is dedicated under CC0, and it documents its provenance, half-open interval semantics, known pre-2018 cardinality drift, and validation results. It is third-party reconstructed data, not an official NSE constituent history. Review its current README and validation report before use.

The repository's headline file is `index_history/data/index_membership_history.csv`. Convert it to the NSIS format with:
```bash
python -m scripts.convert_nse_membership_history /path/to/index_membership_history.csv --as-of-date 2026-11-02
```

The adapter keeps only Nifty 500 rows and converts the source's half-open `[valid_from, valid_to)` intervals into NSIS inclusive end dates. It retains each source label, source URL, notes and a confidence flag. `snapshot_floor` / inferred intervals are explicitly marked lower confidence. The source export does not provide historical sector classifications in this table, so the historical filter omits the sector-strength component rather than pretending current sectors are historical sectors.

Before using the result in strategy evaluation, check daily member counts, known additions/removals, ticker and ISIN migrations, and all `snapshot_floor_or_inferred` intervals. The project intentionally does not ship this third-party file as verified ground truth; the user must obtain and review the source export separately.

### Historical data source findings

NSE's official [All Reports](https://www.nseindia.com/all-reports) portal provides daily cash-market reports. The official catalogue states the old CM bhavcopy formats were discontinued from 8 July 2024 and replaced with the UDiFF common bhavcopy. The importer accepts UDiFF files and the older `sec_bhavdata_full` / legacy equity CSV header variants. For 2020–2026, `sec_bhavdata_full` is a practical daily bulk source where available; UDiFF is the current format from July 2024. Keep downloaded raw files so the source data can be reprocessed and audited.

**Do not treat the current NSE 500 list as historical membership.** The membership file and OHLCV history are separate datasets and both need date-level validation before a survivorship-bias-free backtest is considered ready.
