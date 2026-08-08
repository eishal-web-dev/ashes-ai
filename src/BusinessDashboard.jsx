import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, BarChart3, Box, Building2, Camera, Check, ChefHat, ChevronRight, ImagePlus, LogOut, QrCode, ScanLine, Sparkles, Upload, Utensils } from 'lucide-react';
import { absoluteApiUrl, clearSession, createBusinessProduct, getBusinessAnalytics, getBusinessOrders, getBusinessProducts, updateOrderStatus } from './api';

export default function BusinessDashboard({ onBack, onOpenProduct, business, user, onLogout }) {
  const [step, setStep] = useState('dashboard');
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [analytics, setAnalytics] = useState({ scans: 0, views_3d: 0, ar_launches: 0, products: [] });
  const [form, setForm] = useState({ name: '', price: '', category: 'Main', calories: '', protein: '', carbs: '', fat: '', tags: 'Halal, Popular' });
  const [imageFile, setImageFile] = useState(null);
  const [created, setCreated] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const slug = business?.slug;

  const loadDashboard = async () => {
    if (!slug) return;
    try {
      const [items, metrics, latestOrders] = await Promise.all([
        getBusinessProducts(slug),
        getBusinessAnalytics(slug),
        getBusinessOrders(slug),
      ]);
      const metricMap = Object.fromEntries((metrics.products || []).map(p => [p.id, p]));
      setProducts(items.map(item => ({ ...item, ...(metricMap[item.id] || {}) })));
      setAnalytics(metrics);
      setOrders(latestOrders || []);
    } catch {
      // Keep the dashboard usable if one service is temporarily unavailable.
    }
  };

  useEffect(() => {
    loadDashboard();
    const timer = setInterval(loadDashboard, 8000);
    return () => clearInterval(timer);
  }, [slug]);

  const totals = useMemo(() => ({
    scans: analytics.scans || 0,
    views: analytics.views_3d || 0,
    ar: analytics.ar_launches || 0,
    ready: products.filter(p => p.status === 'ready').length,
    revenue: orders.filter(o => o.status !== 'cancelled').reduce((sum, o) => sum + Number(o.total || 0), 0),
    openOrders: orders.filter(o => !['served', 'cancelled'].includes(o.status)).length,
  }), [analytics, products, orders]);

  const addProduct = async () => {
    if (!form.name || !form.price || !imageFile || !slug) {
      setError('Add a product name, price and image first.');
      return;
    }
    setSaving(true); setError('');
    try {
      const next = await createBusinessProduct(slug, form, imageFile);
      setProducts(prev => [{ ...next }, ...prev]);
      setCreated(next);
      setStep('success');
      setTimeout(loadDashboard, 600);
    } catch (err) { setError(err.message || 'Could not create product'); }
    finally { setSaving(false); }
  };

  const changeOrderStatus = async (orderId, status) => {
    try {
      const updated = await updateOrderStatus(slug, orderId, status);
      setOrders(prev => prev.map(o => o.id === orderId ? updated : o));
    } catch {}
  };

  const logout = () => { clearSession(); onLogout?.(); };
  const initial = (business?.name || 'A').slice(0,1).toUpperCase();

  if (step === 'add') return (
    <main className="business-shell"><div className="noise" />
      <div className="business-topbar container"><button className="icon-button" onClick={() => setStep('dashboard')}><ArrowLeft size={18} /></button><div className="brand"><span>ASHES</span><b>BUSINESS</b></div><span className="business-badge">CREATE PRODUCT</span></div>
      <section className="product-builder container">
        <div className="builder-intro"><span className="kicker">ONE PHOTO → 3D EXPERIENCE</span><h1>Add a product.</h1><p>Upload one clean photo and Ashes stores it, generates a smart QR, and queues the product for the 3D worker.</p></div>
        <div className="builder-grid">
          <div className="upload-panel glass-panel"><label className="photo-dropzone"><input type="file" accept="image/*" onChange={e => setImageFile(e.target.files?.[0] || null)} /><div className="upload-orb"><ImagePlus size={34} /></div><strong>{imageFile?.name || 'Upload product photo'}</strong><span>{imageFile ? 'Photo selected — ready for upload' : 'JPG, PNG or WEBP. Clean background works best.'}</span><div className="upload-action"><Upload size={15} /> Choose image</div></label><div className="ai-pipeline-strip"><div><Camera size={16} /><span>Image</span></div><ChevronRight size={15} /><div><Sparkles size={16} /><span>AI 3D</span></div><ChevronRight size={15} /><div><Box size={16} /><span>GLB</span></div><ChevronRight size={15} /><div><QrCode size={16} /><span>QR</span></div></div></div>
          <div className="product-form glass-panel">
            <div className="field-row two"><label><span>Product name</span><input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="Signature burger" /></label><label><span>Price (PKR)</span><input type="number" value={form.price} onChange={e => setForm({...form, price:e.target.value})} placeholder="1290" /></label></div>
            <label><span>Category</span><select value={form.category} onChange={e => setForm({...form, category:e.target.value})}><option>Main</option><option>Burgers</option><option>Coffee</option><option>Desserts</option><option>Retail</option><option>Furniture</option></select></label>
            <div className="nutrition-inputs"><label><span>Calories</span><input value={form.calories} onChange={e=>setForm({...form,calories:e.target.value})} placeholder="820" /></label><label><span>Protein</span><input value={form.protein} onChange={e=>setForm({...form,protein:e.target.value})} placeholder="42g" /></label><label><span>Carbs</span><input value={form.carbs} onChange={e=>setForm({...form,carbs:e.target.value})} placeholder="56g" /></label><label><span>Fat</span><input value={form.fat} onChange={e=>setForm({...form,fat:e.target.value})} placeholder="47g" /></label></div>
            <label><span>Tags</span><input value={form.tags} onChange={e => setForm({...form, tags:e.target.value})} placeholder="Halal, High Protein, Spicy" /></label>
            <div className="ai-note"><Sparkles size={16} /><p>Nutrition and allergens stay business-approved; Ashes can assist later but should not silently publish guessed allergen data.</p></div>
            {error && <div className="form-error">{error}</div>}<button className="primary-btn wide" disabled={saving} onClick={addProduct}>{saving ? 'Uploading & creating…' : 'Create product & generate QR'} <Sparkles size={17} /></button>
          </div>
        </div>
      </section>
    </main>
  );

  if (step === 'success') return (
    <main className="business-shell success-shell"><div className="noise" /><section className="success-card glass-panel"><div className="success-icon"><Check size={34} /></div><span className="kicker">PRODUCT CREATED</span><h1>{created?.name}</h1><p>Your product belongs to {business?.name}, has its own public URL and QR, and its 3D job is queued.</p><div className="qr-demo real-qr">{created?.qr_url ? <img src={absoluteApiUrl(created.qr_url)} alt={`QR for ${created.name}`} /> : <QrCode size={110} strokeWidth={1.2}/>}<span>{created?.id?.slice(0, 8).toUpperCase()}</span></div><div className="public-link">{created?.public_url}</div><div className="success-actions"><button className="secondary-btn" onClick={() => { setStep('dashboard'); loadDashboard(); }}>Back to dashboard</button><button className="primary-btn" onClick={() => onOpenProduct?.(created?.id)}>Preview customer view <ScanLine size={17}/></button></div></section></main>
  );

  return (
    <main className="business-shell"><div className="noise" /><div className="dashboard-layout">
      <aside className="business-sidebar"><div className="brand"><span>ASHES</span><b>AI</b></div><div className="business-profile"><div className="profile-logo">{initial}</div><div><strong>{business?.name || 'Your business'}</strong><span>{business?.kind || 'business'}{business?.city ? ` · ${business.city}` : ''}</span></div></div><nav className="side-nav"><button className="active"><BarChart3 size={17}/> Overview</button><button><Utensils size={17}/> Products</button><button><ChefHat size={17}/> Orders <span className="nav-count">{totals.openOrders}</span></button><button><QrCode size={17}/> QR Codes</button><button><ScanLine size={17}/> Analytics</button><button><Building2 size={17}/> Business</button></nav><button className="side-back" onClick={onBack}><ArrowLeft size={16}/> Ashes home</button><button className="side-back" onClick={logout}><LogOut size={16}/> Sign out</button></aside>
      <section className="dashboard-main"><header className="dashboard-header"><div><span className="kicker">ASHES BUSINESS OS</span><h1>Good evening, {user?.name || business?.name}.</h1><p className="dashboard-subline">Managing <strong>{business?.name}</strong> · @{business?.slug}</p></div><button className="primary-btn" onClick={() => setStep('add')}><Upload size={17}/> Add product</button></header>
      <div className="stat-grid business-stats"><article><span>PRODUCTS</span><strong>{products.length}</strong><em>{totals.ready} 3D ready</em></article><article><span>LIVE ORDERS</span><strong>{totals.openOrders}</strong><em>Waiting / preparing</em></article><article><span>ORDER VALUE</span><strong>Rs {totals.revenue.toLocaleString()}</strong><em>Non-cancelled orders</em></article><article><span>AR LAUNCHES</span><strong>{totals.ar.toLocaleString()}</strong><em>{totals.scans ? Math.round(totals.ar/totals.scans*100) : 0}% of scans</em></article></div>

      <section className="orders-panel glass-panel">
        <div className="panel-head"><div><span className="kicker">LIVE KITCHEN QUEUE</span><h2>Incoming table orders</h2></div><button className="secondary-btn" onClick={loadDashboard}>Refresh</button></div>
        <div className="orders-list">
          {orders.length === 0 && <div className="empty-catalog">No orders yet. Customer orders from scanned product pages will appear here automatically.</div>}
          {orders.slice(0, 8).map(order => <article className="order-card" key={order.id}>
            <div className="order-card-top"><div><strong>#{order.id.slice(0,8).toUpperCase()}</strong><span>{order.table_code ? `Table ${order.table_code}` : 'No table'}{order.customer_name ? ` · ${order.customer_name}` : ''}</span></div><b>Rs {Number(order.total).toLocaleString()}</b></div>
            <div className="order-items-mini">{(order.items || []).map(item => <span key={item.product_id}>{item.quantity}× {item.product_name}</span>)}</div>
            {order.notes && <p className="order-note">“{order.notes}”</p>}
            <div className="order-status-actions">
              {['new','accepted','preparing','ready','served'].map(status => <button key={status} className={order.status === status ? 'active' : ''} onClick={() => changeOrderStatus(order.id, status)}>{status}</button>)}
              <button className={order.status === 'cancelled' ? 'active danger' : 'danger'} onClick={() => changeOrderStatus(order.id, 'cancelled')}>cancel</button>
            </div>
          </article>)}
        </div>
      </section>

      <div className="dashboard-content-grid"><section className="catalog-panel glass-panel"><div className="panel-head"><div><span className="kicker">CATALOG</span><h2>Your experiences</h2></div><button className="text-btn" onClick={() => setStep('add')}>Add new <ChevronRight size={15}/></button></div><div className="product-table">{products.length === 0 && <div className="empty-catalog">No products yet. Upload the first one and Ashes will create its QR + 3D job.</div>}{products.map(product => { const ready = product.status === 'ready'; return <div className="product-row" key={product.id}><div className="product-thumb"><Box size={19}/></div><div className="product-meta"><strong>{product.name}</strong><span>{product.category} · Rs {Number(product.price).toLocaleString()}</span></div><span className={`status-pill ${ready ? 'ready' : 'processing'}`}>{ready ? '3D Ready' : product.status}</span><div className="row-metric"><strong>{product.scans || 0}</strong><span>scans</span></div><div className="row-metric"><strong>{product.ar_launches || 0}</strong><span>AR</span></div><button className="row-action" onClick={() => onOpenProduct?.(product.id)}><ChevronRight size={17}/></button></div>; })}</div></section><aside className="qr-panel glass-panel"><div className="panel-head"><div><span className="kicker">LIVE FUNNEL</span><h2>Scan → 3D → AR</h2></div></div><div className="analytics-funnel"><div><strong>{totals.scans}</strong><span>QR scans</span></div><i>→</i><div><strong>{totals.views}</strong><span>3D views</span></div><i>→</i><div><strong>{totals.ar}</strong><span>AR launches</span></div></div><p>These numbers come from real product-page events. Table ordering now adds a second measurable conversion layer.</p><button className="secondary-btn wide" onClick={loadDashboard}>Refresh analytics</button></aside></div></section>
    </div></main>
  );
}
