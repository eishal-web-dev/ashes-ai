import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowLeft, Ban, Boxes, Building2, Check, CheckCircle2, CircleDollarSign, CreditCard, ExternalLink, RefreshCw, RotateCcw, Save, ShieldCheck, Sparkles, Store, TriangleAlert, X } from 'lucide-react';
import { getAdminBilling, getAdminJobs, getAdminManualPayments, getAdminOverview, reviewAdminManualPayment, setAdminBusinessStatus, updateAdminBillingSettings, updateAdminManualPaymentSettings } from './api';

function Metric({ icon: Icon, label, value, sub }) {
  return <article className="admin-metric glass-panel"><div className="admin-metric-icon"><Icon size={18}/></div><span>{label}</span><strong>{value}</strong><small>{sub}</small></article>;
}

export default function AdminDashboard({ onBack }) {
  const [overview, setOverview] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [billing, setBilling] = useState({ pending_checkouts: [], recent_events: [], settings: null });
  const [manualPayments, setManualPayments] = useState({ settings: { methods: {} }, proofs: [] });
  const [billingForm, setBillingForm] = useState({ currency: 'usd', starter: { price_monthly: 29, enabled: true }, pro: { price_monthly: 79, enabled: true } });
  const [manualForm, setManualForm] = useState({
    easypaisa: { enabled: false, account_title: '', account_number: '', instructions: 'Send payment, then upload the receipt screenshot.' },
    jazzcash: { enabled: false, account_title: '', account_number: '', instructions: 'Send payment, then upload the receipt screenshot.' },
  });
  const [tab, setTab] = useState('businesses');
  const [busyId, setBusyId] = useState('');
  const [savingBilling, setSavingBilling] = useState(false);
  const [savingManual, setSavingManual] = useState(false);
  const [reviewingProof, setReviewingProof] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [nextOverview, nextJobs, nextBilling, nextManual] = await Promise.all([getAdminOverview(), getAdminJobs(), getAdminBilling(), getAdminManualPayments()]);
      setOverview(nextOverview); setJobs(nextJobs?.jobs || []); setBilling(nextBilling || { pending_checkouts: [], recent_events: [], settings: null }); setManualPayments(nextManual || { settings: { methods: {} }, proofs: [] });
      const settings = nextBilling?.settings || nextOverview?.billing_settings;
      if (settings) setBillingForm({
        currency: settings.currency || 'usd',
        starter: { price_monthly: Number(settings.plans?.starter?.price_monthly ?? 29), enabled: settings.plans?.starter?.enabled !== false },
        pro: { price_monthly: Number(settings.plans?.pro?.price_monthly ?? 79), enabled: settings.plans?.pro?.enabled !== false },
      });
      const methods = nextManual?.settings?.methods || {};
      setManualForm({
        easypaisa: { enabled: methods.easypaisa?.enabled === true, account_title: methods.easypaisa?.account_title || '', account_number: methods.easypaisa?.account_number || '', instructions: methods.easypaisa?.instructions || 'Send payment, then upload the receipt screenshot.' },
        jazzcash: { enabled: methods.jazzcash?.enabled === true, account_title: methods.jazzcash?.account_title || '', account_number: methods.jazzcash?.account_number || '', instructions: methods.jazzcash?.instructions || 'Send payment, then upload the receipt screenshot.' },
      });
    } catch (err) {
      setError(err.message || 'Could not load Ashes admin');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const totals = overview?.totals || {};
  const businesses = overview?.businesses || [];
  const planSummary = useMemo(() => overview?.plans || { free: 0, starter: 0, pro: 0 }, [overview]);
  const pendingProofs = (manualPayments.proofs || []).filter(item => item.status === 'pending');

  const changeStatus = async (business, action) => {
    setBusyId(business.id); setError('');
    try {
      const updated = await setAdminBusinessStatus(business.id, action);
      setOverview(prev => ({ ...prev, businesses: (prev?.businesses || []).map(item => item.id === business.id ? { ...item, ...updated } : item) }));
    } catch (err) { setError(err.message || 'Could not update business'); }
    finally { setBusyId(''); }
  };

  const saveBillingSettings = async () => {
    setSavingBilling(true); setError('');
    try {
      const saved = await updateAdminBillingSettings(billingForm);
      setBilling(prev => ({ ...prev, settings: saved }));
      setOverview(prev => ({ ...prev, billing_settings: saved }));
    } catch (err) { setError(err.message || 'Could not save billing settings'); }
    finally { setSavingBilling(false); }
  };

  const saveManualSettings = async () => {
    setSavingManual(true); setError('');
    try {
      const saved = await updateAdminManualPaymentSettings(manualForm);
      setManualPayments(prev => ({ ...prev, settings: saved }));
    } catch (err) { setError(err.message || 'Could not save Easypaisa/JazzCash settings'); }
    finally { setSavingManual(false); }
  };

  const reviewProof = async (proof, action) => {
    const note = window.prompt(action === 'approve' ? 'Approval note (optional)' : 'Reason for rejection (optional)', '') ?? '';
    setReviewingProof(proof.id); setError('');
    try {
      const updated = await reviewAdminManualPayment(proof.id, action, note);
      setManualPayments(prev => ({ ...prev, proofs: (prev.proofs || []).map(item => item.id === proof.id ? updated : item) }));
      if (action === 'approve') await load();
    } catch (err) { setError(err.message || 'Could not review payment proof'); }
    finally { setReviewingProof(''); }
  };

  const updateMethod = (method, field, value) => setManualForm(prev => ({ ...prev, [method]: { ...prev[method], [field]: value } }));

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
        <Metric icon={CreditCard} label="PAID ACCOUNTS" value={totals.paid_businesses || 0} sub={`${totals.pending_checkouts || 0} Stripe pending · ${pendingProofs.length} receipt pending`} />
        <Metric icon={AlertTriangle} label="FAILED 3D" value={totals.failed_3d || 0} sub="Needs attention" />
      </div>

      <div className="admin-tabs"><button className={tab === 'businesses' ? 'active' : ''} onClick={() => setTab('businesses')}>Businesses</button><button className={tab === 'jobs' ? 'active' : ''} onClick={() => setTab('jobs')}>3D Jobs</button><button className={tab === 'billing' ? 'active' : ''} onClick={() => setTab('billing')}>Billing</button></div>

      {loading && <div className="admin-loading glass-panel"><Sparkles size={20}/> Loading platform data…</div>}

      {!loading && tab === 'businesses' && <section className="admin-panel glass-panel"><div className="admin-panel-head"><div><span className="kicker">TENANTS</span><h2>All businesses</h2></div><span>{businesses.length} loaded</span></div><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Business</th><th>Plan</th><th>Products</th><th>Orders</th><th>3D</th><th>Status</th><th>Control</th></tr></thead><tbody>{businesses.map(business => <tr key={business.id}><td><strong>{business.name}</strong><span>@{business.slug}{business.city ? ` · ${business.city}` : ''}</span></td><td><span className={`admin-plan-pill ${business.plan?.key || 'free'}`}>{business.plan?.name || 'Free'}</span></td><td>{business.products}</td><td>{business.orders}<small>Rs {Number(business.order_value || 0).toLocaleString()}</small></td><td><span className={business.failed_3d ? 'admin-danger-text' : ''}>{business.failed_3d} failed</span><small>{business.pending_3d} pending</small></td><td><span className={`admin-status ${business.account_status === 'suspended' ? 'suspended' : 'active'}`}>{business.account_status || 'active'}</span></td><td>{business.account_status === 'suspended' ? <button className="admin-control-btn" disabled={busyId === business.id} onClick={() => changeStatus(business, 'reactivate')}><RotateCcw size={14}/> Reactivate</button> : <button className="admin-control-btn danger" disabled={busyId === business.id} onClick={() => changeStatus(business, 'suspend')}><Ban size={14}/> Suspend</button>}</td></tr>)}</tbody></table></div></section>}

      {!loading && tab === 'jobs' && <section className="admin-panel glass-panel"><div className="admin-panel-head"><div><span className="kicker">GENERATION OPERATIONS</span><h2>3D job health</h2></div><span>{jobs.length} jobs</span></div><div className="admin-job-grid">{jobs.length === 0 && <div className="admin-empty"><CheckCircle2 size={18}/> No pending or failed 3D jobs.</div>}{jobs.map(job => <article className={`admin-job-card ${job.status === 'failed' ? 'failed' : ''}`} key={`${job.product_id}-${job.status}`}><div><strong>{job.name || job.product_id}</strong><span>{job.product_id?.slice(0,8)}</span></div><span className={`admin-status ${job.status === 'failed' ? 'suspended' : 'active'}`}>{job.status}</span>{job.error_message && <p>{job.error_message}</p>}</article>)}</div></section>}

      {!loading && tab === 'billing' && <section className="admin-panel glass-panel"><div className="admin-panel-head"><div><span className="kicker">MONETIZATION OPS</span><h2>Billing & subscription pricing</h2></div><CircleDollarSign size={20}/></div><div className="admin-billing-settings"><label><span>Currency</span><input maxLength="3" value={billingForm.currency} onChange={e => setBillingForm({...billingForm,currency:e.target.value.toLowerCase()})} /></label><label><span>Starter monthly price</span><input type="number" min="0" step="0.01" value={billingForm.starter.price_monthly} onChange={e => setBillingForm({...billingForm,starter:{...billingForm.starter,price_monthly:e.target.value}})} /></label><label className="admin-toggle"><input type="checkbox" checked={billingForm.starter.enabled} onChange={e => setBillingForm({...billingForm,starter:{...billingForm.starter,enabled:e.target.checked}})} /><span>Starter enabled</span></label><label><span>Pro monthly price</span><input type="number" min="0" step="0.01" value={billingForm.pro.price_monthly} onChange={e => setBillingForm({...billingForm,pro:{...billingForm.pro,price_monthly:e.target.value}})} /></label><label className="admin-toggle"><input type="checkbox" checked={billingForm.pro.enabled} onChange={e => setBillingForm({...billingForm,pro:{...billingForm.pro,enabled:e.target.checked}})} /><span>Pro enabled</span></label><button className="primary-btn" disabled={savingBilling} onClick={saveBillingSettings}><Save size={15}/>{savingBilling ? 'Saving…' : 'Save pricing'}</button></div><p className="admin-billing-note">Stripe payments are deposited into the Stripe account that owns the backend STRIPE_SECRET_KEY. Never expose that key in the frontend.</p>

      <div className="manual-admin-settings"><div className="manual-admin-head"><div><span className="kicker">LOCAL PAYMENT METHODS</span><h3>Easypaisa & JazzCash</h3><p>Set the account details restaurants should pay. Their receipt screenshots come to the review queue below.</p></div><button className="secondary-btn" disabled={savingManual} onClick={saveManualSettings}><Save size={14}/>{savingManual ? 'Saving…' : 'Save payment accounts'}</button></div><div className="manual-method-admin-grid">{['easypaisa','jazzcash'].map(method => <article key={method}><label className="admin-toggle"><input type="checkbox" checked={manualForm[method].enabled} onChange={e=>updateMethod(method,'enabled',e.target.checked)}/><span>{method === 'easypaisa' ? 'Easypaisa enabled' : 'JazzCash enabled'}</span></label><label><span>Account title</span><input value={manualForm[method].account_title} onChange={e=>updateMethod(method,'account_title',e.target.value)} placeholder="Ashes AI / Your Name"/></label><label><span>Account number</span><input value={manualForm[method].account_number} onChange={e=>updateMethod(method,'account_number',e.target.value)} placeholder="03xx xxxxxxx"/></label><label><span>Instructions</span><textarea value={manualForm[method].instructions} onChange={e=>updateMethod(method,'instructions',e.target.value)} rows="3"/></label></article>)}</div></div>

      <div className="manual-review-section"><div className="admin-panel-head"><div><span className="kicker">PAYMENT PROOFS</span><h3>Receipt review queue</h3></div><span>{pendingProofs.length} pending</span></div>{(manualPayments.proofs || []).length === 0 && <div className="admin-empty">No Easypaisa/JazzCash receipts yet.</div>}<div className="manual-review-grid">{(manualPayments.proofs || []).map(proof => <article className={`manual-review-card ${proof.status}`} key={proof.id}><div className="manual-review-top"><div><strong>{proof.business_name || proof.business_id}</strong><span>{proof.method === 'easypaisa' ? 'Easypaisa' : 'JazzCash'} · {proof.plan?.toUpperCase()}</span></div><span className={`manual-proof-status ${proof.status}`}>{proof.status}</span></div><div className="manual-review-money"><b>{proof.currency} {Number(proof.amount || 0).toLocaleString()}</b><span>{proof.transaction_reference || 'No transaction reference'}</span></div>{proof.receipt_url && <a className="secondary-btn" href={proof.receipt_url} target="_blank" rel="noreferrer"><ExternalLink size={14}/> View receipt screenshot</a>}{proof.customer_note && <p>{proof.customer_note}</p>}{proof.admin_note && <p className="manual-admin-note">Admin: {proof.admin_note}</p>}{proof.status === 'pending' && <div className="manual-review-actions"><button className="primary-btn" disabled={reviewingProof === proof.id} onClick={()=>reviewProof(proof,'approve')}><Check size={14}/> Approve & activate</button><button className="secondary-btn" disabled={reviewingProof === proof.id} onClick={()=>reviewProof(proof,'reject')}><X size={14}/> Reject</button></div>}</article>)}</div></div>

      <div className="admin-billing-grid"><div><h3>Pending Stripe checkouts</h3>{(billing.pending_checkouts || []).length === 0 && <div className="admin-empty">No pending checkouts.</div>}{(billing.pending_checkouts || []).map(item => <article className="admin-billing-row" key={item.id}><div><strong>{item.plan || 'Plan'}</strong><span>{item.business_id}</span></div><span className="admin-status active">{item.status || 'pending'}</span></article>)}</div><div><h3>Recent billing events</h3>{(billing.recent_events || []).length === 0 && <div className="admin-empty">No billing events yet.</div>}{(billing.recent_events || []).map((item,index) => <article className="admin-billing-row" key={item.id || index}><div><strong>{item.type || item.event_type || 'Billing event'}</strong><span>{item.business_id || item.provider || 'Ashes'}</span></div><span>{item.created_at ? String(item.created_at).slice(0,16).replace('T',' ') : ''}</span></article>)}</div></div></section>}
    </section>
  </main>;
}
