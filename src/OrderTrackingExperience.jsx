import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Check, ChefHat, CircleDot, Clock3, PackageCheck, ReceiptText, RefreshCw, ShoppingBag, Sparkles, Store, UtensilsCrossed } from 'lucide-react';
import { getOrder, getProductBusiness } from './api';

const STEPS = [
  { id: 'new', label: 'Received', icon: ReceiptText, text: 'Your order reached the business.' },
  { id: 'accepted', label: 'Confirmed', icon: Check, text: 'The business confirmed your order.' },
  { id: 'preparing', label: 'Preparing', icon: ChefHat, text: 'Your items are being prepared.' },
  { id: 'ready', label: 'Ready', icon: PackageCheck, text: 'Your order is ready for the next step.' },
  { id: 'served', label: 'Completed', icon: Sparkles, text: 'Order completed. Enjoy!' },
];

function statusCopy(status) {
  if (status === 'accepted') return ['Order confirmed', 'Everything is confirmed and queued.'];
  if (status === 'preparing') return ['It’s being prepared', 'The business is working on your order now.'];
  if (status === 'ready') return ['Your order is ready', 'You’re up — your order has reached the ready stage.'];
  if (status === 'served') return ['Order complete', 'Thanks for ordering through Ashes.'];
  if (status === 'cancelled') return ['Order cancelled', 'This order was cancelled by the business.'];
  return ['Order received', 'The business has your order and will confirm it shortly.'];
}

export default function OrderTrackingExperience({ orderId, onBack, onBackToStore }) {
  const [order, setOrder] = useState(null);
  const [business, setBusiness] = useState(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    if (!orderId) return;
    setRefreshing(true);
    try {
      const next = await getOrder(orderId);
      setOrder(next); setError('');
      const firstProductId = next?.items?.[0]?.product_id;
      if (firstProductId && !business) {
        try { setBusiness(await getProductBusiness(firstProductId)); } catch {}
      }
    } catch (e) { setError(e?.message || 'Could not load this order.'); }
    finally { setRefreshing(false); }
  };

  useEffect(() => { load(); }, [orderId]);
  useEffect(() => {
    if (!orderId || ['served','cancelled'].includes(order?.status)) return;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [orderId, order?.status]);

  const activeIndex = useMemo(() => Math.max(0, STEPS.findIndex(s => s.id === order?.status)), [order?.status]);
  const [headline, subline] = statusCopy(order?.status);
  const accent = business?.accent_color || '#ff2f9f';
  const totalQty = (order?.items || []).reduce((n, item) => n + Number(item.quantity || 0), 0);
  const initial = (business?.name || 'A').slice(0,1).toUpperCase();

  return <main className="track-page" style={{'--business-accent':accent}}>
    <div className="track-glow"/><div className="track-grid-bg"/>
    <header className="track-topbar">
      <button className="track-icon-btn" onClick={onBack}><ArrowLeft size={18}/></button>
      <div className="track-brand"><div>{initial}</div><span><strong>{business?.name || 'Ashes Order'}</strong><small>LIVE ORDER TRACKING</small></span></div>
      <button className="track-refresh" onClick={load}><RefreshCw size={15} className={refreshing?'spin-icon':''}/> Refresh</button>
    </header>

    <section className="track-wrap">
      {error && <div className="track-error">{error}</div>}
      {!order && !error ? <div className="track-loading"><RefreshCw className="spin-icon"/><span>Loading your order…</span></div> : order && <>
        <div className="track-hero">
          <span className="track-kicker"><CircleDot size={12}/> LIVE · ORDER #{order.id?.slice(0,8).toUpperCase()}</span>
          <h1>{headline}</h1>
          <p>{subline}</p>
          <div className={`track-status-pill ${order.status}`}><i/><span>{String(order.status || 'new').replace('_',' ')}</span></div>
        </div>

        <div className="track-layout">
          <section className="track-main-card">
            <div className="track-progress-head"><div><span>ORDER JOURNEY</span><h2>Follow every step</h2></div><Clock3 size={22}/></div>
            <div className="track-timeline">
              {STEPS.map((step,index)=>{const Icon=step.icon;const done=index<activeIndex || order.status==='served';const current=index===activeIndex && order.status!=='cancelled';return <div className={`track-step ${done?'done':''} ${current?'current':''}`} key={step.id}><div className="track-step-marker">{done?<Check size={16}/>:<Icon size={16}/>}</div><div><strong>{step.label}</strong><span>{step.text}</span></div>{current&&<b>NOW</b>}</div>})}
            </div>
            {order.status==='cancelled'&&<div className="track-cancelled">This order was cancelled. Please contact the business if you need help.</div>}
          </section>

          <aside className="track-summary">
            <div className="track-summary-title"><ShoppingBag size={18}/><div><span>YOUR ORDER</span><strong>{totalQty} item{totalQty===1?'':'s'}</strong></div></div>
            <div className="track-items">{(order.items||[]).map((item,i)=><div className="track-item" key={`${item.product_id}-${i}`}><div><b>{item.quantity}×</b><span><strong>{item.product_name}</strong><small>Rs {Number(item.unit_price||0).toLocaleString()} each</small></span></div><strong>Rs {Number(item.line_total||0).toLocaleString()}</strong></div>)}</div>
            <div className="track-meta">{order.table_code&&<div><span><UtensilsCrossed size={14}/> Table</span><b>{order.table_code}</b></div>}{order.customer_name&&<div><span><Store size={14}/> Name</span><b>{order.customer_name}</b></div>}<div className="track-total"><span>Total</span><strong>Rs {Number(order.total||0).toLocaleString()}</strong></div></div>
            <button className="track-store-btn" onClick={()=>onBackToStore?.(business)}><Store size={17}/> Back to {business?.name || 'store'}</button>
          </aside>
        </div>
        <div className="track-powered">POWERED BY <strong>ASHES AI</strong> · THIS PAGE UPDATES AUTOMATICALLY</div>
      </>}
    </section>
  </main>;
}
