import { useEffect, useMemo, useState } from 'react';
import { Check, Clock3, Crown, ExternalLink, ImagePlus, Sparkles, Upload, WalletCards } from 'lucide-react';
import { createBillingCheckout, devCompleteBillingCheckout, getBillingPlans, getBusinessBilling, getBusinessManualPaymentProofs, getManualPaymentMethods, submitManualPaymentProof } from './api';

function moneyLabel(plan) {
  const amount = Number(plan?.price_monthly ?? 1400);
  const currency = String(plan?.currency || 'pkr').toUpperCase();
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount); }
  catch { return `${currency} ${amount.toLocaleString()}`; }
}

export default function BillingPanel({ slug }) {
  const [billing, setBilling] = useState(null);
  const [plans, setPlans] = useState([]);
  const [provider, setProvider] = useState('manual');
  const [changing, setChanging] = useState(false);
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
      setBilling(snapshot); setPlans(catalog?.plans || []); setProvider(catalog?.provider || snapshot?.provider || 'manual');
      setManualMethods(methods?.methods || {}); setManualProofs(proofs?.proofs || []);
      const firstMethod = Object.keys(methods?.methods || {})[0];
      if (firstMethod) setManualForm(prev => ({ ...prev, method: firstMethod }));
      setPendingIntent((snapshot?.checkout_intents || []).find(x => x.status === 'pending') || null); setError('');
    } catch (err) { setError(err.message || 'Could not load billing'); }
  };

  useEffect(() => { load(); }, [slug]);

  const paidPlan = useMemo(() => plans.find(p => p.key === 'starter') || { key:'starter', name:'Ashes', currency:'pkr', price_monthly:1400, features:[] }, [plans]);
  const subscribed = billing?.plan?.key === 'starter' && billing?.status === 'active';
  const trialDays = Number(billing?.trial_days_left || 0);

  const subscribe = async () => {
    if (!slug || subscribed) return;
    setChanging(true); setError('');
    try {
      const intent = await createBillingCheckout(slug, 'starter', window.location.href, window.location.href);
      setPendingIntent(intent);
      if (intent?.checkout_url) window.location.assign(intent.checkout_url);
    } catch (err) { setError(err.message || 'Could not start subscription checkout'); }
    finally { setChanging(false); }
  };

  const devActivate = async () => {
    if (!pendingIntent?.id) return;
    setChanging(true); setError('');
    try { setBilling(await devCompleteBillingCheckout(slug, pendingIntent.id)); setPendingIntent(null); }
    catch (err) { setError(err.message || 'Development activation is disabled'); }
    finally { setChanging(false); }
  };

  const submitManual = async () => {
    if (!manualForm.receipt) return setError('Upload the payment receipt screenshot first.');
    setManualSending(true); setError('');
    try {
      await submitManualPaymentProof(slug, { ...manualForm, plan:'starter' });
      setManualForm(prev => ({ ...prev, transaction_reference:'', note:'', receipt:null }));
      const proofs = await getBusinessManualPaymentProofs(slug); setManualProofs(proofs?.proofs || []);
    } catch (err) { setError(err.message || 'Could not submit payment proof'); }
    finally { setManualSending(false); }
  };

  const enabledManual = Object.entries(manualMethods);

  return <section className="billing-section billing-v2" id="billing">
    <div className="billing-v2-hero">
      <div className="billing-v2-copy">
        <span className="kicker">ASHES MEMBERSHIP</span>
        <h2>One plan. Everything included.</h2>
        <p>Use Ashes free for your first 30 days. After that, keep the entire platform for one simple monthly price — no per-product pricing and no confusing tiers.</p>
        <div className="billing-trust-row"><span><Check size={14}/> 30 days free</span><span><Check size={14}/> Cancel anytime</span><span><Check size={14}/> Full platform access</span></div>
      </div>
      <div className={`billing-status-card ${subscribed ? 'paid' : ''}`}>
        <div className="billing-status-icon">{subscribed ? <Crown size={22}/> : <Clock3 size={22}/>}</div>
        <span>{subscribed ? 'ACTIVE MEMBERSHIP' : billing?.trial_expired ? 'TRIAL ENDED' : 'FREE TRIAL'}</span>
        <strong>{subscribed ? 'Ashes' : `${trialDays} day${trialDays===1?'':'s'} left`}</strong>
        <small>{subscribed ? 'Your workspace is fully active.' : 'Explore everything before your first payment.'}</small>
      </div>
    </div>

    <div className="billing-single-plan">
      <div className="billing-plan-main">
        <div><span>ASHES MONTHLY</span><h3>{moneyLabel(paidPlan)}<small>/month</small></h3><p>Approximately $5/month for international positioning. Your admin can change the billing currency when needed.</p></div>
        <div className="billing-feature-grid">{['3D + AR experiences','Smart QR Studio','Website/catalog import','Customer storefront','Orders OS','Analytics','Warranty/product data','Business themes'].map(f=><span key={f}><Check size={14}/>{f}</span>)}</div>
      </div>
      <button className="primary-btn billing-subscribe-btn" disabled={subscribed || changing} onClick={subscribe}>{subscribed ? 'Membership active' : changing ? 'Opening checkout…' : <>Subscribe to Ashes <Sparkles size={16}/></>}</button>
    </div>

    {pendingIntent && <div className="billing-pending"><div><strong>Subscription checkout pending</strong><span>{provider === 'manual' ? 'Choose Easypaisa/JazzCash below or complete an enabled online checkout.' : 'Finish payment to activate Ashes.'}</span></div>{pendingIntent.checkout_url ? <a className="secondary-btn" href={pendingIntent.checkout_url}><ExternalLink size={14}/> Continue checkout</a> : <button className="secondary-btn" onClick={devActivate}>Dev activate</button>}</div>}
    {error && <div className="form-error">{error}</div>}

    {enabledManual.length > 0 && <section className="manual-payment-box billing-manual-v2">
      <div className="manual-payment-head"><div><WalletCards size={20}/><div><strong>Pay manually</strong><span>Easypaisa or JazzCash receipt → admin approval → Ashes activates.</span></div></div></div>
      <div className="manual-payment-grid">
        <label><span>Payment method</span><select value={manualForm.method} onChange={e=>setManualForm({...manualForm,method:e.target.value})}>{enabledManual.map(([key])=><option value={key} key={key}>{key==='easypaisa'?'Easypaisa':'JazzCash'}</option>)}</select></label>
        <div className="manual-account-card"><span>Send Rs 1,400 to</span><strong>{manualMethods[manualForm.method]?.account_title || 'Ashes AI'}</strong><b>{manualMethods[manualForm.method]?.account_number || 'Set by super-admin'}</b><small>{manualMethods[manualForm.method]?.instructions}</small></div>
        <label><span>Transaction/reference ID</span><input value={manualForm.transaction_reference} onChange={e=>setManualForm({...manualForm,transaction_reference:e.target.value})} placeholder="TXN123456"/></label>
        <label className="receipt-upload"><span>Receipt screenshot</span><input type="file" accept="image/*" onChange={e=>setManualForm({...manualForm,receipt:e.target.files?.[0]||null})}/><div><ImagePlus size={18}/>{manualForm.receipt?.name || 'Choose receipt image'}</div></label>
        <label className="manual-note"><span>Note (optional)</span><input value={manualForm.note} onChange={e=>setManualForm({...manualForm,note:e.target.value})} placeholder="Anything admin should know"/></label>
      </div>
      <button className="primary-btn" disabled={manualSending} onClick={submitManual}><Upload size={15}/>{manualSending?'Submitting…':'Submit Rs 1,400 payment proof'}</button>
      {manualProofs.length>0 && <div className="manual-proof-list"><h4>Recent payments</h4>{manualProofs.slice(0,4).map(item=><article key={item.id}><div><strong>{item.method==='easypaisa'?'Easypaisa':'JazzCash'} · Ashes</strong><span>{item.currency} {Number(item.amount||0).toLocaleString()} · {item.transaction_reference||'No reference'}</span></div><span className={`manual-proof-status ${item.status}`}>{item.status}</span>{item.receipt_url&&<a href={item.receipt_url} target="_blank" rel="noreferrer">Receipt</a>}</article>)}</div>}
    </section>}
  </section>;
}
