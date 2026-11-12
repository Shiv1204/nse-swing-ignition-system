"use client";

import { useCallback, useEffect, useState } from "react";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
type Portfolio = { initial_capital:number; cash:number; realized_pnl:number; market_value?:number; unrealized_pnl?:number; estimated_equity?:number; total_pnl_including_unrealized?:number; open_positions:{symbol:string;quantity:number;average_price:number;updated_at:string;market_price?:number|null;unrealized_pnl?:number|null}[]; recent_orders:{id:number;symbol:string;side:string;quantity:number;fill_price:number;realized_pnl:number;created_at:string}[]; warning:string };

export default function PaperTradingPage() {
  const [portfolio,setPortfolio]=useState<Portfolio|null>(null);
  const [symbol,setSymbol]=useState("RELIANCE");
  const [side,setSide]=useState<"buy"|"sell">("buy");
  const [quantity,setQuantity]=useState("1");
  const [price,setPrice]=useState("");
  const [capital,setCapital]=useState("1000000");
  const [note,setNote]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const refresh=useCallback(async()=>{
    const response=await fetch(`${API}/api/v1/paper-trading/portfolio?initial_capital=${capital}`,{cache:"no-store"});
    const data=await response.json(); if(!response.ok) throw new Error(data.detail||"Could not load paper portfolio"); setPortfolio(data);
  },[capital]);
  useEffect(()=>{void refresh().catch(e=>setMessage(e.message));},[refresh]);
  const submit=async()=>{
    setBusy(true);setMessage("");
    try {
      const response=await fetch(`${API}/api/v1/paper-trading/orders`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol,side,quantity:Number(quantity),assumed_fill_price:Number(price),initial_capital:Number(capital),note})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"Paper order failed");
      setMessage(`Paper ${side} recorded: ${data.quantity} ${data.symbol} @ ₹${data.assumed_fill_price}`);await refresh();
    } catch(e){setMessage(e instanceof Error?e.message:"Paper order failed");} finally{setBusy(false);}
  };
  return <main style={{minHeight:"100vh",background:"#080d16",color:"#e7edf7",padding:"32px",fontFamily:"Arial,sans-serif"}}>
    <div style={{maxWidth:1100,margin:"0 auto"}}>
      <a href="/" style={{color:"#8da7cc",textDecoration:"none"}}>← Back to dashboard</a>
      <h1 style={{marginBottom:4}}>Paper trading ledger</h1>
      <p style={{color:"#9aabc3"}}>Manual simulated cash-equity trades only. No broker connection or live orders.</p>
      {portfolio&&<section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(170px,1fr))",gap:12,margin:"24px 0"}}>
        {[["Initial capital",portfolio.initial_capital],["Available cash",portfolio.cash],["Market value",portfolio.market_value ?? 0],["Unrealized P&L",portfolio.unrealized_pnl ?? 0],["Estimated equity",portfolio.estimated_equity ?? portfolio.cash],["Total P&L",portfolio.total_pnl_including_unrealized ?? portfolio.realized_pnl],["Open positions",portfolio.open_positions.length]].map(([label,value])=><div key={String(label)} style={{background:"#111a29",border:"1px solid #253247",borderRadius:12,padding:18}}><small style={{color:"#9aabc3"}}>{label}</small><h2 style={{margin:"8px 0"}}>{typeof value==="number"&&label!=="Open positions"?`₹${value.toLocaleString("en-IN",{maximumFractionDigits:2})}`:value}</h2></div>)}
      </section>}
      <section style={{background:"#111a29",border:"1px solid #253247",borderRadius:12,padding:20}}>
        <h2>Record simulated order</h2>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(150px,1fr))",gap:12}}>
          <label>Symbol<input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} style={inputStyle}/></label>
          <label>Side<select value={side} onChange={e=>setSide(e.target.value as "buy"|"sell")} style={inputStyle}><option value="buy">Buy</option><option value="sell">Sell</option></select></label>
          <label>Quantity<input type="number" min="1" value={quantity} onChange={e=>setQuantity(e.target.value)} style={inputStyle}/></label>
          <label>Assumed fill price (₹)<input type="number" min="0.01" step="0.01" value={price} onChange={e=>setPrice(e.target.value)} style={inputStyle}/></label>
          <label>Initial capital (₹)<input type="number" min="1" value={capital} onChange={e=>setCapital(e.target.value)} style={inputStyle}/></label>
          <label>Note<input value={note} onChange={e=>setNote(e.target.value)} style={inputStyle}/></label>
        </div>
        <button disabled={busy||!symbol||Number(quantity)<=0||Number(price)<=0} onClick={()=>void submit()} style={{marginTop:16,padding:"11px 18px",border:0,borderRadius:8,background:"#3977df",color:"white",fontWeight:700,opacity:busy?.6:1}}>{busy?"Recording…":`Record paper ${side}`}</button>
        {message&&<p role="status" style={{color:"#b9d2ff"}}>{message}</p>}
      </section>
      {portfolio&&<><section style={{marginTop:22}}><h2>Open positions</h2><DataTable headers={["Symbol","Quantity","Average price","Latest close","Unrealized P&L"]} rows={portfolio.open_positions.map(p=>[p.symbol,p.quantity,`₹${p.average_price.toFixed(2)}`,p.market_price == null ? "—" : `₹${p.market_price.toFixed(2)}`,p.unrealized_pnl == null ? "—" : `₹${p.unrealized_pnl.toFixed(2)}`])}/></section>
      <section style={{marginTop:22}}><h2>Recent paper orders</h2><DataTable headers={["Symbol","Side","Quantity","Assumed fill","Realized P&L"]} rows={portfolio.recent_orders.map(o=>[o.symbol,o.side.toUpperCase(),o.quantity,`₹${o.fill_price.toFixed(2)}`,`₹${o.realized_pnl.toFixed(2)}`])}/></section>
      <p style={{color:"#9aabc3",fontSize:12,lineHeight:1.6}}>{portfolio.warning}</p></>}
    </div>
  </main>;
}
const inputStyle:React.CSSProperties={display:"block",width:"100%",boxSizing:"border-box",marginTop:6,padding:10,background:"#0a1220",border:"1px solid #34445d",borderRadius:7,color:"#e7edf7"};
function DataTable({headers,rows}:{headers:string[];rows:(string|number)[][]}){return <div style={{overflowX:"auto",background:"#111a29",border:"1px solid #253247",borderRadius:10}}><table style={{width:"100%",borderCollapse:"collapse",textAlign:"left"}}><thead><tr>{headers.map(h=><th key={h} style={{padding:12,color:"#9aabc3"}}>{h}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{row.map((cell,j)=><td key={j} style={{padding:12,borderTop:"1px solid #253247"}}>{cell}</td>)}</tr>)}</tbody></table>{!rows.length&&<p style={{padding:12,color:"#9aabc3"}}>No records yet.</p>}</div>}
