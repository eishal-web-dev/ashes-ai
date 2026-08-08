import { useEffect, useMemo, useState } from 'react';
import { Check, Crown, ExternalLink, ImagePlus, Sparkles, Upload, WalletCards, Zap } from 'lucide-react';
import { createBillingCheckout, devCompleteBillingCheckout, getBillingPlans, getBusinessBilling, getBusinessManualPaymentProofs, getManualPaymentMethods, submitManualPaymentProof } from './api';

const resourceLabels = {
  products: 'Products',
  ai_generations: 'AI generations',
  menu_imports: 'Menu imports',
  table_qrs: 'Table QRs',
};

function UsageRow({ label, value, limit }) {
  const percentage = limit ? Math.min(100, Math.round((value / limit) * 100)) : 0;
  return <div className="billing-usage-row">
    <div className="billing-usage-copy"><span>{label}</span><strong>{value} / {limit}</strong></div>
    <div className="billing-meter"><span style={{ width: `${percentage}%` }} /></div>
  </div>;
}

function moneyLabel(plan) {
  const amount = Number(plan?.price_monthly ?? plan?.price_monthly_usd ?? 0);
  const currency = String(plan?.currency || 'usd').toUpperCase();
  if (amount === 0) return '$0';
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount); }
  catch { return `${currency} ${amount.toFixed(2)}`; }
}

