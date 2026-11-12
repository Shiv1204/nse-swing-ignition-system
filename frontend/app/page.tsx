"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowUpRight, BarChart3, Bell, CandlestickChart,
  CheckCircle2, ChevronDown, CircleAlert, Clock3, Command, Gauge, LayoutDashboard,
  ListFilter, LoaderCircle, Play, RefreshCw, Search, Settings2, ShieldCheck,
  SlidersHorizontal, Sparkles, Target, TrendingUp, Wallet, Wifi, WifiOff, X,
} from "lucide-react";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

type Tab = "overview" | "scanner" | "backtest";
type ScanRow = {
  symbol: string;
  ranking?: { score?: number; rank_band?: string; close?: number; reasons?: string[] };
  setups?: Record<string, { passed?: boolean; score?: number; reasons?: string[] }>;
  passed_setups?: string[];
  rank_position?: number;
};
type Pipeline = {
  universe_count?: number; symbols_ranked?: number; shortlist_count?: number;
  shortlist?: ScanRow[]; all_ranked?: ScanRow[]; errors?: {symbol:string;error:string}[];
  notes?: string[];
};

function money(value?: number) {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(value);
}
function scoreColor(score = 0) {
  return score >= 80 ? "green" : score >= 70 ? "blue" : score >= 60 ? "amber" : "muted";
}

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [apiOnline, setApiOnline] = useState(false);
  const [apiChecking, setApiChecking] = useState(true);
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [pipelineError, setPipelineError] = useState("");
  const [setup, setSetup] = useState("momentum");
  const [symbolSearch, setSymbolSearch] = useState("");
  const [backtestSymbols, setBacktestSymbols] = useState("RELIANCE,TCS,INFY");
  const [backtestResult, setBacktestResult] = useState<Record<string, unknown> | null>(null);
  const [backtestBusy, setBacktestBusy] = useState(false);
  const [toast, setToast] = useState("");

  const checkApi = useCallback(async () => {
    setApiChecking(true);
    try {
      const response = await fetch(`${API}/health`, { cache: "no-store" });
      setApiOnline(response.ok);
    } catch {
      setApiOnline(false);
    } finally {
      setApiChecking(false);
    }
  }, []);

  useEffect(() => { void checkApi(); }, [checkApi]);

  const runPipeline = async (sync: boolean) => {
    setPipelineBusy(true); setPipelineError("");
    try {
      const response = await fetch(`${API}/api/v1/pipeline/eod`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sync_market_data: sync, shortlist_limit: 30 }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Pipeline request failed");
      setPipeline(payload);
      setToast("EOD scan completed");
      window.setTimeout(() => setToast(""), 3500);
    } catch (error) {
      setPipelineError(error instanceof Error ? error.message : "Unable to run the scan");
    } finally { setPipelineBusy(false); }
  };

  const runBacktest = async () => {
    const symbols = backtestSymbols.split(",").map(s => s.trim().toUpperCase()).filter(Boolean);
    if (!symbols.length) return;
    setBacktestBusy(true); setBacktestResult(null);
    try {
      const response = await fetch(`${API}/api/v1/backtest/portfolio`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbols, setup, initial_capital: 1000000, risk_per_trade_pct: 0.5,
          max_positions: 5, target_pct: 5, stop_atr_multiple: 1.5,
          max_holding_sessions: 10, cost_bps_per_side: 10, train_fraction: 0.7,
          max_participation_pct: 1,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Backtest request failed");
      setBacktestResult(payload);
    } catch (error) {
      setBacktestResult({ error: error instanceof Error ? error.message : "Backtest failed" });
    } finally { setBacktestBusy(false); }
  };

  const rows = useMemo(() => {
    const source = pipeline?.shortlist || pipeline?.all_ranked || [];
    return source.filter(row => row.symbol.toLowerCase().includes(symbolSearch.toLowerCase()));
  }, [pipeline, symbolSearch]);

  const tabs = [
    { id: "overview" as Tab, label: "Overview", icon: LayoutDashboard },
    { id: "scanner" as Tab, label: "Stock scanner", icon: ListFilter },
    { id: "backtest" as Tab, label: "Portfolio backtest", icon: BarChart3 },
  ];

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><CandlestickChart size={22}/></div><div><strong>NSIS<span>10</span></strong><small>SWING IGNITION SYSTEM</small></div></div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav">
          {tabs.map(item => <button key={item.id} className={tab === item.id ? "nav-item active" : "nav-item"} onClick={() => setTab(item.id)}><item.icon size={17}/>{item.label}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="mode-card"><div className="mode-icon"><ShieldCheck size={17}/></div><div><b>Research mode</b><small>Live orders disabled</small></div><span className="status-dot"/></div>
          <div className="user-row"><div className="avatar">S</div><div><b>Strategy workspace</b><small>Developer environment</small></div><Settings2 size={16}/></div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> {tabs.find(t => t.id === tab)?.label}</div>
          <div className="top-actions">
            <div className={apiOnline ? "connection online" : "connection offline"}>{apiChecking ? <LoaderCircle className="spin" size={14}/> : apiOnline ? <Wifi size={14}/> : <WifiOff size={14}/>}<span>{apiChecking ? "Checking API" : apiOnline ? "API connected" : "API offline"}</span></div>
            <button className="icon-button" aria-label="Notifications"><Bell size={17}/></button>
            <div className="avatar small">S</div>
          </div>
        </header>

        <div className="content">
          <div className="page-heading">
            <div><div className="eyebrow"><span className="live-pulse"/> NSE SWING RESEARCH</div><h1>{tab === "overview" ? "Market overview" : tab === "scanner" ? "Stock scanner" : "Portfolio backtest"}</h1><p>Find, evaluate and validate high-quality swing setups across the NSE universe.</p></div>
            <div className="heading-actions"><button className="button secondary" onClick={() => void checkApi()}><RefreshCw size={15}/> Refresh status</button><button className="button primary" disabled={!apiOnline || pipelineBusy} onClick={() => void runPipeline(false)}>{pipelineBusy ? <LoaderCircle className="spin" size={16}/> : <Play size={15}/>} Run EOD scan</button></div>
          </div>

          {!apiOnline && <div className="notice warning"><CircleAlert size={18}/><div><b>Backend not connected</b><p>Start the FastAPI service at <code>{API}</code> to load market data and run scans. The dashboard UI is ready, but it will not invent market values.</p></div></div>}
          {pipelineError && <div className="notice error"><CircleAlert size={18}/><div><b>Scan could not run</b><p>{pipelineError}</p></div><button className="plain-icon" onClick={() => setPipelineError("")}><X size={16}/></button></div>}

          {tab === "overview" && <>
            <div className="metric-grid">
              <Metric icon={<Gauge size={18}/>} label="Universe loaded" value={pipeline?.universe_count?.toString() || "—"} hint="Verified constituents"/>
              <Metric icon={<Activity size={18}/>} label="Stocks ranked" value={pipeline?.symbols_ranked?.toString() || "—"} hint="Daily data available"/>
              <Metric icon={<Target size={18}/>} label="Shortlisted" value={pipeline?.shortlist_count?.toString() || "—"} hint="Score ≥ 60 + setup pass"/>
              <Metric icon={<Clock3 size={18}/>} label="Holding horizon" value="3–10 days" hint="Research objective"/>
            </div>
            <div className="section-grid">
              <div className="panel-card featured-card">
                <div className="card-head"><div><div className="eyebrow">DAILY WORKFLOW</div><h2>End-of-day ignition scan</h2></div><div className="icon-tile"><Sparkles size={19}/></div></div>
                <p>Refresh historical candles, calculate indicators, rank the universe and identify reversal, VCP and momentum candidates.</p>
                <div className="workflow">
                  <WorkflowStep n="01" title="Market data" desc="Historical daily OHLCV"/>
                  <WorkflowStep n="02" title="Rank & classify" desc="Explainable 100-point score"/>
                  <WorkflowStep n="03" title="Setup detection" desc="Three long-only strategies"/>
                </div>
                <div className="card-footer"><span><ShieldCheck size={14}/> No orders are placed</span><button className="button primary" disabled={!apiOnline || pipelineBusy} onClick={() => void runPipeline(false)}>{pipelineBusy ? <LoaderCircle className="spin" size={15}/> : <Play size={14}/>} Run scan</button></div>
              </div>
              <div className="panel-card">
                <div className="card-head"><div><div className="eyebrow">STRATEGY MIX</div><h2>Setup framework</h2></div><SlidersHorizontal size={18} className="muted-icon"/></div>
                <SetupInfo name="Momentum breakout" tag="TREND FOLLOWING" text="Price expansion with trend, ADX and relative-volume confirmation." color="blue"/>
                <SetupInfo name="Volatility contraction" tag="BASE FORMATION" text="Tightening range near highs with declining volume." color="purple"/>
                <SetupInfo name="Reversal" tag="TREND RECOVERY" text="Early recovery above short-term averages with improving momentum." color="green"/>
              </div>
            </div>
            <div className="panel-card table-card">
              <div className="card-head"><div><div className="eyebrow">LATEST RESULTS</div><h2>Priority watchlist</h2></div><button className="text-button" onClick={() => setTab("scanner")}>View scanner <ArrowUpRight size={14}/></button></div>
              <Watchlist rows={rows.slice(0, 6)} emptyText="Run the EOD scan to populate your watchlist with actual backend results."/>
            </div>
          </>}

          {tab === "scanner" && <div className="panel-card table-card">
            <div className="scanner-toolbar"><div><div className="eyebrow">NSE UNIVERSE</div><h2>Ranked candidates</h2></div><div className="toolbar-controls"><div className="search-box"><Search size={15}/><input value={symbolSearch} onChange={e => setSymbolSearch(e.target.value)} placeholder="Search symbol"/></div><button className="button secondary" disabled={!apiOnline || pipelineBusy} onClick={() => void runPipeline(false)}>{pipelineBusy ? <LoaderCircle className="spin" size={15}/> : <RefreshCw size={15}/>} Refresh scan</button></div></div>
            <div className="filter-row"><label>Setup focus</label><select value={setup} onChange={e => setSetup(e.target.value)}><option value="momentum">Momentum</option><option value="vcp">VCP</option><option value="reversal">Reversal</option></select><span className="filter-note">Results reflect the latest EOD pipeline response.</span></div>
            <Watchlist rows={rows} emptyText="No scan results yet. Run the EOD scan after configuring the verified NSE 500 universe and loading daily candles."/>
          </div>}

          {tab === "backtest" && <div className="panel-card backtest-card">
            <div className="eyebrow">HISTORICAL VALIDATION</div><h2>Portfolio simulation</h2><p className="panel-intro">Run a capital-constrained backtest against symbols with daily candles already stored in the backend.</p>
            <div className="form-grid">
              <div className="field wide"><label>Symbols (comma separated)</label><input value={backtestSymbols} onChange={e => setBacktestSymbols(e.target.value)} placeholder="RELIANCE,TCS,INFY"/></div>
              <div className="field"><label>Strategy setup</label><select value={setup} onChange={e => setSetup(e.target.value)}><option value="momentum">Momentum breakout</option><option value="vcp">VCP</option><option value="reversal">Reversal</option></select></div>
              <div className="field"><label>Initial capital</label><input value="₹10,00,000" disabled/></div>
              <div className="field"><label>Risk per trade</label><input value="0.5%" disabled/></div>
              <div className="field"><label>Maximum positions</label><input value="5" disabled/></div>
            </div>
            <div className="backtest-actions"><span><ShieldCheck size={15}/> Research only · no live orders</span><button className="button primary" disabled={!apiOnline || backtestBusy} onClick={() => void runBacktest()}>{backtestBusy ? <LoaderCircle className="spin" size={15}/> : <Play size={14}/>} Run portfolio backtest</button></div>
            {backtestResult && <div className="result-panel"><div className="card-head"><h3>Backtest response</h3><button className="plain-icon" onClick={() => setBacktestResult(null)}><X size={16}/></button></div>{"error" in backtestResult ? <div className="result-error">{String(backtestResult.error)}</div> : <pre>{JSON.stringify(backtestResult, null, 2)}</pre>}</div>}
          </div>}
          <footer className="footer-note"><span>NSIS v0.1 · Development branch</span><span>Research tool only · Not investment advice</span></footer>
        </div>
      </section>
      {toast && <div className="toast"><CheckCircle2 size={16}/>{toast}</div>}
    </main>
  );
}

function Metric({icon,label,value,hint}:{icon:React.ReactNode;label:string;value:string;hint:string}) {
  return <div className="metric-card"><div className="metric-top"><span className="metric-icon">{icon}</span><span className="metric-label">{label}</span></div><strong>{value}</strong><small>{hint}</small></div>;
}
function WorkflowStep({n,title,desc}:{n:string;title:string;desc:string}) {
  return <div className="workflow-step"><span>{n}</span><div><b>{title}</b><small>{desc}</small></div><CheckCircle2 size={16}/></div>;
}
function SetupInfo({name,tag,text,color}:{name:string;tag:string;text:string;color:string}) {
  return <div className="setup-info"><span className={`setup-dot ${color}`}/><div><b>{name}</b><small>{tag}</small><p>{text}</p></div><ChevronDown size={15}/></div>;
}
function Watchlist({rows,emptyText}:{rows:ScanRow[];emptyText:string}) {
  if (!rows.length) return <div className="empty-state"><div className="empty-icon"><BarChart3 size={22}/></div><b>No candidates to display</b><p>{emptyText}</p></div>;
  return <div className="table-wrap"><table><thead><tr><th>RANK / SYMBOL</th><th>LAST CLOSE</th><th>RANK SCORE</th><th>RANK BAND</th><th>SETUPS PASSED</th></tr></thead><tbody>{rows.map((row,i) => <tr key={row.symbol}><td><div className="symbol-cell"><span className="rank-num">{row.rank_position || i+1}</span><b>{row.symbol}</b></div></td><td>{money(row.ranking?.close)}</td><td><div className="score-cell"><b>{row.ranking?.score ?? "—"}</b><span className="score-track"><i style={{width:`${Math.max(0,Math.min(100,row.ranking?.score || 0))}%`}}/></span></div></td><td><span className={`score-badge ${scoreColor(row.ranking?.score)}`}>{row.ranking?.rank_band || "—"}</span></td><td><div className="setup-tags">{(row.passed_setups || []).length ? row.passed_setups?.map(s=><span key={s}>{s}</span>) : <span className="none-tag">None</span>}</div></td></tr>)}</tbody></table></div>;
}
