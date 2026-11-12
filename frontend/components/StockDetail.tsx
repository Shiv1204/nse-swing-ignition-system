"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, ComposedChart, Line, Bar, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { ArrowLeft, CircleAlert, LoaderCircle, RefreshCw, TrendingUp } from "lucide-react";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

type BarData = { timestamp: string; open: number; high: number; low: number; close: number; volume: number };
type Indicators = Record<string, number | null>;
type DetailResponse = { symbol: string; bars: BarData[]; latest: Indicators; note?: string };

const fmt = (n?: number | null) => n == null || !Number.isFinite(n) ? "—" : n.toFixed(2);
const rupee = (n?: number | null) => n == null ? "—" : new Intl.NumberFormat("en-IN", {style:"currency",currency:"INR",maximumFractionDigits:2}).format(n);

export default function StockDetail({ symbol, onBack }: { symbol: string; onBack: () => void }) {
  const [data, setData] = useState<DetailResponse | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

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
      // Display a 20-day simple average overlay as a visual guide; backend EMA values remain in the indicator cards.
      setData({ symbol, bars: chart as BarData[], latest, note: indicatorPayload.note });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load stock detail");
      setData(null);
    } finally { setBusy(false); }
  };

  useEffect(() => { void load(); }, [symbol]);

  const last = data?.bars[data.bars.length - 1];
  const previous = data?.bars[data.bars.length - 2];
  const change = last && previous ? ((last.close / previous.close) - 1) * 100 : null;
  const chartData = useMemo(() => data?.bars.map((bar, index, all) => ({
    ...bar,
    ema20: index >= 19 ? all.slice(index - 19, index + 1).reduce((sum, item) => sum + item.close, 0) / 20 : null,
  })) || [], [data]);

  return <div className="stock-detail">
    <div className="detail-toolbar">
      <button className="button secondary" onClick={onBack}><ArrowLeft size={15}/> Back to scanner</button>
      <button className="button secondary" onClick={() => void load()} disabled={busy}>{busy ? <LoaderCircle className="spin" size={15}/> : <RefreshCw size={15}/>} Refresh data</button>
    </div>
    {busy && <div className="detail-loading"><LoaderCircle className="spin" size={22}/> Loading {symbol} daily history and indicators…</div>}
    {error && <div className="notice error"><CircleAlert size={18}/><div><b>Stock data unavailable</b><p>{error}</p></div></div>}
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
        <div className="card-head"><div><div className="eyebrow">PRICE ACTION</div><h2>Daily close & trend reference</h2></div><span className="chart-legend"><i/> Close <i className="legend-ema"/> 20-day average</span></div>
        <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{top:10,right:12,left:0,bottom:0}}>
          <CartesianGrid stroke="#263548" strokeDasharray="3 3" vertical={false}/>
          <XAxis dataKey="date" tick={{fill:"#8091a8",fontSize:10}} minTickGap={35} axisLine={{stroke:"#34465c"}} tickLine={false}/>
          <YAxis domain={["auto","auto"]} tick={{fill:"#8091a8",fontSize:10}} axisLine={false} tickLine={false} width={58}/>
          <Tooltip contentStyle={{background:"#101b29",border:"1px solid #34465c",borderRadius:8,color:"#e8eef7",fontSize:11}}/>
          <Line type="monotone" dataKey="close" name="Close" stroke="#76aaff" dot={false} strokeWidth={2}/>
          <Line type="monotone" dataKey="ema20" name="20-day average" stroke="#e9b765" dot={false} strokeWidth={1.5}/>
        </ComposedChart></ResponsiveContainer></div>
      </div>
      <div className="panel-card volume-panel">
        <div className="card-head"><div><div className="eyebrow">PARTICIPATION</div><h2>Daily traded volume</h2></div><span className="volume-latest">{last?.volume.toLocaleString("en-IN") ?? "—"} shares</span></div>
        <div className="volume-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{top:5,right:12,left:0,bottom:0}}><CartesianGrid stroke="#263548" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" tick={{fill:"#8091a8",fontSize:10}} minTickGap={35} axisLine={{stroke:"#34465c"}} tickLine={false}/><YAxis tick={{fill:"#8091a8",fontSize:10}} axisLine={false} tickLine={false} width={58}/><Tooltip contentStyle={{background:"#101b29",border:"1px solid #34465c",borderRadius:8,color:"#e8eef7",fontSize:11}}/><Bar dataKey="volume" name="Volume" fill="#477fbd" opacity={0.75}/></ComposedChart></ResponsiveContainer></div>
      </div>
      <div className="notice warning"><TrendingUp size={17}/><div><b>Indicator interpretation</b><p>Indicators describe historical price and volume behaviour; they are not trade instructions. The trend line shown is a 20-day simple average for chart reference. EMA values above are calculated by the backend.</p></div></div>
    </>}
  </div>;
}

function Indicator({label,value,note}:{label:string;value:string;note:string}) {
  return <div className="indicator-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}
