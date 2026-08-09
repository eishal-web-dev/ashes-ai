import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Building2, Camera, Check, ChevronRight, ImagePlus, Pencil, QrCode, Rocket, Sparkles, Upload, Utensils } from 'lucide-react';
import BusinessDashboard from './BusinessDashboard';
import { attachBusinessProductPhoto, createTableQr, getBusinessProducts, getMenuImports, getTableQrs, importMenuCard, updateBusinessProduct } from './api';

function Step({ done, icon: Icon, title, text, active }) {
  return <div className={`onboarding-step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
    <div className="onboarding-step-icon">{done ? <Check size={18}/> : <Icon size={18}/>}</div>
    <div><strong>{title}</strong><span>{text}</span></div>
  </div>;
}

export default function BusinessOnboardingShell(props) {
  const { business, onBusinessUpdated } = props;
  const slug = business?.slug;
  const [products, setProducts] = useState([]);
  const [qrs, setQrs] = useState([]);
  const [imports, setImports] = useState([]);
  const [menuFile, setMenuFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [photoUploadingId, setPhotoUploadingId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({ name: '', category: '', price: '' });
  const [tableCode, setTableCode] = useState('T01');
  const [creatingQr, setCreatingQr] = useState(false);
  const [error, setError] = useState('');
  const [showDashboard, setShowDashboard] = useState(false);

  const load = async () => {
    if (!slug) return;
    try {
      const [productRows, qrRows, importRows] = await Promise.all([
        getBusinessProducts(slug, true), getTableQrs(slug), getMenuImports(slug),
      ]);
      setProducts(productRows || []); setQrs(qrRows || []); setImports(importRows || []);
    } catch (err) { setError(err?.message || 'Could not load setup status'); }
  };

  useEffect(() => { load(); }, [slug]);

  const profileDone = Boolean(business?.name && business?.kind && business?.city);
  const menuDone = imports.some(x => x.status === 'completed') || products.length > 0;
  const needsPhotos = products.filter(x => x.status === 'awaiting-image');
  const photoDone = products.length > 0 && needsPhotos.length === 0;
  const readyModels = products.filter(x => x.status === 'ready').length;
  const modelDone = products.length > 0 && readyModels === products.length;
  const qrDone = qrs.length > 0;
  const checks = [profileDone, menuDone, photoDone, modelDone, qrDone];
  const completed = checks.filter(Boolean).length;
  const progress = Math.round((completed / checks.length) * 100);
  const launchReady = profileDone && menuDone && photoDone && qrDone;

  const activeStep = useMemo(() => {
    if (!profileDone) return 0;
    if (!menuDone) return 1;
    if (!photoDone) return 2;
    if (!modelDone) return 3;
    if (!qrDone) return 4;
    return 5;
  }, [profileDone, menuDone, photoDone, modelDone, qrDone]);

  const runImport = async () => {
    if (!menuFile) { setError('Choose a clear menu-card photo first.'); return; }
    setImporting(true); setError(''); setImportResult(null);
    try {
      const result = await importMenuCard(slug, menuFile);
      setImportResult(result); setMenuFile(null); await load();
      if (result?.business) onBusinessUpdated?.(result.business);
    } catch (err) { setError(err?.message || 'Menu import failed'); }
    finally { setImporting(false); }
  };

  const addPhoto = async (product, file) => {
    if (!file) return;
    setPhotoUploadingId(product.id); setError('');
    try { await attachBusinessProductPhoto(slug, product.id, file); await load(); }
    catch (err) { setError(err?.message || `Could not upload ${product.name} photo`); }
    finally { setPhotoUploadingId(null); }
  };

  const startEdit = product => {
    setEditingId(product.id);
    setEditDraft({ name: product.name || '', category: product.category || 'Main', price: product.price ?? '' });
  };

  const saveEdit = async product => {
    setError('');
    try {
      await updateBusinessProduct(slug, product.id, editDraft);
      setEditingId(null); await load();
    } catch (err) { setError(err?.message || 'Could not save menu item'); }
  };

  const createFirstQr = async () => {
    if (!tableCode.trim()) return;
    setCreatingQr(true); setError('');
    try { await createTableQr(slug, tableCode.trim().toUpperCase(), null); setTableCode('T02'); await load(); }
    catch (err) { setError(err?.message || 'Could not create table QR'); }
    finally { setCreatingQr(false); }
  };

  if (showDashboard || (progress === 100 && products.length > 0)) return <BusinessDashboard {...props} />;

  return <main className="onboarding-shell">
    <div className="onboarding-bg-grid" />
    <header className="onboarding-topbar">
      <div className="brand"><span>ASHES</span><b>AI</b></div>
      <div className="onboarding-top-actions"><span>{business?.name}</span><button className="secondary-btn" onClick={() => setShowDashboard(true)}>Open dashboard</button></div>
    </header>

    <div className="onboarding-layout">
      <aside className="onboarding-rail">
        <span className="kicker">RESTAURANT LAUNCH</span>
        <h2>Go live in minutes.</h2>
        <p>Ashes turns one menu photo into the starting point for your digital restaurant.</p>
        <div className="onboarding-progress-ring" style={{'--progress': `${progress * 3.6}deg`}}><div><strong>{progress}%</strong><span>ready</span></div></div>
        <div className="onboarding-step-list">
          <Step done={profileDone} active={activeStep===0} icon={Building2} title="Business profile" text="Name, type and city" />
          <Step done={menuDone} active={activeStep===1} icon={Sparkles} title="Import menu" text="AI extracts items and prices" />
          <Step done={photoDone} active={activeStep===2} icon={Camera} title="Add product photos" text={`${needsPhotos.length} still need photos`} />
          <Step done={modelDone} active={activeStep===3} icon={ImagePlus} title="Generate 3D" text={`${readyModels}/${products.length || 0} models ready`} />
          <Step done={qrDone} active={activeStep===4} icon={QrCode} title="Create table QR" text={`${qrs.length} entry points created`} />
        </div>
      </aside>

      <section className="onboarding-main">
        <div className="onboarding-hero-card">
          <div><span className="eyebrow"><Rocket size={14}/> ASHES QUICK START</span><h1>Build your digital restaurant from one menu photo.</h1><p>Upload the menu, review what AI found, add real food photos, and Ashes prepares your 3D catalog and table QR flow.</p></div>
          <div className="onboarding-progress-copy"><span>SETUP PROGRESS</span><strong>{completed}/5</strong><div><i style={{width:`${progress}%`}} /></div></div>
        </div>

        {!menuDone && <section className="onboarding-card onboarding-import-card">
          <div className="onboarding-card-head"><div><span className="kicker">STEP 1 · AI MENU IMPORT</span><h2>Upload your menu card</h2><p>Take one clear photo. Ashes extracts names, categories and prices into editable drafts.</p></div><Sparkles size={28}/></div>
          <label className="onboarding-dropzone"><input type="file" accept="image/*" onChange={e=>setMenuFile(e.target.files?.[0] || null)} /><Upload size={26}/><strong>{menuFile?.name || 'Drop or choose menu photo'}</strong><span>JPG, PNG or WEBP · clear front-facing photo works best</span></label>
          <button className="primary-btn" disabled={!menuFile || importing} onClick={runImport}>{importing ? 'Ashes is reading your menu…' : 'Build my menu with AI'} <ArrowRight size={16}/></button>
        </section>}

        {menuDone && <section className="onboarding-card">
          <div className="onboarding-card-head"><div><span className="kicker">AI REVIEW</span><h2>Review your extracted menu</h2><p>Correct names, categories or prices before customers see anything. Imported items remain drafts.</p></div><span className="onboarding-count">{products.length} items</span></div>
          {importResult && <div className="onboarding-import-result"><Check size={16}/><span>{importResult.created_count || 0} products created · {importResult.duplicates_skipped || 0} duplicates skipped · {importResult.needs_review || 0} need review</span></div>}
          <div className="onboarding-review-list">{products.slice(0,12).map(product => <article key={product.id}>
            <div className="review-product-icon"><Utensils size={17}/></div>
            {editingId === product.id ? <div className="review-edit-grid"><input value={editDraft.name} onChange={e=>setEditDraft({...editDraft,name:e.target.value})}/><input value={editDraft.category} onChange={e=>setEditDraft({...editDraft,category:e.target.value})}/><input type="number" value={editDraft.price} onChange={e=>setEditDraft({...editDraft,price:e.target.value})}/></div> : <div className="review-product-copy"><strong>{product.name}</strong><span>{product.category} · Rs {Number(product.price || 0).toLocaleString()}</span></div>}
            <span className={`review-status ${product.status}`}>{product.status === 'awaiting-image' ? 'Needs photo' : product.status}</span>
            <div className="review-actions">{editingId === product.id ? <button onClick={()=>saveEdit(product)}>Save</button> : <button onClick={()=>startEdit(product)}><Pencil size={14}/> Edit</button>}</div>
          </article>)}</div>
        </section>}

        {menuDone && needsPhotos.length > 0 && <section className="onboarding-card">
          <div className="onboarding-card-head"><div><span className="kicker">PRODUCT PHOTOS</span><h2>Add the real food photos</h2><p>Each photo immediately moves that item into the 3D-generation pipeline.</p></div><Camera size={26}/></div>
          <div className="photo-checklist">{needsPhotos.slice(0,10).map(product => <article key={product.id}><div><strong>{product.name}</strong><span>{product.category} · Rs {Number(product.price || 0).toLocaleString()}</span></div><label className="photo-upload-mini"><Camera size={15}/>{photoUploadingId===product.id?'Uploading…':'Add photo'}<input type="file" accept="image/*" disabled={photoUploadingId===product.id} onChange={e=>{const f=e.target.files?.[0];e.target.value='';addPhoto(product,f)}} /></label></article>)}</div>
        </section>}

        {menuDone && <section className="onboarding-card onboarding-qr-card">
          <div className="onboarding-card-head"><div><span className="kicker">TABLE ENTRY</span><h2>{qrDone ? 'Your table QR is ready' : 'Create your first table QR'}</h2><p>Customers scan this code to open your Ashes menu without installing an app.</p></div><QrCode size={28}/></div>
          {!qrDone ? <div className="onboarding-qr-builder"><input value={tableCode} onChange={e=>setTableCode(e.target.value.toUpperCase())} placeholder="T01"/><button className="primary-btn" disabled={creatingQr} onClick={createFirstQr}>{creatingQr?'Creating…':'Create table QR'} <QrCode size={16}/></button></div> : <div className="onboarding-success-line"><Check size={18}/><span>{qrs.length} QR code{qrs.length===1?'':'s'} created. Add more from your dashboard anytime.</span></div>}
        </section>}

        {error && <div className="onboarding-error">{error}</div>}

        <div className="onboarding-launch-bar"><div><span>{launchReady ? 'READY FOR THE NEXT STEP' : 'KEEP GOING'}</span><strong>{launchReady ? 'Your restaurant foundation is ready.' : `${progress}% of setup complete`}</strong></div><button className="primary-btn" onClick={()=>setShowDashboard(true)}>{launchReady ? 'Enter Ashes dashboard' : 'Continue in dashboard'} <ChevronRight size={17}/></button></div>
      </section>
    </div>
  </main>;
}
