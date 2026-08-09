import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronLeft, Minus, Plus, Search, ShoppingBag, Store, Trash2, Truck, UtensilsCrossed, X } from 'lucide-react';
import { absoluteApiUrl, createOrder, getBusinessProducts } from './api';

const CART_KEY = 'ashes_customer_cart_v1';

function readCart(slug) {
  try { const saved = JSON.parse(localStorage.getItem(CART_KEY) || '{}'); return saved?.slug === slug ? saved.items || {} : {}; }
  catch { return {}; }
}

export default function CustomerCart({ business, initialProduct, tableCode = '', onClose, onViewProduct }) {
  const slug = business?.slug;
  const [products, setProducts] = useState([]);
  const [items, setItems] = useState(() => readCart(slug));
  const [query, setQuery] = useState('');
  const [service, setService] = useState(tableCode ? 'dine_in' : 'takeaway');
  const [step, setStep] = useState('browse');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [notes, setNotes] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [order, setOrder] = useState(null);

  useEffect(() => {
    if (!slug) return;
    getBusinessProducts(slug).then(setProducts).catch(e => setError(e.message || 'Could not load this menu.'));
  }, [slug]);

  useEffect(() => {
    if (!initialProduct?.id || !slug) return;
    setItems(prev => Object.keys(prev).length ? prev : { [initialProduct.id]: 1 });
  }, [initialProduct?.id, slug]);

  useEffect(() => { if (slug) localStorage.setItem(CART_KEY, JSON.stringify({ slug, items })); }, [items, slug]);

  const filtered = useMemo(() => products.filter(p => !query || `${p.name} ${p.category || ''}`.toLowerCase().includes(query.toLowerCase())), [products, query]);
  const lines = useMemo(() => products.filter(p => items[p.id]).map(p => ({ ...p, quantity: items[p.id] })), [products, items]);
  const subtotal = lines.reduce((sum, p) => sum + Number(p.price || 0) * p.quantity, 0);
  const deliveryFee = service === 'delivery' ? Number(business?.delivery_fee || 0) : 0;
  const serviceFee = Number(business?.service_fee || 0);
  const total = subtotal + deliveryFee + serviceFee;
  const count = lines.reduce((sum, p) => sum + p.quantity, 0);

  const change = (id, delta) => setItems(prev => {
    const next = { ...prev }; const qty = Math.max(0, Number(next[id] || 0) + delta);
    if (!qty) delete next[id]; else next[id] = qty; return next;
  });

  const submit = async () => {
    if (!lines.length) return setError('Your cart is empty.');
    if (service === 'delivery' && !address.trim()) return setError('Add a delivery address.');
    setSending(true); setError('');
    try {
      const result = await createOrder({
        items: lines.map(p => ({ product_id: p.id, quantity: p.quantity })),
        table_code: service === 'dine_in' ? (tableCode || 'DINE-IN') : null,
        customer_name: name || null,
        notes: [`Service: ${service.replace('_',' ')}`, phone && `Phone: ${phone}`, address && `Address: ${address}`, notes].filter(Boolean).join(' | '),
      });
      setOrder(result); setItems({}); localStorage.removeItem(CART_KEY); setStep('success');
    } catch (e) { setError(e.message || 'Could not place order.'); }
    finally { setSending(false); }
  };

  return <div className="customer-store-backdrop">
    <section className="customer-store-shell">
      <header className="customer-store-head">
        <button className="customer-icon-btn" onClick={onClose}><X size={20}/></button>
        <div className="customer-store-brand"><div className="customer-store-logo">{business?.logo_url ? <img src={absoluteApiUrl(business.logo_url)} alt=""/> : <Store size={20}/>}</div><div><strong>{business?.name || 'Store'}</strong><span>{step === 'browse' ? 'Browse & order' : step === 'checkout' ? 'Checkout' : 'Order confirmed'}</span></div></div>
        {step !== 'success' && <button className="customer-cart-count" onClick={() => setStep('checkout')}><ShoppingBag size={17}/><b>{count}</b><span>Rs {subtotal.toLocaleString()}</span></button>}
      </header>

      {step === 'browse' && <div className="customer-store-body">
        <div className="customer-store-hero"><span>FULL MENU</span><h2>What else looks good?</h2><p>Add anything from {business?.name} to one cart. Your scanned item stays with you.</p></div>
        <div className="customer-search"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search products or categories"/></div>
        <div className="customer-product-grid">{filtered.map(p => <article className="customer-product-card" key={p.id}>
          <button className="customer-product-image" onClick={()=>onViewProduct?.(p.id)}>{p.image_url ? <img src={absoluteApiUrl(p.image_url)} alt={p.name}/> : <Store size={28}/>}</button>
          <div><span>{p.category || 'Product'}</span><h3>{p.name}</h3><strong>Rs {Number(p.price || 0).toLocaleString()}</strong></div>
          {items[p.id] ? <div className="customer-qty"><button onClick={()=>change(p.id,-1)}><Minus size={15}/></button><b>{items[p.id]}</b><button onClick={()=>change(p.id,1)}><Plus size={15}/></button></div> : <button className="customer-add" onClick={()=>change(p.id,1)}><Plus size={16}/> Add</button>}
        </article>)}</div>
        {count > 0 && <button className="customer-sticky-checkout" onClick={()=>setStep('checkout')}><span><ShoppingBag size={18}/> {count} item{count===1?'':'s'}</span><strong>Checkout · Rs {subtotal.toLocaleString()}</strong></button>}
      </div>}

      {step === 'checkout' && <div className="customer-checkout-body">
        <button className="customer-back-link" onClick={()=>setStep('browse')}><ChevronLeft size={17}/> Continue shopping</button>
        <div className="customer-checkout-grid"><div className="customer-checkout-main">
          <section className="customer-checkout-card"><div className="customer-section-title"><span>01</span><div><h3>How do you want it?</h3><p>Choose how this order should be fulfilled.</p></div></div><div className="customer-service-grid">
            <button className={service==='dine_in'?'active':''} onClick={()=>setService('dine_in')}><UtensilsCrossed/><strong>Dine in</strong><span>{tableCode ? `Table ${tableCode}` : 'At this location'}</span></button>
            <button className={service==='takeaway'?'active':''} onClick={()=>setService('takeaway')}><ShoppingBag/><strong>Takeaway</strong><span>Pick up when ready</span></button>
            <button className={service==='delivery'?'active':''} onClick={()=>setService('delivery')}><Truck/><strong>Delivery</strong><span>Send to your address</span></button>
          </div></section>
          <section className="customer-checkout-card"><div className="customer-section-title"><span>02</span><div><h3>Your details</h3><p>Only what the business needs for this order.</p></div></div><div className="customer-fields"><label><span>Name</span><input value={name} onChange={e=>setName(e.target.value)} placeholder="Your name"/></label><label><span>Phone</span><input value={phone} onChange={e=>setPhone(e.target.value)} placeholder="03xx xxx xxxx"/></label>{service==='delivery'&&<label className="wide"><span>Delivery address</span><textarea value={address} onChange={e=>setAddress(e.target.value)} placeholder="House, street, area, city"/></label>}<label className="wide"><span>Order notes</span><textarea value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Anything the business should know?"/></label></div></section>
          <section className="customer-checkout-card"><div className="customer-section-title"><span>03</span><div><h3>Payment</h3><p>Order now. Online customer payments can plug into this step when enabled by the merchant.</p></div></div><div className="customer-payment-choice active"><div><strong>Pay at business / on delivery</strong><span>No card details required</span></div><Check size={18}/></div></section>
        </div><aside className="customer-order-summary"><h3>Your order</h3><div className="customer-summary-lines">{lines.map(p=><div className="customer-summary-item" key={p.id}><div><strong>{p.quantity}× {p.name}</strong><span>Rs {Number(p.price).toLocaleString()} each</span></div><b>Rs {(Number(p.price)*p.quantity).toLocaleString()}</b><button onClick={()=>setItems(prev=>{const n={...prev};delete n[p.id];return n;})}><Trash2 size={14}/></button></div>)}</div><div className="customer-totals"><div><span>Subtotal</span><b>Rs {subtotal.toLocaleString()}</b></div>{serviceFee>0&&<div><span>Service fee</span><b>Rs {serviceFee.toLocaleString()}</b></div>}{deliveryFee>0&&<div><span>Delivery</span><b>Rs {deliveryFee.toLocaleString()}</b></div>}<div className="grand"><span>Total</span><strong>Rs {total.toLocaleString()}</strong></div></div>{error&&<div className="form-error">{error}</div>}<button className="customer-place-order" disabled={sending||!lines.length} onClick={submit}>{sending?'Placing order…':`Place order · Rs ${total.toLocaleString()}`}</button><small>Final payable amount is confirmed by the business if delivery/service fees are not configured.</small></aside></div>
      </div>}

      {step === 'success' && <div className="customer-order-success"><div><Check size={34}/></div><span>ORDER RECEIVED</span><h2>You're all set.</h2><p>{business?.name} has received order <strong>#{order?.id?.slice(0,8).toUpperCase()}</strong>.</p><section><div><span>Status</span><b>{order?.status || 'new'}</b></div><div><span>Order total</span><b>Rs {Number(order?.total || total).toLocaleString()}</b></div><div><span>Fulfilment</span><b>{service.replace('_',' ')}</b></div></section><button className="customer-place-order" onClick={onClose}>Back to product</button></div>}
    </section>
  </div>;
}
