import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, BarChart3, Box, Building2, Camera, Check, ChefHat, ChevronRight, Download, ImagePlus, LogOut, Pencil, Plus, QrCode, ScanLine, Sparkles, Trash2, Upload, Utensils } from 'lucide-react';
import { absoluteApiUrl, clearSession, createBusinessProduct, createTableQr, deleteBusinessProduct, getBusinessAnalytics, getBusinessOrders, getBusinessProducts, getTableQrs, updateBusinessProduct, updateOrderStatus } from './api';

export default function BusinessDashboard({ onBack, onOpenProduct, business, user, onLogout }) {
  const [step, setStep] = useState('dashboard');
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [tableQrs, setTableQrs] = useState([]);
  const [tableCode, setTableCode] = useState('T01');
  const [tableProductId, setTableProductId] = useState('');
  const [analytics, setAnalytics] = useState({ scans: 0, views_3d: 0, ar_launches: 0, products: [] });
  const [form, setForm] = useState({ name: '', price: '', category: 'Main', calories: '', protein: '', carbs: '', fat: '', tags: 'Halal, Popular' });
  const [imageFile, setImageFile] = useState(null);
  const [created, setCreated] = useState(null);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const slug = business?.slug;

  const loadDashboard = async () => {
    if (!slug) return;
    try {
      const [items, metrics, latestOrders, qrs] = await Promise.all([
        getBusinessProducts(slug, true),
        getBusinessAnalytics(slug),
        getBusinessOrders(slug),
        getTableQrs(slug),
      ]);
      const metricMap = Object.fromEntries((metrics.products || []).map(p => [p.id, p]));
      setProducts(items.map(item => ({ ...item, ...(metricMap[item.id] || {}) })));
      setAnalytics(metrics);
      setOrders(latestOrders || []);
      setTableQrs(qrs || []);
    } catch {}
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
    published: products.filter(p => p.is_published).length,
    revenue: orders.filter(o => o.status !== 'cancelled').reduce((sum, o) => sum + Number(o.total || 0), 0),
    openOrders: orders.filter(o => !['served', 'cancelled'].includes(o.status)).length,
  }), [analytics, products, orders]);

  const addProduct = async () => {
    if (!form.name || !form.price || !imageFile || !slug) { setError('Add a product name, price and image first.'); return; }
    setSaving(true); setError('');
    try {
      const next = await createBusinessProduct(slug, form, imageFile);
      setProducts(prev => [{ ...next }, ...prev]); setCreated(next); setStep('success'); setTimeout(loadDashboard, 600);
    } catch (err) { setError(err.message || 'Could not create product'); }
    finally { setSaving(false); }
  };

  const changeOrderStatus = async (orderId, status) => {
    try { const updated = await updateOrderStatus(slug, orderId, status); setOrders(prev => prev.map(o => o.id === orderId ? updated : o)); } catch {}
  };

  const addTableQr = async () => {
    if (!tableCode.trim()) return;
    try {
      await createTableQr(slug, tableCode, tableProductId || null);
      setTableCode(`T${String(tableQrs.length + 2).padStart(2, '0')}`);
      await loadDashboard();
    } catch (err) { setError(err.message || 'Could not create table QR'); }
  };

  const togglePublish = async product => {
    try {
      const updated = await updateBusinessProduct(slug, product.id, { is_published: !product.is_published });
      setProducts(prev => prev.map(p => p.id === product.id ? { ...p, ...updated } : p));
    } catch (err) { setError(err.message || 'Could not update product'); }
  };

  const beginEdit = product => {
    setEditing(product.id);
    setEditForm({
      name: product.name || '', category: product.category || 'Main', price: product.price || '',
      calories: product.calories || '', protein: product.protein || '', carbs: product.carbs || '', fat: product.fat || '',
      tags: (product.tags || []).join(', '),
    });
  };

  const saveEdit = async productId => {
    try {
      const updated = await updateBusinessProduct(slug, productId, editForm);
      setProducts(prev => prev.map(p => p.id === productId ? { ...p, ...updated } : p));
      setEditing(null); setEditForm(null);
    } catch (err) { setError(err.message || 'Could not save product'); }
  };

  const removeProduct = async product => {
    if (!window.confirm(`Delete ${product.name}? This also removes its uploaded image/model/QR where possible.`)) return;
    try {
      await deleteBusinessProduct(slug, product.id);
      setProducts(prev => prev.filter(p => p.id !== product.id));
      if (tableProductId === product.id) setTableProductId('');
    } catch (err) { setError(err.message || 'Could not delete product'); }
  };

  const logout = () => { clearSession(); onLogout?.(); };
  const initial = (business?.name || 'A').slice(0,1).toUpperCase();

  if (step === 'add') return (
    <main className="business-shell"><div className="noise" />
      <div className="business-topbar container"><button className="icon-button" onClick={() => setStep('dashboard')}><ArrowLeft size={18} /></button><div className="brand"><span>ASHES</span><b>BUSINESS</b></div><span className="business-badge">CREATE PRODUCT</span></div>
      <section className="product-builder container">
        <div className="builder-intro"><span className="kicker">ONE PHOTO → 3D EXPERIENCE</span><h1>Add a product.</h1><p>Upload one clean photo and Ashes stores it, generates a smart QR, and queues the product for the 3D worker. New products start as drafts until you publish them.</p></div>
        <div className="builder-grid">
          <div className="upload-panel glass-panel"><label className="photo-dropzone"><input type="file" accept="image/*" onChange={e => setImageFile(e.target.files?.[0] || null)} /><div className="upload-orb"><ImagePlus size={34} /></div><strong>{imageFile?.name || 'Upload product photo'}</strong><span>{imageFile ? 'Photo selected — ready for upload' : 'JPG, PNG or WEBP. Clean background works best.'}</span><div className="upload-action"><Upload size={15} /> Choose image</div></label><div className="ai-pipeline-strip"><div><Camera size={16} /><span>Image</span></div><ChevronRight size={15} /><div><Sparkles size={16} /><span>AI 3D</span></div><ChevronRight size={15} /><div><Box size={16} /><span>GLB</span></div><ChevronRight size={15} /><div><QrCode size={16} /><span>QR</span></div></div></div>
          <div className="product-form glass-panel">
            <div className="field-row two"><label><span>Product name</span><input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="Signature burger" /></label><label><span>Price (PKR)</span><input type="number" value={form.price} onChange={e => setForm({...form, price:e.target.value})} placeholder="1290" /></label></div>
            <label><span>Category</span><select value={form.category} onChange={e => setForm({...form, category:e.target.value})}><option>Main</option><option>Burgers</option><option>Coffee</option><option>Desserts</option><option>Retail</option><option>Furniture</option></select></label>
            <div className="nutrition-inputs"><label><span>Calories</span><input value={form.calories} onChange={e=>setForm({...form,calories:e.target.value})} placeholder="820" /></label><label><span>Protein</span><input value={form.protein} onChange={e=>setForm({...form,protein:e.target.value})} placeholder="42g" /></label><label><span>Carbs</span><input value={form.carbs} onChange={e=>setForm({...form,carbs:e.target.value})} placeholder="56g" /></label><label><span>Fat</span><input value={form.fat} onChange={e=>setForm({...form,fat:e.target.value})} placeholder="47g" /></label></div>
            <label><span>Tags</span><input value={form.tags} onChange={e => setForm({...form, tags:e.target.value})} placeholder="Halal, High Protein, Spicy" /></label>
            <div className="ai-note"><Sparkles size={16} /><p>Nutrition and allergens stay business-approved; Ashes can assist later but should not silently publish guessed allergen data.</p></div>
            {error && <div className="form-error">{error}</div>}<button className="primary-btn wide" disabled={saving} onClick={addProduct}>{saving ? 'Uploading & creating…' : 'Create draft product & generate QR'} <Sparkles size={17} /></button>
          </div>
        </div>
      </section>
    </main>
  );

  if (step === 'success') return (
    <main className="business-shell success-shell"><div className="noise" /><section className="success-card glass-panel"><div className="success-icon"><Check size={34} /></div><span className="kicker">DRAFT CREATED</span><h1>{created?.name}</h1><p>Your product belongs to {business?.name}, has its own QR, and its 3D job is queued. It stays hidden from customers until you publish it.</p><div className="qr-demo real-qr">{created?.qr_url ? <img src={absoluteApiUrl(created.qr_url)} alt={`QR for ${created.name}`} /> : <QrCode size={110} strokeWidth={1.2}/>}<span>{created?.id?.slice(0, 8).toUpperCase()}</span></div><div className="public-link">{created?.public_url}</div><div className="success-actions"><button className="secondary-btn" onClick={() => { setStep('dashboard'); loadDashboard(); }}>Manage draft</button></div></section></main>
  );

  return (
    <main className="business-shell"><div className="noise" /><div className="dashboard-layout">
      <aside className="business-sidebar"><div className="brand"><span>ASHES</span><b>AI</b></div><div className="business-profile"><div className="profile-logo">{initial}</div><div><strong>{business?.name || 'Your business'}</strong><span>{business?.kind || 'business'}{business?.city ? ` · ${business.city}` : ''}</span></div></div><nav className="side-nav"><button className="active"><BarChart3 size={17}/> Overview</button><button><Utensils size={17}/> Products</button><button><ChefHat size={17}/> Orders <span className="nav-count">{totals.openOrders}</span></button><button><QrCode size={17}/> QR Codes <span className="nav-count">{tableQrs.length}</span></button><button><ScanLine size={17}/> Analytics</button><button><Building2 size={17}/> Business</button></nav><button className="side-back" onClick={onBack}><ArrowLeft size={16}/> Ashes home</button><button className="side-back" onClick={logout}><LogOut size={16}/> Sign out</button></aside>
      <section className="dashboard-main"><header className="dashboard-header"><div><span className="kicker">ASHES BUSINESS OS</span><h1>Good evening, {user?.name || business?.name}.</h1><p className="dashboard-subline">Managing <strong>{business?.name}</strong> · @{business?.slug}</p></div><button className="primary-btn" onClick={() => setStep('add')}><Upload size={17}/> Add product</button></header>
      <div className="stat-grid business-stats"><article><span>PRODUCTS</span><strong>{products.length}</strong><em>{totals.published} published</em></article><article><span>LIVE ORDERS</span><strong>{totals.openOrders}</strong><em>Waiting / preparing</em></article><article><span>ORDER VALUE</span><strong>Rs {totals.revenue.toLocaleString()}</strong><em>Non-cancelled orders</em></article><article><span>TABLE QRS</span><strong>{tableQrs.length}</strong><em>Printable entry points</em></article></div>

      <section className="orders-panel glass-panel"><div className="panel-head"><div><span className="kicker">LIVE KITCHEN QUEUE</span><h2>Incoming table orders</h2></div><button className="secondary-btn" onClick={loadDashboard}>Refresh</button></div><div className="orders-list">{orders.length === 0 && <div className="empty-catalog">No orders yet. Customer orders from scanned product pages will appear here automatically.</div>}{orders.slice(0,8).map(order => <article className="order-card" key={order.id}><div className="order-card-top"><div><strong>#{order.id.slice(0,8).toUpperCase()}</strong><span>{order.table_code ? `Table ${order.table_code}` : 'No table'}{order.customer_name ? ` · ${order.customer_name}` : ''}</span></div><b>Rs {Number(order.total).toLocaleString()}</b></div><div className="order-items-mini">{(order.items || []).map(item => <span key={item.product_id}>{item.quantity}× {item.product_name}</span>)}</div>{order.notes && <p className="order-note">“{order.notes}”</p>}<div className="order-status-actions">{['new','accepted','preparing','ready','served'].map(status => <button key={status} className={order.status === status ? 'active' : ''} onClick={() => changeOrderStatus(order.id,status)}>{status}</button>)}<button className={order.status === 'cancelled' ? 'active danger' : 'danger'} onClick={() => changeOrderStatus(order.id,'cancelled')}>cancel</button></div></article>)}</div></section>

      <section className="table-qr-panel glass-panel"><div className="panel-head"><div><span className="kicker">TABLE ENTRY POINTS</span><h2>Create printable QR codes</h2></div></div><div className="table-qr-builder"><label><span>Table code</span><input value={tableCode} onChange={e => setTableCode(e.target.value.toUpperCase())} placeholder="T01" /></label><label><span>Open directly to product (optional)</span><select value={tableProductId} onChange={e => setTableProductId(e.target.value)}><option value="">Table session only</option>{products.filter(p => p.is_published).map(p => <option value={p.id} key={p.id}>{p.name}</option>)}</select></label><button className="primary-btn" onClick={addTableQr}><Plus size={16}/> Create table QR</button></div>{error && <div className="form-error">{error}</div>}<div className="table-qr-grid">{tableQrs.length === 0 && <div className="empty-catalog">Create T01, T02, Counter, Patio-1, or any code the restaurant uses.</div>}{tableQrs.map(qr => <article className="table-qr-card" key={qr.id}><img src={absoluteApiUrl(qr.qr_url)} alt={`QR for table ${qr.table_code}`} /><div><strong>Table {qr.table_code}</strong><span>{qr.public_url}</span><a className="secondary-btn" href={absoluteApiUrl(qr.qr_url)} download={`ashes-${business?.slug}-${qr.table_code}.png`}><Download size={15}/> Download QR</a></div></article>)}</div></section>

      <section className="catalog-panel glass-panel">
        <div className="panel-head"><div><span className="kicker">CATALOG CONTROL</span><h2>Products, drafts & publishing</h2></div><button className="text-btn" onClick={() => setStep('add')}>Add new <ChevronRight size={15}/></button></div>
        <div className="product-table">
          {products.length === 0 && <div className="empty-catalog">No products yet. Upload the first one and Ashes will create its QR + 3D job.</div>}
          {products.map(product => {
            const ready = product.status === 'ready';
            const isEditing = editing === product.id;
            return <div className="product-manage-card" key={product.id}>
              {isEditing ? <div className="product-edit-grid">
                <input value={editForm.name} onChange={e => setEditForm({...editForm,name:e.target.value})} />
                <input value={editForm.category} onChange={e => setEditForm({...editForm,category:e.target.value})} />
                <input type="number" value={editForm.price} onChange={e => setEditForm({...editForm,price:Number(e.target.value)})} />
                <input value={editForm.tags} onChange={e => setEditForm({...editForm,tags:e.target.value})} placeholder="Tags" />
                <button className="primary-btn" onClick={() => saveEdit(product.id)}>Save</button>
                <button className="secondary-btn" onClick={() => { setEditing(null); setEditForm(null); }}>Cancel</button>
              </div> : <>
                <div className="product-row">
                  <div className="product-thumb"><Box size={19}/></div>
                  <div className="product-meta"><strong>{product.name}</strong><span>{product.category} · Rs {Number(product.price).toLocaleString()}</span></div>
                  <span className={`status-pill ${ready ? 'ready' : 'processing'}`}>{ready ? '3D Ready' : product.status}</span>
                  <span className={`publish-pill ${product.is_published ? 'published' : 'draft'}`}>{product.is_published ? 'Published' : 'Draft'}</span>
                  <div className="row-metric"><strong>{product.scans || 0}</strong><span>scans</span></div>
                </div>
                <div className="product-manage-actions">
                  <button className="secondary-btn" onClick={() => beginEdit(product)}><Pencil size={14}/> Edit</button>
                  <button className={product.is_published ? 'secondary-btn' : 'primary-btn'} onClick={() => togglePublish(product)}>{product.is_published ? 'Unpublish' : 'Publish'}</button>
                  {product.is_published && <button className="secondary-btn" onClick={() => onOpenProduct?.(product.id)}>Preview</button>}
                  <button className="danger-action" onClick={() => removeProduct(product)}><Trash2 size={14}/> Delete</button>
                </div>
              </>}
            </div>;
          })}
        </div>
      </section>
      </section>
    </div></main>
  );
}
