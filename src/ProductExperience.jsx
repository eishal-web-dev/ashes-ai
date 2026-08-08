import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Float, useGLTF } from '@react-three/drei';
import { ArrowLeft, Box, Camera, Check, Flame, Leaf, LoaderCircle, Minus, Plus, ScanLine, ShoppingBag, Sparkles, Utensils, Wheat, X } from 'lucide-react';
import { absoluteApiUrl, createOrder, getProduct, trackProductEvent } from './api';

function DemoFoodModel() {
  return (
    <Float speed={1.4} rotationIntensity={0.22} floatIntensity={0.35}>
      <group rotation={[0.05, -0.35, 0]}>
        <mesh position={[0, 0.78, 0]} scale={[1.65, 0.5, 1.65]}><sphereGeometry args={[1, 64, 64]} /><meshStandardMaterial color="#ef9a42" roughness={0.42} metalness={0.05} /></mesh>
        <mesh position={[0, 0.32, 0]} scale={[1.55, 0.17, 1.55]}><cylinderGeometry args={[1, 1, 1, 64]} /><meshStandardMaterial color="#58c56c" roughness={0.72} /></mesh>
        <mesh position={[0, 0.08, 0]} scale={[1.42, 0.24, 1.42]}><cylinderGeometry args={[1, 1, 1, 64]} /><meshStandardMaterial color="#5b241d" roughness={0.82} /></mesh>
        <mesh position={[0, -0.18, 0]} rotation={[0, 0.2, 0]}><cylinderGeometry args={[1.28, 1.28, 0.14, 4]} /><meshStandardMaterial color="#ffd94a" roughness={0.45} /></mesh>
        <mesh position={[0, -0.43, 0]} scale={[1.48, 0.22, 1.48]}><cylinderGeometry args={[1, 1, 1, 64]} /><meshStandardMaterial color="#70261e" roughness={0.84} /></mesh>
        <mesh position={[0, -0.78, 0]} scale={[1.6, 0.35, 1.6]}><sphereGeometry args={[1, 64, 64]} /><meshStandardMaterial color="#d88635" roughness={0.52} /></mesh>
      </group>
    </Float>
  );
}

function GeneratedModel({ url }) {
  const gltf = useGLTF(url);
  return <Float speed={1.1} rotationIntensity={0.12} floatIntensity={0.22}><primitive object={gltf.scene} scale={2.1} /></Float>;
}

function Stat({ icon: Icon, label, value }) {
  return <div className="product-stat glass-panel"><Icon size={18} /><div><span>{label}</span><strong>{value}</strong></div></div>;
}

