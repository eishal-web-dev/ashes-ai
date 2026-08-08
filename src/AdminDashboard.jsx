import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowLeft, Ban, Boxes, Building2, CheckCircle2, CircleDollarSign, CreditCard, RefreshCw, RotateCcw, ShieldCheck, Sparkles, Store, TriangleAlert } from 'lucide-react';
import { getAdminBilling, getAdminJobs, getAdminOverview, setAdminBusinessStatus } from './api';

function Metric({ icon: Icon, label, value, sub }) {
  return <article className="admin-metric glass-panel"><div className="admin-metric-icon"><Icon size={18}/></div><span>{label}</span><strong>{value}</strong><small>{sub}</small></article>;
}

export default function AdminDashboard({ onBack }) {
  const [overview, setOverview] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [billing, setBilling] = useState({ pending_checkouts: [], recent_events: [] });
  const [tab, setTab] = useState('businesses');
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [nextOverview, nextJobs, nextBilling] = await Promise.all([getAdminOverview(), getAdminJobs(), getAdminBilling()]);
      setOverview(nextOverview); setJobs(nextJobs?.jobs || []); setBilling(nextBilling || { pending_checkouts: [], recent_events: [] });
    } catch (err) {
      setError(err.message || 'Could not load Ashes admin');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const totals = overview?.totals || {};
  const businesses = overview?.businesses || [];
  const planSummary = useMemo(() => overview?.plans || { free: 0, starter: 0, pro: 0 }, [overview]);

  const changeStatus = async (business, action) => {
    setBusyId(business.id); setError('');
    try {
      const updated = await setAdminBusinessStatus(business.id, action);
      setOverview(prev => ({ ...prev, businesses: (prev?.businesses || []).map(item => item.id === business.id ? { ...item, ...updated } : item) }));
    } catch (err) { setError(err.message || 'Could not update business'); }
    finally { setBusyId(''); }
  };

  return <main className="admin-shell">
    <div className="noise" />
    <header className="admin-topbar container">
      <div className="admin-brand"><div className="brand"><span>ASHES</span><b>ADMIN</b></div><span><ShieldCheck size={14}/> CONTROL CENTER</span></div>
      <div className="admin-top-actions"><button className="secondary-btn" onClick={load} disabled={loading}><RefreshCw size={15}/> Refresh</button><button className="secondary-btn" onClick={onBack}><ArrowLeft size={15}/> Back</button></div>
    </header>

    <section className="admin-main container">
      <div className="admin-hero"><div><span className="kicker">PLATFORM COMMAND</span><h1>Ashes Super Admin</h1><p>Monitor businesses, subscriptions, AI generation health and platform activity from one place.</p></div><div className="admin-plan-mini"><span>Free <b>{planSummary.free || 0}</b></span><span>Starter <b>{planSummary.starter || 0}</b></span><span>Pro <b>{planSummary.pro || 0}</b></span></div></div>

      {error && <div className="admin-error"><TriangleAlert size={16}/>{error}</div>}

      <div className="admin-metric-grid">
        <Metric icon={Building2} label="BUSINESSES" value={totals.businesses || 0} sub={`${totals.active_businesses || 0} active`} />
        <Metric icon={Boxes} label="PRODUCTS" value={totals.products || 0} sub={`${totals.pending_3d || 0} pending 3D`} />
        <Metric icon={Store} label="ORDERS" value={totals.orders || 0} sub={`Rs ${Number(totals.gross_order_value || 0).toLocaleString()}`} />
        <Metric icon={CreditCard} label="PAID ACCOUNTS" value={totals.paid_businesses || 0} sub={`${totals.pending_checkouts || 0} pending checkouts`} />
        <Metric icon={AlertTriangle} label="FAILED 3D" value={totals.failed_3d || 0} sub="Needs attention" />
      </div>

      <div className="admin-tabs"><button className={tab === 'businesses' ? 'active' : ''} onClick={() => setTab('businesses')}>Businesses</button><button className={tab === 'jobs' ? 'active' : ''} onClick={() => setTab('jobs')}>3D Jobs</button><button className={tab === 'billing' ? 'active' : ''} onClick={() => setTab('billing')}>Billing</button></div>

      {loading && <div className="admin-loading glass-panel"><Sparkles size={20}/> Loading platform data…</div>}

      {!loading && tab === 'businesses' && <section className="admin-panel glass-panel"><div className="admin-panel-head"><div><span className="kicker">TENANTS</span><h2>All businesses</h2></div><span>{businesses.length} loaded</span></div><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Business</th><th>Plan</th><th>Products</th><th>Orders</th><th>3D</th><th>Status</th><th>Control</th></tr></thead><tbody>{businesses.map(business => <tr key={business.id}><td><strong>{business.name}</strong><span>@{business.slug}{business.city ? ` · ${business.city}` : ''}</span></td><td><span className={`admin-plan-pill ${business.plan?.key || 'free'}`}>{business.plan?.name || 'Free'}</span></td><td>{business.products}</td><td>{business.orders}<small>Rs {Number(business.order_value || 0).toLocaleString()}</small></td><td><span className={business.failed_3d ? 'admin-danger-text' : ''}>{business.failed_3d} failed</span><small>{business.pending_3d} pending</small></td><td><span className={`admin-status ${business.account_status === 'suspended' ? 'suspended' : 'active'}`}>{business.account_status || 'active'}</span></td><td>{business.account_status === 'suspended' ? <button className="admin-control-btn" disabled={busyId === business.id} onClick={() => changeStatus(business, 'reactivate')}><RotateCcw size={14}/> Reactivate</button> : <button className="admin-control-btn danger" disabled={busyId === business.id} onClick={() => changeStatus(business, 'suspend')}><Ban size={14}/> Suspend</button>}</td></tr>)}</tbody></table></div></section>}

      {!loading && tab === 'jobs' && <section className="admin-panel glass-panel"><div className="admin-panel-head"><div><span className="kicker">GENERATION OPERATIONS</span><h2>3D job health</h2></div><span>{jobs.length} jobs</span></div><div className="admin-job-grid">{jobs.length === 0 && <div className="admin-empty"><CheckCircle2 size={18}/> No pending or failed 3D jobs.</div>}{jobs.map(job => <article className={`admin-job-card ${job.status === 'failed' ? 'failed' : ''}`} key={`${job.product_id}-${job.status}`}><div><strong>{job.name || job.product_id}</strong><span>{job.product_id?.slice(0,8)}</span></div><span className={`admin-status ${job.status === 'failed' ? 'suspended' : 'active'}`}>{job.status}</span>{job.error_message && <p>{job.error_message}</p>}</article>)}</div></section>}

      {!loading && tab === 'billing' && <section className="admin-panel glass-panel"><div className="admin-panel-head"><div><span className="kicker">MONETIZATION OPS</span><h2>Billing activity</h2></div><CircleDollarSign size={20}/></div><div className="admin-billing-grid"><div><h3>Pending checkouts</h3>{(billing.pending_checkouts || []).length === 0 && <div className="admin-empty">No pending checkouts.</div>}{(billing.pending_checkouts || []).map(item => <article className="admin-billing-row" key={item.id}><div><strong>{item.plan || item.plan_key || 'Plan'}</strong><span>{item.business_id}</span></div><span className="admin-status active">{item.status || 'pending'}</span></article>)}</div><div><h3>Recent billing events</h3>{(billing.recent_events || []).length === 0 && <div className="admin-empty">No billing events yet.</div>}{(billing.recent_events || []).map((item,index) => <article className="admin-billing-row" key={item.id || index}><div><strong>{item.type || item.event_type || 'Billing event'}</strong><span>{item.business_id || item.provider || 'Ashes'}</span></div><span>{item.created_at ? String(item.created_at).slice(0,16).replace('T',' ') : ''}</span></article>)}</div></div></section>}
    </section>
  </main>;
}
