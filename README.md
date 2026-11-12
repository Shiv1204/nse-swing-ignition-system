# NSE Swing Ignition System (NSIS-10)

A research and decision-support platform for long-only NSE 500 swing trading, targeting 3–10 trading-day setups. The system will scan, rank, backtest, and manage hypothetical trades before any live-broker integration is enabled.

## Safety and execution policy

- Paper/research mode only during initial development.
- Live order placement is disabled by default and will require explicit manual approval if introduced later.
- No strategy performance is assumed; all setups must be validated with historical and out-of-sample testing.

## Planned capabilities

1. NSE 500 universe and market-data ingestion
2. Daily and intraday indicator calculations
3. Reversal, volatility-contraction (VCP), and momentum-breakout scanners
4. Explainable 100-point setup scoring and ranking
5. ATR-based risk, stop-loss, position sizing, and trade journal
6. Backtesting with transaction costs, slippage, and look-ahead safeguards
7. FastAPI backend and Next.js dashboard
8. Optional Zerodha Kite integration only after validation, initially read-only/paper mode

## Dashboard (Next.js)

The frontend lives in `frontend/` and connects to the FastAPI backend.

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` to the backend URL (default: `http://localhost:8000`). Start the backend separately using the instructions in `backend/README.md`. The dashboard currently provides API connectivity status, EOD pipeline execution, ranked watchlists, and portfolio backtest controls. It displays no fabricated market prices; results require a configured universe and stored OHLCV history.

## Initial development sequence

- Phase 1: backend foundation, configuration, health endpoint, and tests
- Phase 2: indicator engine and scanner rules
- Phase 3: scoring, risk management, and backtesting
- Phase 4: dashboard and data-provider integration
- Phase 5: paper trading and monitored validation

## Important

The proposed 3–10 day holding period and 3–8% target range are research objectives, not guaranteed outcomes. This software is not investment advice.