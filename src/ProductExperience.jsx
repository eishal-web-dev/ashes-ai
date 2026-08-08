import { Suspense, useEffect, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Float, useGLTF } from '@react-three/drei';
import { ArrowLeft, Box, Camera, Flame, Leaf, LoaderCircle, ScanLine, Sparkles, Utensils, Wheat } from 'lucide-react';
import { getProduct } from './api';

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
  return (
    <Float speed={1.1} rotationIntensity={0.12} floatIntensity={0.22}>
      <primitive object={gltf.scene} scale={2.1} />
    </Float>
  );
}

function Stat({ icon: Icon, label, value }) {
  return <div className="product-stat glass-panel"><Icon size={18} /><div><span>{label}</span><strong>{value}</strong></div></div>;
}

export default function ProductExperience({ onBack, productId: propProductId }) {
  const [mode, setMode] = useState('3d');
  const [product, setProduct] = useState(null);
  const productId = useMemo(() => propProductId || new URLSearchParams(window.location.search).get('product'), [propProductId]);

  useEffect(() => {
    if (!productId) return;
    let cancelled = false;
    let timer;

    const load = async () => {
      try {
        const data = await getProduct(productId);
        if (!cancelled) setProduct(data);
        if (!cancelled && ['queued', 'processing'].includes(data.status)) timer = setTimeout(load, 2500);
      } catch {
        if (!cancelled) setProduct(null);
      }
    };

    load();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [productId]);

  const data = product || {
    name: 'Quantum Smash Burger', price: 1290, calories: '~820 kcal', protein: '42 g', carbs: '56 g', fat: '47 g', tags: ['HIGH PROTEIN','HALAL','SPICY','DAIRY','GLUTEN'], status: 'demo', model_url: null,
  };

  const processing = ['queued', 'processing', 'awaiting-generator'].includes(data.status);
  const modelReady = data.status === 'ready' && data.model_url;

  return (
    <main className="product-page">
      <div className="scan-grid" />
      <header className="product-topbar">
        <button className="icon-button" onClick={onBack} aria-label="Back"><ArrowLeft size={20} /></button>
        <div className="brand-lockup"><div className="brand-mark">A</div><div><strong>ASHES AI</strong><span>LIVE EXPERIENCE</span></div></div>
        <div className="live-chip"><span /> {modelReady ? '3D READY' : processing ? 'AI PROCESSING' : 'QR CONNECTED'}</div>
      </header>

      <section className="product-experience-shell">
        <div className="product-visual glass-panel neon-edge">
          <div className="visual-toolbar">
            <div className="eyebrow"><Sparkles size={15} /> {modelReady ? 'AI GENERATED PRODUCT TWIN' : 'ASHES PRODUCT EXPERIENCE'}</div>
            <div className="mode-switch"><button className={mode === '3d' ? 'active' : ''} onClick={() => setMode('3d')}><Box size={16} /> 3D</button><button className={mode === 'ar' ? 'active' : ''} onClick={() => setMode('ar')}><Camera size={16} /> AR</button></div>
          </div>

          <div className="canvas-wrap">
            {mode === '3d' ? (
              <Canvas camera={{ position: [0, 0, 5.8], fov: 40 }}>
                <ambientLight intensity={1.6} />
                <pointLight position={[4, 5, 4]} intensity={28} color="#ff2aa3" />
                <pointLight position={[-4, 1, 3]} intensity={22} color="#21e8ff" />
                <Suspense fallback={null}>{modelReady ? <GeneratedModel url={data.model_url} /> : <DemoFoodModel />}</Suspense>
                <OrbitControls enablePan={false} minDistance={3.3} maxDistance={9} autoRotate autoRotateSpeed={0.7} />
              </Canvas>
            ) : (
              <div className="ar-placeholder"><div className="ar-reticle"><ScanLine size={54} /></div><h3>{modelReady ? 'AR asset ready' : 'Preparing AR asset'}</h3><p>{modelReady ? 'This product now has a GLB ready for the browser AR hand-off.' : 'Ashes will enable table placement once the generated GLB is ready.'}</p><button className="primary-action" disabled={!modelReady}><Camera size={18} /> OPEN CAMERA</button></div>
            )}
            {processing && <div className="floating-chip chip-one"><LoaderCircle size={13} className="spin-icon" /> {data.status === 'awaiting-generator' ? 'GENERATOR NEEDED' : 'GENERATING 3D'}</div>}
            {modelReady && <div className="floating-chip chip-one">100% MODEL READY</div>}
            <div className="floating-chip chip-two">REAL-TIME 3D</div><div className="floating-chip chip-three">DRAG TO ROTATE</div>
          </div>
        </div>

        <aside className="product-info">
          <div className="merchant-line"><div className="merchant-logo">NB</div><div><span>Now viewing</span><strong>Neon Bites</strong></div></div>
          <div className="product-heading"><div className="eyebrow pink">ASHES EXPERIENCE</div><h1>{data.name}</h1><p>{processing ? 'Your product has been saved. Ashes is preparing its interactive 3D twin.' : 'Explore this product as an interactive Ashes AI experience.'}</p></div>
          <div className="price-row"><strong>Rs {Number(data.price || 0).toLocaleString()}</strong><span>{modelReady ? '3D ready' : data.status}</span></div>
          <div className="stats-grid"><Stat icon={Flame} label="Calories" value={data.calories || '—'} /><Stat icon={Utensils} label="Protein" value={data.protein || '—'} /><Stat icon={Leaf} label="Carbs" value={data.carbs || '—'} /><Stat icon={Wheat} label="Fat" value={data.fat || '—'} /></div>
          <div className="tag-row">{(data.tags || []).map(tag => <span key={tag}>{tag}</span>)}</div>
          {data.error_message && <div className="allergen-note glass-panel"><strong>3D pipeline status</strong><p>{data.error_message}</p></div>}
          <div className="allergen-note glass-panel"><strong>Smart nutrition</strong><p>Restaurant-provided values should be treated as authoritative. AI estimates should stay clearly labelled until approved.</p></div>
          <div className="cta-stack"><button className="primary-action wide" disabled={!modelReady}><Camera size={19} /> VIEW ON MY TABLE</button><button className="secondary-action wide"><Utensils size={19} /> ADD TO ORDER</button></div>
        </aside>
      </section>
    </main>
  );
}