export default function ProductExperience({ onBack, productId: propProductId }) {
  const [mode, setMode] = useState('3d');
  const [product, setProduct] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [cartOpen, setCartOpen] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [tableCode, setTableCode] = useState(() => new URLSearchParams(window.location.search).get('table') || '');
  const [customerName, setCustomerName] = useState('');
  const [notes, setNotes] = useState('');
  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderResult, setOrderResult] = useState(null);
  const [orderError, setOrderError] = useState('');
  const arViewerRef = useRef(null);
  const trackedScanRef = useRef(false);
  const tracked3DRef = useRef(false);
  const productId = useMemo(() => propProductId || new URLSearchParams(window.location.search).get('product'), [propProductId]);

  useEffect(() => {
    if (!productId) return;
    let cancelled = false;
    let timer;
    if (!trackedScanRef.current) {
      trackedScanRef.current = true;
      trackProductEvent(productId, 'scan').catch(() => {});
    }
    const load = async () => {
      try {
        const data = await getProduct(productId);
        if (!cancelled) { setProduct(data); setLoadError(''); }
        if (!cancelled && ['queued', 'processing'].includes(data.status)) timer = setTimeout(load, 2500);
      } catch (error) {
        if (!cancelled) { setProduct(null); setLoadError(error?.message || 'Product could not be loaded'); }
      }
    };
    load();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [productId]);

  useEffect(() => {
    if (!productId || mode !== '3d' || tracked3DRef.current) return;
    tracked3DRef.current = true;
    trackProductEvent(productId, 'view_3d').catch(() => {});
  }, [mode, productId]);

  const data = product || {
    name: 'Quantum Smash Burger', price: 1290, calories: '~820 kcal', protein: '42 g', carbs: '56 g', fat: '47 g', tags: ['HIGH PROTEIN','HALAL','SPICY','DAIRY','GLUTEN'], status: productId ? 'loading' : 'demo', model_url: null,
  };
  const processing = ['queued', 'processing', 'awaiting-generator', 'loading'].includes(data.status);
  const modelUrl = data.model_url ? absoluteApiUrl(data.model_url) : null;
  const modelReady = data.status === 'ready' && Boolean(modelUrl);
  const total = Number(data.price || 0) * quantity;

  const launchAR = async () => {
    if (!modelReady || !arViewerRef.current) return;
    if (productId) trackProductEvent(productId, 'ar_launch').catch(() => {});
    try { await arViewerRef.current.activateAR(); } catch { setMode('ar'); }
  };

  const placeOrder = async () => {
    if (!productId) return;
    setPlacingOrder(true); setOrderError('');
    try {
      const order = await createOrder({
        items: [{ product_id: productId, quantity }],
        table_code: tableCode || null,
        customer_name: customerName || null,
        notes: notes || null,
      });
      setOrderResult(order);
    } catch (error) {
      setOrderError(error?.message || 'Could not place order');
    } finally {
      setPlacingOrder(false);
    }
  };

  return (
    <main className="product-page">
      <div className="scan-grid" />
      <header className="product-topbar">
        <button className="icon-button" onClick={onBack} aria-label="Back"><ArrowLeft size={20} /></button>
        <div className="brand-lockup"><div className="brand-mark">A</div><div><strong>ASHES AI</strong><span>LIVE EXPERIENCE</span></div></div>
        <button className="cart-pill" onClick={() => setCartOpen(true)}><ShoppingBag size={16} /> {quantity} · Rs {total.toLocaleString()}</button>
      </header>

      {modelReady && <model-viewer ref={arViewerRef} class="ashes-hidden-ar-viewer" src={modelUrl} ar ar-modes="webxr scene-viewer quick-look" camera-controls shadow-intensity="1" exposure="1" alt={data.name} />}

      <section className="product-experience-shell">
        <div className="product-visual glass-panel neon-edge">
          <div className="visual-toolbar">
            <div className="eyebrow"><Sparkles size={15} /> {modelReady ? 'AI GENERATED PRODUCT TWIN' : 'ASHES PRODUCT EXPERIENCE'}</div>
            <div className="mode-switch"><button className={mode === '3d' ? 'active' : ''} onClick={() => setMode('3d')}><Box size={16} /> 3D</button><button className={mode === 'ar' ? 'active' : ''} onClick={() => setMode('ar')}><Camera size={16} /> AR</button></div>
          </div>
          <div className="canvas-wrap">
            {mode === '3d' ? (
              <Canvas camera={{ position: [0, 0, 5.8], fov: 40 }}>
                <ambientLight intensity={1.6} /><pointLight position={[4, 5, 4]} intensity={28} color="#ff2aa3" /><pointLight position={[-4, 1, 3]} intensity={22} color="#21e8ff" />
                <Suspense fallback={null}>{modelReady ? <GeneratedModel url={modelUrl} /> : <DemoFoodModel />}</Suspense>
                <OrbitControls enablePan={false} minDistance={3.3} maxDistance={9} autoRotate autoRotateSpeed={0.7} />
              </Canvas>
            ) : (
              <div className="ar-placeholder"><div className="ar-reticle"><ScanLine size={54} /></div><h3>{modelReady ? 'Place it in your space' : 'Preparing AR asset'}</h3><p>{modelReady ? 'Ashes can hand this GLB to your device AR viewer.' : 'Ashes will enable placement once the generated 3D asset is ready.'}</p><button className="primary-action" disabled={!modelReady} onClick={launchAR}><Camera size={18} /> LAUNCH AR</button></div>
            )}
            {processing && <div className="floating-chip chip-one"><LoaderCircle size={13} className="spin-icon" /> {data.status === 'awaiting-generator' ? 'GENERATOR NEEDED' : data.status === 'loading' ? 'LOADING PRODUCT' : 'GENERATING 3D'}</div>}
            {modelReady && <div className="floating-chip chip-one">100% MODEL READY</div>}
            <div className="floating-chip chip-two">REAL-TIME 3D</div><div className="floating-chip chip-three">DRAG TO ROTATE</div>
          </div>
        </div>

        <aside className="product-info">
          <div className="merchant-line"><div className="merchant-logo">A</div><div><span>Now viewing</span><strong>Ashes Partner</strong></div></div>
          <div className="product-heading"><div className="eyebrow pink">ASHES EXPERIENCE</div><h1>{data.name}</h1><p>{processing ? 'Ashes is preparing the interactive 3D twin.' : 'Explore this product and order directly from your table.'}</p></div>
          <div className="price-row"><strong>Rs {Number(data.price || 0).toLocaleString()}</strong><span>{tableCode ? `Table ${tableCode}` : 'Table not set'}</span></div>
          <div className="stats-grid"><Stat icon={Flame} label="Calories" value={data.calories || '—'} /><Stat icon={Utensils} label="Protein" value={data.protein || '—'} /><Stat icon={Leaf} label="Carbs" value={data.carbs || '—'} /><Stat icon={Wheat} label="Fat" value={data.fat || '—'} /></div>
          <div className="tag-row">{(data.tags || []).map(tag => <span key={tag}>{tag}</span>)}</div>
          {loadError && <div className="allergen-note glass-panel"><strong>Product loading</strong><p>{loadError}</p></div>}
          {data.error_message && <div className="allergen-note glass-panel"><strong>3D pipeline status</strong><p>{data.error_message}</p></div>}
          <div className="cta-stack"><button className="primary-action wide" disabled={!modelReady} onClick={launchAR}><Camera size={19} /> VIEW ON MY TABLE</button><button className="secondary-action wide" onClick={() => setCartOpen(true)}><Utensils size={19} /> ADD TO ORDER</button></div>
        </aside>
      </section>

      {cartOpen && <div className="cart-backdrop" onClick={() => setCartOpen(false)}>
        <aside className="order-drawer glass-panel" onClick={e => e.stopPropagation()}>
          <div className="order-drawer-head"><div><span className="kicker">TABLE ORDER</span><h2>Your order</h2></div><button className="icon-button" onClick={() => setCartOpen(false)}><X size={18}/></button></div>
          {orderResult ? (
            <div className="order-success"><div className="success-icon"><Check size={28}/></div><h3>Order sent.</h3><p>Order <strong>#{orderResult.id.slice(0,8).toUpperCase()}</strong> is now in the restaurant queue.</p><div className="order-status-line"><span>Status</span><strong>{orderResult.status}</strong></div><div className="order-status-line"><span>Total</span><strong>Rs {Number(orderResult.total).toLocaleString()}</strong></div><button className="primary-btn wide" onClick={() => setCartOpen(false)}>Done</button></div>
          ) : (
            <>
              <div className="cart-product"><div><strong>{data.name}</strong><span>Rs {Number(data.price || 0).toLocaleString()} each</span></div><div className="qty-control"><button onClick={() => setQuantity(q => Math.max(1, q - 1))}><Minus size={15}/></button><strong>{quantity}</strong><button onClick={() => setQuantity(q => q + 1)}><Plus size={15}/></button></div></div>
              <label className="order-field"><span>Table number / code</span><input value={tableCode} onChange={e => setTableCode(e.target.value)} placeholder="T12" /></label>
              <label className="order-field"><span>Your name (optional)</span><input value={customerName} onChange={e => setCustomerName(e.target.value)} placeholder="Eishal" /></label>
              <label className="order-field"><span>Notes</span><textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="No onions, extra sauce…" /></label>
              <div className="order-total"><span>Total</span><strong>Rs {total.toLocaleString()}</strong></div>
              {orderError && <div className="form-error">{orderError}</div>}
              <button className="primary-btn wide" disabled={placingOrder} onClick={placeOrder}>{placingOrder ? 'Sending order…' : 'Send order to restaurant'} <ShoppingBag size={17}/></button>
            </>
          )}
        </aside>
      </div>}
    </main>
  );
}
