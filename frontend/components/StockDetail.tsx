"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, ComposedChart, Bar, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { ArrowLeft, CircleAlert, LoaderCircle, RefreshCw, TrendingUp } from "lucide-react";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

type BarData = { timestamp: string; open: number; high: number; low: number; close: number; volume: number };
type Indicators = Record<string, number | null>;
type ChartBar = BarData & { date: string; ema20?: number | null };
type DetailResponse = { symbol: string; bars: ChartBar[]; latest: Indicators; note?: string };

const fmt = (n?: number | null) => n == null || !Number.isFinite(n) ? "—" : n.toFixed(2);
const rupee = (n?: number | null) => n == null ? "—" : new Intl.NumberFormat("en-IN", {style:"currency",currency:"INR",maximumFractionDigits:2}).format(n);

export default function StockDetail({ symbol, onBack }: { symbol: string; onBack: () => void }) {
  const [data, setData] = useState<DetailResponse | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [syncBusy, setSyncBusy] = useState(false);

  const load = async () => {
    setBusy(true); setError("");
    try {
      const barsResponse = await fetch(`${API}/api/v1/market-data/bars/${encodeURIComponent(symbol)}?timeframe=1d&limit=500`, { cache: "no-store" });
      const barsPayload = await barsResponse.json();
      if (!barsResponse.ok) throw new Error(barsPayload.detail || "Could not load stored candles");
      if (!barsPayload.bars?.length) throw new Error("No daily candles are stored for this symbol. Import or sync history first.");
      const indicatorResponse = await fetch(`${API}/api/v1/indicators`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, timeframe: "1d", bars: barsPayload.bars }),
      });
      const indicatorPayload = await indicatorResponse.json();
      if (!indicatorResponse.ok) throw new Error(indicatorPayload.detail || "Could not calculate indicators");
      const bars: BarData[] = barsPayload.bars;
      const latest = indicatorPayload.latest as Indicators;
      const chart = bars.map((bar, index) => ({
        ...bar,
        date: new Date(bar.timestamp).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }),
        ema20: index >= 19 ? bars.slice(index - 19, index + 1).reduce((sum, item) => sum + item.close, 0) / 20 : null,
      }));
      // The chart overlay is a 20-day simple average; EMA20 is separately shown from the backend.
      setData({ symbol, bars: chart, latest, note: indicatorPayload.note });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load stock detail");
      setData(null);
    } finally { setBusy(false); }
  };

  useEffect(() => { void load(); }, [symbol]);

  const last = data?.bars[data.bars.length - 1];
  const previous = data?.bars[data.bars.length - 2];
  const change = last && previous ? ((last.close / previous.close) - 1) * 100 : null;
  const chartData = useMemo(() => data?.bars || [], [data]);

  return <div className="stock-detail">
    <div className="detail-toolbar">
      <button className="button secondary" onClick={onBack}><ArrowLeft size={15}/> Back to scanner</button>
      <button className="button secondary" onClick={() => void load()} disabled={busy || syncBusy}>{busy ? <LoaderCircle className="spin" size={15}/> : <RefreshCw size={15}/>} Refresh data</button>
    </div>
    {busy && <div className="detail-loading"><LoaderCircle className="spin" size={22}/> Loading {symbol} daily history and indicators…</div>}
    {error && <div className="notice error"><CircleAlert size={18}/><div><b>Stock data unavailable</b><p>{error}</p><button className="button secondary sync-button" disabled={syncBusy} onClick={async () => { setSyncBusy(true); try { const response = await fetch(`${API}/api/v1/market-data/sync/${encodeURIComponent(symbol)}?timeframe=1d&period=5y`, { method: "POST" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || "History sync failed"); await load(); } catch (e) { setError(e instanceof Error ? e.message : "History sync failed"); } finally { setSyncBusy(false); } }}>{syncBusy ? <LoaderCircle className="spin" size={14}/> : <RefreshCw size={14}/>} Sync 5 years of daily history</button></div></div>}
    {data && !busy && <>
      <div className="detail-title-row">
        <div><div className="eyebrow">NSE · DAILY CHART · {data.bars.length} CANDLES</div><h2>{symbol}</h2><p className="detail-subtitle">Latest stored adjusted daily OHLCV data</p></div>
        <div className="detail-price"><strong>{rupee(last?.close)}</strong><span className={change != null && change >= 0 ? "positive" : "negative"}>{change == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`} vs previous close</span></div>
      </div>
      <div className="indicator-grid">
        <Indicator label="RSI (14)" value={fmt(data.latest.rsi_14)} note="Momentum" />
        <Indicator label="ADX (14)" value={fmt(data.latest.adx)} note="Trend strength" />
        <Indicator label="+DI / −DI" value={`${fmt(data.latest.plus_di)} / ${fmt(data.latest.minus_di)}`} note="Directional movement" />
        <Indicator label="ATR (14)" value={fmt(data.latest.atr_14)} note="Volatility" />
        <Indicator label="EMA 20" value={fmt(data.latest.ema_20)} note="Short trend" />
        <Indicator label="EMA 50" value={fmt(data.latest.ema_50)} note="Medium trend" />
        <Indicator label="MACD" value={fmt(data.latest.macd)} note={`Signal ${fmt(data.latest.signal)}`} />
        <Indicator label="Relative volume" value={fmt(data.latest.relative_volume_20)} note="20-day baseline" />
      </div>
      <div className="panel-card chart-panel">
        <div className="card-head"><div><div className="eyebrow">PRICE ACTION</div><h2>OHLC candlesticks & trend reference</h2></div><span className="chart-legend"><i/> Close <i className="legend-ema"/> 20-day average</span></div>
        <div className="chart-area"><CandlestickPlot data={chartData}/></div>
      </div>
      <div className="panel-card volume-panel">
        <div className="card-head"><div><div className="eyebrow">PARTICIPATION</div><h2>Daily traded volume</h2></div><span className="volume-latest">{last?.volume.toLocaleString("en-IN") ?? "—"} shares</span></div>
        <div className="volume-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{top:5,right:12,left:0,bottom:0}}><CartesianGrid stroke="#263548" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" tick={{fill:"#8091a8",fontSize:10}} minTickGap={35} axisLine={{stroke:"#34465c"}} tickLine={false}/><YAxis tick={{fill:"#8091a8",fontSize:10}} axisLine={false} tickLine={false} width={58}/><Tooltip contentStyle={{background:"#101b29",border:"1px solid #34465c",borderRadius:8,color:"#e8eef7",fontSize:11}}/><Bar dataKey="volume" name="Volume" fill="#477fbd" opacity={0.75}/></ComposedChart></ResponsiveContainer></div>
      </div>
      <div className="notice warning"><TrendingUp size={17}/><div><b>Indicator interpretation</b><p>Indicators describe historical price and volume behaviour; they are not trade instructions. The trend line shown is a 20-day simple average for chart reference. EMA values above are calculated by the backend.</p></div></div>
    </>}
  </div>;
}

function CandlestickPlot({data}:{data:ChartBar[]}) {
  if (!data.length) return null;
  const width = 1100, height = 300, left = 12, right = 12, top = 12, bottom = 24;
  const min = Math.min(...data.map(d => d.low));
  const max = Math.max(...data.map(d => d.high));
  const pad = (max - min) * 0.06 || max * 0.01;
  const low = min - pad, high = max + pad;
  const plotHeight = height - top - bottom, plotWidth = width - left - right;
  const y = (price:number) => top + (high - price) / (high - low) * plotHeight;
  const step = plotWidth / data.length, bodyWidth = Math.max(2, Math.min(10, step * 0.62));
  const average = data.map((d,i) => d.ema20 == null ? null : `${left + (i + 0.5) * step},${y(d.ema20)}`).filter(Boolean).join(" ");
  return <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Daily candlestick chart with 20-day simple moving average" preserveAspectRatio="none">
    {[0,1,2,3].map(i => { const price = high - (high-low)*i/3; return <g key={i}><line x1={left} x2={width-right} y1={y(price)} y2={y(price)} stroke="#263548" strokeDasharray="4 5"/><text x={left+3} y={y(price)-4} fill="#8091a8" fontSize="10">{price.toFixed(0)}</text></g>; })}
    {data.map((d,i) => { const x = left + (i + .5) * step; const up = d.close >= d.open; const color = up ? "#45d6a0" : "#ff7d83"; const bodyY = Math.min(y(d.open),y(d.close)); const bodyH = Math.max(1.5,Math.abs(y(d.open)-y(d.close))); return <g key={d.timestamp}><title>{d.date}: O {d.open} H {d.high} L {d.low} C {d.close}</title><line x1={x} x2={x} y1={y(d.high)} y2={y(d.low)} stroke={color} strokeWidth="1.2"/><rect x={x-bodyWidth/2} y={bodyY} width={bodyWidth} height={bodyH} fill={color} rx=".5"/></g>; })}
    {average && <polyline points={average} fill="none" stroke="#e9b765" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round"/>}
  </svg>;
}

function Indicator({label,value,note}:{label:string;value:string;note:string}) {
  return <div className="indicator-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}