export default function BillingPanel({ slug }) {
  const [billing, setBilling] = useState(null);
  const [plans, setPlans] = useState([]);
  const [provider, setProvider] = useState('manual');
  const [changing, setChanging] = useState('');
  const [pendingIntent, setPendingIntent] = useState(null);
  const [manualMethods, setManualMethods] = useState({});
  const [manualProofs, setManualProofs] = useState([]);
  const [manualForm, setManualForm] = useState({ plan: 'starter', method: 'easypaisa', transaction_reference: '', note: '', receipt: null });
  const [manualSending, setManualSending] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    if (!slug) return;
    try {
      const [snapshot, catalog, methods, proofs] = await Promise.all([
        getBusinessBilling(slug), getBillingPlans(), getManualPaymentMethods(), getBusinessManualPaymentProofs(slug),
      ]);
      setBilling(snapshot);
      setPlans(catalog?.plans || []);
      setProvider(catalog?.provider || snapshot?.provider || 'manual');
      setManualMethods(methods?.methods || {});
      setManualProofs(proofs?.proofs || []);
      const firstMethod = Object.keys(methods?.methods || {})[0];
      if (firstMethod) setManualForm(prev => ({ ...prev, method: firstMethod }));
      const pending = (snapshot?.checkout_intents || []).find(intent => intent.status === 'pending');
      setPendingIntent(pending || null);
      setError('');
    } catch (err) { setError(err.message || 'Could not load billing'); }
  };

  useEffect(() => { load(); }, [slug]);

  const currentKey = billing?.plan?.key || 'free';
  const usageRows = useMemo(() => {
    if (!billing) return [];
    return Object.entries(resourceLabels).map(([key, label]) => ({ key, label, value: Number(billing.usage?.[key] || 0), limit: Number(billing.limits?.[key] || 0) }));
  }, [billing]);

  const choosePlan = async plan => {
    if (!slug || plan === currentKey || plan === 'free') return;
    setChanging(plan); setError('');
    try {
      const intent = await createBillingCheckout(slug, plan, window.location.href, window.location.href);
      setPendingIntent(intent);
      if (intent?.checkout_url) window.location.assign(intent.checkout_url);
    } catch (err) { setError(err.message || 'Could not start checkout'); }
    finally { setChanging(''); }
  };

  const devActivate = async () => {
    if (!pendingIntent?.id) return;
    setChanging(pendingIntent.plan); setError('');
    try {
      const snapshot = await devCompleteBillingCheckout(slug, pendingIntent.id);
      setBilling(snapshot); setPendingIntent(null);
    } catch (err) { setError(err.message || 'Development activation is disabled'); }
    finally { setChanging(''); }
  };

  const submitManual = async () => {
    if (!manualForm.receipt) { setError('Upload the payment receipt screenshot first.'); return; }
    setManualSending(true); setError('');
    try {
      await submitManualPaymentProof(slug, manualForm);
      setManualForm(prev => ({ ...prev, transaction_reference: '', note: '', receipt: null }));
      const proofs = await getBusinessManualPaymentProofs(slug);
      setManualProofs(proofs?.proofs || []);
    } catch (err) { setError(err.message || 'Could not submit payment proof'); }
    finally { setManualSending(false); }
  };

  const enabledManual = Object.entries(manualMethods);

  return <section className="billing-section glass-panel" id="billing">
    <div className="billing-heading">
      <div><span className="kicker">ASHES SUBSCRIPTION</span><h2>Plan & usage</h2><p>Use Stripe for automatic recurring billing, or submit an Easypaisa/JazzCash receipt for admin review.</p></div>
      <div className="current-plan-badge"><Crown size={16}/><span>{billing?.plan?.name || 'Free'}</span><small>{billing?.status || 'active'}</small></div>
    </div>

    {billing && <div className="billing-usage-grid">{usageRows.map(row => <UsageRow key={row.key} {...row} />)}</div>}
    {pendingIntent && <div className="billing-pending"><div><strong>{pendingIntent.plan?.toUpperCase()} checkout pending</strong><span>{provider === 'manual' ? 'Payment provider is not connected yet. The plan has not been activated.' : 'Complete payment to activate this plan.'}</span></div>{pendingIntent.checkout_url ? <a className="secondary-btn" href={pendingIntent.checkout_url}><ExternalLink size={14}/> Continue checkout</a> : <button className="secondary-btn" onClick={devActivate}>Dev activate</button>}</div>}
    {error && <div className="form-error">{error}</div>}

    <div className="plan-grid">
      {plans.map(plan => {
        const active = plan.key === currentKey;
        const featured = plan.key === 'starter';
        const pending = pendingIntent?.plan === plan.key && pendingIntent?.status === 'pending';
        const disabled = plan.enabled === false;
        return <article key={plan.key} className={`plan-card ${active ? 'active' : ''} ${featured ? 'featured' : ''}`}>
          <div className="plan-card-top"><div><span>{plan.name}</span><strong>{moneyLabel(plan)}<small>/mo</small></strong></div>{featured && <Zap size={18}/>}</div>
          <div className="plan-limits"><span>{plan.product_limit} products</span><span>{plan.ai_generations_monthly} AI generations / month</span><span>{plan.menu_imports_monthly} menu imports / month</span><span>{plan.table_qr_limit} table QRs</span></div>
          <div className="plan-features">{(plan.features || []).map(feature => <div key={feature}><Check size={14}/><span>{feature}</span></div>)}</div>
          <button className={active ? 'secondary-btn wide' : 'primary-btn wide'} disabled={active || plan.key === 'free' || changing === plan.key || pending || disabled} onClick={() => choosePlan(plan.key)}>
            {active ? 'Current plan' : plan.key === 'free' ? 'Free tier' : disabled ? 'Plan unavailable' : pending ? 'Checkout pending' : changing === plan.key ? 'Creating checkout…' : <>Pay by Stripe <Sparkles size={15}/></>}
          </button>
        </article>;
      })}
    </div>

    {enabledManual.length > 0 && <section className="manual-payment-box">
      <div className="manual-payment-head"><div><WalletCards size={19}/><div><strong>Pay with Easypaisa / JazzCash</strong><span>Send payment to the account below, then upload the receipt screenshot. Your plan activates after admin approval.</span></div></div></div>
      <div className="manual-payment-grid">
        <label><span>Plan</span><select value={manualForm.plan} onChange={e=>setManualForm({...manualForm,plan:e.target.value})}><option value="starter">Starter</option><option value="pro">Pro</option></select></label>
        <label><span>Payment method</span><select value={manualForm.method} onChange={e=>setManualForm({...manualForm,method:e.target.value})}>{enabledManual.map(([key]) => <option value={key} key={key}>{key === 'easypaisa' ? 'Easypaisa' : 'JazzCash'}</option>)}</select></label>
        <div className="manual-account-card"><span>Send payment to</span><strong>{manualMethods[manualForm.method]?.account_title || 'Ashes AI'}</strong><b>{manualMethods[manualForm.method]?.account_number || 'Account number set by admin'}</b><small>{manualMethods[manualForm.method]?.instructions}</small></div>
        <label><span>Transaction/reference ID</span><input value={manualForm.transaction_reference} onChange={e=>setManualForm({...manualForm,transaction_reference:e.target.value})} placeholder="e.g. TXN123456" /></label>
        <label><span>Note (optional)</span><input value={manualForm.note} onChange={e=>setManualForm({...manualForm,note:e.target.value})} placeholder="Business/payment note" /></label>
        <label className="receipt-upload"><span>Receipt screenshot</span><input type="file" accept="image/*" onChange={e=>setManualForm({...manualForm,receipt:e.target.files?.[0] || null})}/><div><ImagePlus size={18}/>{manualForm.receipt?.name || 'Choose receipt image'}</div></label>
      </div>
      <button className="primary-btn" disabled={manualSending} onClick={submitManual}><Upload size={15}/>{manualSending ? 'Submitting…' : 'Submit payment proof'}</button>
      {manualProofs.length > 0 && <div className="manual-proof-list"><h4>Your payment proofs</h4>{manualProofs.slice(0,5).map(item => <article key={item.id}><div><strong>{item.method === 'easypaisa' ? 'Easypaisa' : 'JazzCash'} · {item.plan}</strong><span>{item.currency} {Number(item.amount || 0).toLocaleString()} · {item.transaction_reference || 'No reference'}</span></div><span className={`manual-proof-status ${item.status}`}>{item.status}</span>{item.receipt_url && <a href={item.receipt_url} target="_blank" rel="noreferrer">View receipt</a>}</article>)}</div>}
    </section>}
  </section>;
}
