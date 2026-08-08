import { Suspense, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Float } from '@react-three/drei';
import { ArrowLeft, Box, Camera, Flame, Leaf, ScanLine, Sparkles, Utensils, Wheat } from 'lucide-react';

function DemoFoodModel() {
  return (
    <Float speed={1.4} rotationIntensity={0.22} floatIntensity={0.35}>
      <group rotation={[0.05, -0.35, 0]}>
        <mesh position={[0, 0.78, 0]} scale={[1.65, 0.5, 1.65]}>
          <sphereGeometry args={[1, 64, 64]} />
          <meshStandardMaterial color="#ef9a42" roughness={0.42} metalness={0.05} />
        </mesh>
        <mesh position={[0, 0.32, 0]} scale={[1.55, 0.17, 1.55]}>
          <cylinderGeometry args={[1, 1, 1, 64]} />
          <meshStandardMaterial color="#58c56c" roughness={0.72} />
        </mesh>
        <mesh position={[0, 0.08, 0]} scale={[1.42, 0.24, 1.42]}>
          <cylinderGeometry args={[1, 1, 1, 64]} />
          <meshStandardMaterial color="#5b241d" roughness={0.82} />
        </mesh>
        <mesh position={[0, -0.18, 0]} rotation={[0, 0.2, 0]}>
          <cylinderGeometry args={[1.28, 1.28, 0.14, 4]} />
          <meshStandardMaterial color="#ffd94a" roughness={0.45} />
        </mesh>
        <mesh position={[0, -0.43, 0]} scale={[1.48, 0.22, 1.48]}>
          <cylinderGeometry args={[1, 1, 1, 64]} />
          <meshStandardMaterial color="#70261e" roughness={0.84} />
        </mesh>
        <mesh position={[0, -0.78, 0]} scale={[1.6, 0.35, 1.6]}>
          <sphereGeometry args={[1, 64, 64]} />
          <meshStandardMaterial color="#d88635" roughness={0.52} />
        </mesh>
      </group>
    </Float>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="product-stat glass-panel">
      <Icon size={18} />
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

export default function ProductExperience({ onBack }) {
  const [mode, setMode] = useState('3d');

  return (
    <main className="product-page">
      <div className="scan-grid" />
      <header className="product-topbar">
        <button className="icon-button" onClick={onBack} aria-label="Back">
          <ArrowLeft size={20} />
        </button>
        <div className="brand-lockup">
          <div className="brand-mark">A</div>
          <div>
            <strong>ASHES AI</strong>
            <span>LIVE EXPERIENCE</span>
          </div>
        </div>
        <div className="live-chip"><span /> QR CONNECTED</div>
      </header>

      <section className="product-experience-shell">
        <div className="product-visual glass-panel neon-edge">
          <div className="visual-toolbar">
            <div className="eyebrow"><Sparkles size={15} /> AI GENERATED PRODUCT TWIN</div>
            <div className="mode-switch">
              <button className={mode === '3d' ? 'active' : ''} onClick={() => setMode('3d')}><Box size={16} /> 3D</button>
              <button className={mode === 'ar' ? 'active' : ''} onClick={() => setMode('ar')}><Camera size={16} /> AR</button>
            </div>
          </div>

          <div className="canvas-wrap">
            {mode === '3d' ? (
              <Canvas camera={{ position: [0, 0, 5.8], fov: 40 }}>
                <ambientLight intensity={1.6} />
                <pointLight position={[4, 5, 4]} intensity={28} color="#ff2aa3" />
                <pointLight position={[-4, 1, 3]} intensity={22} color="#21e8ff" />
                <Suspense fallback={null}>
                  <DemoFoodModel />
                </Suspense>
                <OrbitControls enablePan={false} minDistance={4.1} maxDistance={8} autoRotate autoRotateSpeed={0.7} />
              </Canvas>
            ) : (
              <div className="ar-placeholder">
                <div className="ar-reticle"><ScanLine size={54} /></div>
                <h3>AR placement ready</h3>
                <p>Camera-based table placement will connect here once a generated GLB/USDZ asset is available.</p>
                <button className="primary-action"><Camera size={18} /> OPEN CAMERA</button>
              </div>
            )}
            <div className="floating-chip chip-one">98% MODEL READY</div>
            <div className="floating-chip chip-two">REAL-TIME 3D</div>
            <div className="floating-chip chip-three">DRAG TO ROTATE</div>
          </div>
        </div>

        <aside className="product-info">
          <div className="merchant-line">
            <div className="merchant-logo">NF</div>
            <div><span>Now viewing</span><strong>Neon Fork Cafe</strong></div>
          </div>

          <div className="product-heading">
            <div className="eyebrow pink">SIGNATURE COLLECTION</div>
            <h1>Quantum<br/><span>Smash Burger</span></h1>
            <p>Double flame-seared beef, molten cheddar, house neon sauce, crisp lettuce and toasted brioche.</p>
          </div>

          <div className="price-row">
            <strong>Rs 1,290</strong>
            <span>Available now</span>
          </div>

          <div className="stats-grid">
            <Stat icon={Flame} label="Calories" value="~820 kcal" />
            <Stat icon={Utensils} label="Protein" value="42 g" />
            <Stat icon={Leaf} label="Carbs" value="56 g" />
            <Stat icon={Wheat} label="Fat" value="47 g" />
          </div>

          <div className="tag-row">
            <span>HIGH PROTEIN</span><span>HALAL</span><span>SPICY</span><span>DAIRY</span><span>GLUTEN</span>
          </div>

          <div className="allergen-note glass-panel">
            <strong>Smart nutrition</strong>
            <p>Nutrition shown here is demo data. Ashes will support restaurant-verified values and clearly labelled AI estimates.</p>
          </div>

          <div className="cta-stack">
            <button className="primary-action wide"><Camera size={19} /> VIEW ON MY TABLE</button>
            <button className="secondary-action wide"><Utensils size={19} /> ADD TO ORDER</button>
          </div>
        </aside>
      </section>
    </main>
  );
}
