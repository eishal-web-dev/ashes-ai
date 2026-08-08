import { useEffect, useMemo, useState } from 'react';
import { Check, Crown, ExternalLink, Sparkles, Zap } from 'lucide-react';
import { createBillingCheckout, devCompleteBillingCheckout, getBillingPlans, getBusinessBilling } from './api';

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
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

export default function BillingPanel({ slug }) {
  const [billing, setBilling] = useState(null);
  const [plans, setPlans] = useState([]);
  const [provider, setProvider] = useState('manual');
  const [changing, setChanging] = useState('');
  const [pendingIntent, setPendingIntent] = useState(null);
  const [error, setError] = useState('');

  const load = async () => {
    if (!slug) return;
    try {
      const [snapshot, catalog] = await Promise.all([getBusinessBilling(slug), getBillingPlans()]);
      setBilling(snapshot);
      setPlans(catalog?.plans || []);
      setProvider(catalog?.provider || snapshot?.provider || 'manual');
      const pending = (snapshot?.checkout_intents || []).find(intent => intent.status === 'pending');
      setPendingIntent(pending || null);
      setError('');
    } catch (err) {
      setError(err.message || 'Could not load billing');
    }
  };

  useEffect(() => { load(); }, [slug]);

  const currentKey = billing?.plan?.key || 'free';
  const usageRows = useMemo(() => {
    if (!billing) return [];
    return Object.entries(resourceLabels).map(([key, label]) => ({
      key, label, value: Number(billing.usage?.[key] || 0), limit: Number(billing.limits?.[key] || 0),
    }));
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

  return <section className="billing-section glass-panel" id="billing">
    <div className="billing-heading">
      <div><span className="kicker">ASHES SUBSCRIPTION</span><h2>Plan & usage</h2><p>Usage limits protect AI generation costs. Paid upgrades activate only after successful payment confirmation.</p></div>
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
            {active ? 'Current plan' : plan.key === 'free' ? 'Free tier' : disabled ? 'Plan unavailable' : pending ? 'Checkout pending' : changing === plan.key ? 'Creating checkout…' : <>Upgrade to {plan.name} <Sparkles size={15}/></>}
          </button>
        </article>;
      })}
    </div>
  </section>;
}
