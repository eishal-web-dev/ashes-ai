import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Globe2, Instagram, Minus, Phone, Plus, ShoppingBag, Sparkles, Utensils, X } from 'lucide-react';
import { absoluteApiUrl, createOrder, getBusinessProducts, getBusinessProfile } from './api';

export default function MenuExperience({ businessSlug, tableCode, onBack, onOpenProduct }) {
  const [products, setProducts] = useState([]);
  const [business, setBusiness] = useState(null);
  const [cart, setCart] = useState({});
  const [cartOpen, setCartOpen] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [notes, setNotes] = useState('');
  const [placing, setPlacing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [category, setCategory] = useState('All');

  useEffect(() => {
    if (!businessSlug) return;
    Promise.all([getBusinessProducts(businessSlug), getBusinessProfile(businessSlug)])
      .then(([items, profile]) => { setProducts(items); setBusiness(profile); })
      .catch(() => setError('Could not load menu'));
  }, [businessSlug]);

  const categories = useMemo(() => ['All', ...Array.from(new Set(products.map(p => p.category || 'Main')))], [products]);
  const filtered = category === 'All' ? products : products.filter(p => (p.category || 'Main') === category);
  const cartItems = useMemo(() => Object.entries(cart).map(([id, quantity]) => ({ product: products.find(p => p.id === id), quantity })).filter(x => x.product && x.quantity > 0), [cart, products]);
  const cartCount = cartItems.reduce((n, x) => n + x.quantity, 0);
  const total = cartItems.reduce((n, x) => n + Number(x.product.price || 0) * x.quantity, 0);
  const accent = business?.accent_color || '#ff2f9f';
  const initial = (business?.name || 'A').slice(0, 1).toUpperCase();

  const changeQty = (id, delta) => setCart(prev => {
    const next = Math.max(0, (prev[id] || 0) + delta);
    const copy = { ...prev };
    if (next === 0) delete copy[id]; else copy[id] = next;
    return copy;
  });

  const placeOrder = async () => {
    if (!cartItems.length) return;
    setPlacing(true); setError('');
    try {
      const order = await createOrder({
        items: cartItems.map(x => ({ product_id: x.product.id, quantity: x.quantity })),
        table_code: tableCode || null,
        customer_name: customerName || null,
        notes: notes || null,
      });
      setResult(order);
    } catch (e) {
      setError(e?.message || 'Could not place order');
    } finally { setPlacing(false); }
  };

  return <main className="menu-page" style={{ '--business-accent': accent }}>
    <div className="noise" />
    <header className="menu-topbar container">
      <button className="icon-button" onClick={onBack}><ArrowLeft size={18} /></button>
      <div className="menu-brand-lockup">
        <div className="menu-brand-logo">{business?.logo_url ? <img src={absoluteApiUrl(business.logo_url)} alt={business.name}/> : initial}</div>
        <div><strong>{business?.name || 'Ashes Partner'}</strong><span>POWERED BY ASHES AI</span></div>
      </div>
      <button className="cart-pill" onClick={() => setCartOpen(true)}><ShoppingBag size={16}/> {cartCount} · Rs {total.toLocaleString()}</button>
    </header>

    <section className="menu-hero container">
      <div><span className="kicker">TABLE {tableCode || 'SESSION'}</span><h1>{business?.name || 'Explore the menu'} in 3D.</h1><p>Browse dishes, open any item in its interactive experience, then add several items into one table order.</p>
        <div className="menu-business-meta">
          {business?.city && <span>{business.city}</span>}
          {business?.phone && <a href={`tel:${business.phone}`}><Phone size={13}/> {business.phone}</a>}
          {business?.instagram && <span><Instagram size={13}/> {business.instagram}</span>}
          {business?.website && <span><Globe2 size={13}/> {business.website}</span>}
        </div>
      </div>
      <div className="menu-hero-chip"><Sparkles size={18}/> LIVE ASHES MENU</div>
    </section>

    <section className="container menu-content">
      <div className="category-strip">{categories.map(c => <button key={c} className={category === c ? 'active' : ''} onClick={() => setCategory(c)}>{c}</button>)}</div>
      {error && <div className="form-error">{error}</div>}
      <div className="menu-grid">
        {filtered.map(product => <article className="menu-card glass-panel" key={product.id}>
          <div className="menu-thumb">{product.image_url ? <img src={absoluteApiUrl(product.image_url)} alt={product.name}/> : <Utensils size={30}/>}</div>
          <div className="menu-card-body">
            <div><span className="menu-category">{product.category || 'Main'}</span><h3>{product.name}</h3></div>
            <strong>Rs {Number(product.price || 0).toLocaleString()}</strong>
            <div className="menu-card-actions">
              <button className="secondary-btn" onClick={() => onOpenProduct?.(product.id)}>View 3D</button>
              <div className="qty-control"><button onClick={() => changeQty(product.id, -1)}><Minus size={14}/></button><strong>{cart[product.id] || 0}</strong><button onClick={() => changeQty(product.id, 1)}><Plus size={14}/></button></div>
            </div>
          </div>
        </article>)}
      </div>
    </section>

    {cartOpen && <div className="cart-backdrop" onClick={() => setCartOpen(false)}>
      <aside className="order-drawer glass-panel" onClick={e => e.stopPropagation()}>
        <div className="order-drawer-head"><div><span className="kicker">TABLE ORDER</span><h2>{business?.name || 'Your'} cart</h2></div><button className="icon-button" onClick={() => setCartOpen(false)}><X size={18}/></button></div>
        {result ? <div className="order-success"><h3>Order sent.</h3><p>Order <strong>#{result.id.slice(0,8).toUpperCase()}</strong> is in the restaurant queue.</p><div className="order-status-line"><span>Total</span><strong>Rs {Number(result.total).toLocaleString()}</strong></div></div> : <>
          <div className="multi-cart-items">{cartItems.length === 0 && <p>Your cart is empty.</p>}{cartItems.map(({ product, quantity }) => <div className="multi-cart-row" key={product.id}><div><strong>{product.name}</strong><span>Rs {Number(product.price).toLocaleString()}</span></div><div className="qty-control"><button onClick={() => changeQty(product.id,-1)}><Minus size={14}/></button><strong>{quantity}</strong><button onClick={() => changeQty(product.id,1)}><Plus size={14}/></button></div></div>)}</div>
          <label className="order-field"><span>Your name (optional)</span><input value={customerName} onChange={e => setCustomerName(e.target.value)} placeholder="Name"/></label>
          <label className="order-field"><span>Notes</span><textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="No onions, extra sauce…"/></label>
          <div className="order-total"><span>Table {tableCode || '—'} total</span><strong>Rs {total.toLocaleString()}</strong></div>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-btn wide" disabled={!cartItems.length || placing} onClick={placeOrder}>{placing ? 'Sending…' : 'Send combined order'} <ShoppingBag size={16}/></button>
        </>}
      </aside>
    </div>}
  </main>;
}
