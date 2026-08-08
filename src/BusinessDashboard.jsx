import { useMemo, useState } from 'react';
import { ArrowLeft, BarChart3, Box, Building2, Camera, Check, ChevronRight, ImagePlus, QrCode, ScanLine, Sparkles, Store, Upload, Utensils } from 'lucide-react';

const seedProducts = [
  { id: 1, name: 'Neon Smash Burger', category: 'Burgers', price: 1290, status: '3D Ready', scans: 482, ar: 211 },
  { id: 2, name: 'Midnight Mocha', category: 'Coffee', price: 640, status: 'Processing', scans: 0, ar: 0 },
  { id: 3, name: 'Inferno Fries', category: 'Sides', price: 520, status: '3D Ready', scans: 231, ar: 89 },
];

export default function BusinessDashboard({ onBack, onOpenProduct }) {
  const [step, setStep] = useState('dashboard');
  const [products, setProducts] = useState(seedProducts);
  const [form, setForm] = useState({ name: '', price: '', category: 'Main', calories: '', protein: '', carbs: '', fat: '', tags: 'Halal, Popular' });
  const [imageName, setImageName] = useState('');
  const [created, setCreated] = useState(null);

  const totals = useMemo(() => ({
    scans: products.reduce((n, p) => n + p.scans, 0),
    ar: products.reduce((n, p) => n + p.ar, 0),
    ready: products.filter(p => p.status === '3D Ready').length,
  }), [products]);

  const addProduct = () => {
    if (!form.name || !form.price) return;
    const next = {
      id: Date.now(),
      name: form.name,
      category: form.category,
      price: Number(form.price),
      status: 'Processing',
      scans: 0,
      ar: 0,
      nutrition: { calories: form.calories, protein: form.protein, carbs: form.carbs, fat: form.fat },
      tags: form.tags.split(',').map(v => v.trim()).filter(Boolean),
      imageName,
    };
    setProducts(prev => [next, ...prev]);
    setCreated(next);
    setStep('success');
  };

  if (step === 'add') {
    return (
      <main className="business-shell">
        <div className="noise" />
        <div className="business-topbar container">
          <button className="icon-button" onClick={() => setStep('dashboard')}><ArrowLeft size={18} /></button>
          <div className="brand"><span>ASHES</span><b>BUSINESS</b></div>
          <span className="business-badge">CREATE PRODUCT</span>
        </div>

        <section className="product-builder container">
          <div className="builder-intro">
            <span className="kicker">ONE PHOTO → 3D EXPERIENCE</span>
            <h1>Add a product.</h1>
            <p>Upload one clean photo and the Ashes pipeline prepares the item for 3D generation, QR sharing and customer AR.</p>
          </div>

          <div className="builder-grid">
            <div className="upload-panel glass-panel">
              <label className="photo-dropzone">
                <input type="file" accept="image/*" onChange={e => setImageName(e.target.files?.[0]?.name || '')} />
                <div className="upload-orb"><ImagePlus size={34} /></div>
                <strong>{imageName || 'Upload product photo'}</strong>
                <span>{imageName ? 'Photo selected — ready for AI processing' : 'JPG, PNG or WEBP. Clean background works best.'}</span>
                <div className="upload-action"><Upload size={15} /> Choose image</div>
              </label>
              <div className="ai-pipeline-strip">
                <div><Camera size={16} /><span>Image</span></div><ChevronRight size={15} />
                <div><Sparkles size={16} /><span>AI 3D</span></div><ChevronRight size={15} />
                <div><Box size={16} /><span>GLB</span></div><ChevronRight size={15} />
                <div><QrCode size={16} /><span>QR</span></div>
              </div>
            </div>

            <div className="product-form glass-panel">
              <div className="field-row two">
                <label><span>Product name</span><input value={form.name} onChange={e => setForm({...form, name:e.target.value})} placeholder="Neon Smash Burger" /></label>
                <label><span>Price (PKR)</span><input type="number" value={form.price} onChange={e => setForm({...form, price:e.target.value})} placeholder="1290" /></label>
              </div>
              <label><span>Category</span><select value={form.category} onChange={e => setForm({...form, category:e.target.value})}><option>Main</option><option>Burgers</option><option>Coffee</option><option>Desserts</option><option>Retail</option><option>Furniture</option></select></label>
              <div className="nutrition-inputs">
                <label><span>Calories</span><input value={form.calories} onChange={e=>setForm({...form,calories:e.target.value})} placeholder="820" /></label>
                <label><span>Protein</span><input value={form.protein} onChange={e=>setForm({...form,protein:e.target.value})} placeholder="42g" /></label>
                <label><span>Carbs</span><input value={form.carbs} onChange={e=>setForm({...form,carbs:e.target.value})} placeholder="56g" /></label>
                <label><span>Fat</span><input value={form.fat} onChange={e=>setForm({...form,fat:e.target.value})} placeholder="47g" /></label>
              </div>
              <label><span>Tags</span><input value={form.tags} onChange={e => setForm({...form, tags:e.target.value})} placeholder="Halal, High Protein, Spicy" /></label>
              <div className="ai-note"><Sparkles size={16} /><p>Later, Ashes AI can estimate nutrition and tags from the photo + recipe, then the business approves them before publishing.</p></div>
              <button className="primary-btn wide" onClick={addProduct}>Create product & generate 3D <Sparkles size={17} /></button>
            </div>
          </div>
        </section>
      </main>
    );
  }

  if (step === 'success') {
    return (
      <main className="business-shell success-shell">
        <div className="noise" />
        <section className="success-card glass-panel">
          <div className="success-icon"><Check size={34} /></div>
          <span className="kicker">PRODUCT CREATED</span>
          <h1>{created?.name}</h1>
          <p>Your product is in the Ashes pipeline. When its 3D asset is ready, this QR can open the same customer experience automatically.</p>
          <div className="qr-demo"><QrCode size={110} strokeWidth={1.2}/><span>ASH-{String(created?.id || '').slice(-6)}</span></div>
          <div className="success-actions">
            <button className="secondary-btn" onClick={() => setStep('dashboard')}>Back to dashboard</button>
            <button className="primary-btn" onClick={onOpenProduct}>Preview customer view <ScanLine size={17}/></button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="business-shell">
      <div className="noise" />
      <div className="dashboard-layout">
        <aside className="business-sidebar">
          <div className="brand"><span>ASHES</span><b>AI</b></div>
          <div className="business-profile"><div className="profile-logo">N</div><div><strong>Neon Bites</strong><span>Restaurant · Peshawar</span></div></div>
          <nav className="side-nav">
            <button className="active"><BarChart3 size={17}/> Overview</button>
            <button><Utensils size={17}/> Products</button>
            <button><QrCode size={17}/> QR Codes</button>
            <button><ScanLine size={17}/> Analytics</button>
            <button><Building2 size={17}/> Business</button>
          </nav>
          <button className="side-back" onClick={onBack}><ArrowLeft size={16}/> Ashes home</button>
        </aside>

        <section className="dashboard-main">
          <header className="dashboard-header">
            <div><span className="kicker">ASHES BUSINESS OS</span><h1>Good evening, Neon Bites.</h1></div>
            <button className="primary-btn" onClick={() => setStep('add')}><Upload size={17}/> Add product</button>
          </header>

          <div className="stat-grid business-stats">
            <article><span>PRODUCTS</span><strong>{products.length}</strong><em>{totals.ready} 3D ready</em></article>
            <article><span>QR SCANS</span><strong>{totals.scans.toLocaleString()}</strong><em>Lifetime</em></article>
            <article><span>AR LAUNCHES</span><strong>{totals.ar.toLocaleString()}</strong><em>{totals.scans ? Math.round(totals.ar/totals.scans*100) : 0}% of scans</em></article>
            <article><span>PLAN</span><strong>GROWTH</strong><em>12 / 25 products</em></article>
          </div>

          <div className="dashboard-content-grid">
            <section className="catalog-panel glass-panel">
              <div className="panel-head"><div><span className="kicker">CATALOG</span><h2>Your experiences</h2></div><button className="text-btn" onClick={() => setStep('add')}>Add new <ChevronRight size={15}/></button></div>
              <div className="product-table">
                {products.map(product => (
                  <div className="product-row" key={product.id}>
                    <div className="product-thumb"><Box size={19}/></div>
                    <div className="product-meta"><strong>{product.name}</strong><span>{product.category} · Rs {product.price.toLocaleString()}</span></div>
                    <span className={`status-pill ${product.status === '3D Ready' ? 'ready' : 'processing'}`}>{product.status}</span>
                    <div className="row-metric"><strong>{product.scans}</strong><span>scans</span></div>
                    <button className="row-action" onClick={onOpenProduct}><ChevronRight size={17}/></button>
                  </div>
                ))}
              </div>
            </section>

            <aside className="qr-panel glass-panel">
              <div className="panel-head"><div><span className="kicker">SMART QR</span><h2>Table scan</h2></div></div>
              <div className="qr-demo large"><QrCode size={145} strokeWidth={1.15}/><span>NEONBITES-T01</span></div>
              <p>Place this QR on a table, menu, product card or storefront. Customers enter Ashes instantly — no separate app.</p>
              <button className="secondary-btn wide">Download QR</button>
            </aside>
          </div>
        </section>
      </div>
    </main>
  );
}
