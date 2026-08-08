import { useEffect, useMemo, useState } from 'react';
import { Check, Crown, Sparkles, Zap } from 'lucide-react';
import { changeBusinessPlan, getBillingPlans, getBusinessBilling } from './api';

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

export default function BillingPanel({ slug }) {
  const [billing, setBilling] = useState(null);
  const [plans, setPlans] = useState([]);
  const [changing, setChanging] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    if (!slug) return;
    try {
      const [snapshot, catalog] = await Promise.all([getBusinessBilling(slug), getBillingPlans()]);
      setBilling(snapshot);
      setPlans(catalog?.plans || []);
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
    if (!slug || plan === currentKey) return;
    setChanging(plan); setError('');
    try { setBilling(await changeBusinessPlan(slug, plan)); }
    catch (err) { setError(err.message || 'Could not change plan'); }
    finally { setChanging(''); }
  };

  return <section className="billing-section glass-panel" id="billing">
    <div className="billing-heading">
      <div><span className="kicker">ASHES SUBSCRIPTION</span><h2>Plan & usage</h2><p>Limits protect generation costs while your business scales. Real payment checkout can be connected later without changing this plan system.</p></div>
      <div className="current-plan-badge"><Crown size={16}/><span>{billing?.plan?.name || 'Free'}</span><small>{billing?.status || 'active'}</small></div>
    </div>

    {billing && <div className="billing-usage-grid">{usageRows.map(row => <UsageRow key={row.key} {...row} />)}</div>}
    {error && <div className="form-error">{error}</div>}

    <div className="plan-grid">
      {plans.map(plan => {
        const active = plan.key === currentKey;
        const featured = plan.key === 'starter';
        return <article key={plan.key} className={`plan-card ${active ? 'active' : ''} ${featured ? 'featured' : ''}`}>
          <div className="plan-card-top"><div><span>{plan.name}</span><strong>{plan.price_monthly_usd === 0 ? '$0' : `$${plan.price_monthly_usd}`}<small>/mo</small></strong></div>{featured && <Zap size={18}/>}</div>
          <div className="plan-limits"><span>{plan.product_limit} products</span><span>{plan.ai_generations_monthly} AI generations / month</span><span>{plan.menu_imports_monthly} menu imports / month</span><span>{plan.table_qr_limit} table QRs</span></div>
          <div className="plan-features">{(plan.features || []).map(feature => <div key={feature}><Check size={14}/><span>{feature}</span></div>)}</div>
          <button className={active ? 'secondary-btn wide' : 'primary-btn wide'} disabled={active || changing === plan.key} onClick={() => choosePlan(plan.key)}>
            {active ? 'Current plan' : changing === plan.key ? 'Switching…' : <>Choose {plan.name} <Sparkles size={15}/></>}
          </button>
        </article>;
      })}
    </div>
  </section>;
}
