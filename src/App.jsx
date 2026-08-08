import { useState } from 'react';
import { ArrowRight, Box, Camera, QrCode, ScanLine, Sparkles, Store, Utensils, Zap } from 'lucide-react';
import ProductExperience from './ProductExperience';

const experiences = [
  { icon: Utensils, title: 'Restaurants', text: 'Interactive dishes, nutrition, allergens and AR table placement.' },
  { icon: Store, title: 'Retail Brands', text: 'Turn product photos into shoppable 3D experiences.' },
  { icon: Box, title: 'Furniture', text: 'Let customers preview pieces inside their own space.' },
];

const steps = [
  { n: '01', icon: Camera, title: 'Upload one photo', text: 'A business adds a product or dish with a clean image.' },
  { n: '02', icon: Sparkles, title: 'Ashes generates 3D', text: 'Our AI pipeline creates a web-ready 3D asset.' },
  { n: '03', icon: QrCode, title: 'Get a smart QR', text: 'Each business, table or product can have its own scan entry.' },
  { n: '04', icon: ScanLine, title: 'Customers explore', text: 'No separate app. Scan, rotate, inspect and launch AR instantly.' },
];

export default function App() {
  const [view, setView] = useState('home');

  if (view === 'product') {
    return <ProductExperience onBack={() => setView('home')} />;
  }

  return (
    <main className="site-shell">
      <div className="noise" />
      <nav className="nav container">
        <a className="brand" href="#top"><span>ASHES</span><b>AI</b></a>
        <div className="nav-links">
          <a href="#experiences">Experiences</a>
          <a href="#how">How it works</a>
          <a href="#business">For business</a>
        </div>
        <button className="ghost-btn">Join Ashes <ArrowRight size={16} /></button>
      </nav>

      <section className="hero container" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><Zap size={14} /> AI COMMERCE, REBUILT</div>
          <h1>TURN PRODUCTS<br /><span>INTO EXPERIENCES.</span></h1>
          <p>One photo becomes an interactive 3D experience customers can scan, explore and place in their world.</p>
          <div className="hero-actions">
            <button className="primary-btn" onClick={() => setView('product')}>Try live scan demo <ArrowRight size={17} /></button>
            <button className="secondary-btn">Join as a business</button>
          </div>
          <div className="proof-row">
            <div><strong>1</strong><span>photo to start</span></div>
            <div><strong>3D</strong><span>web-ready output</span></div>
            <div><strong>0</strong><span>apps to install</span></div>
          </div>
        </div>

        <div className="hero-visual" aria-label="Ashes AI 3D product preview concept">
          <div className="orb orb-one" />
          <div className="orb orb-two" />
          <div className="scan-grid" />
          <div className="product-core">
            <div className="product-ring ring-a" />
            <div className="product-ring ring-b" />
            <div className="product-object">A</div>
          </div>
          <div className="data-chip chip-one"><span>AI GENERATED</span><b>98%</b></div>
          <div className="data-chip chip-two"><span>3D READY</span><b>GLB</b></div>
          <div className="data-chip chip-three"><span>AR ENABLED</span><b>LIVE</b></div>
          <div className="data-chip chip-four"><span>SCANS</span><b>482</b></div>
        </div>
      </section>

      <section className="experience-section container" id="experiences">
        <div className="section-head">
          <div><span className="kicker">BUILT FOR THE PHYSICAL WORLD</span><h2>One Ashes. Hundreds of businesses.</h2></div>
          <p>Restaurants, cafés and shopping brands join the same platform. Their customers only need a QR scan.</p>
        </div>
        <div className="experience-grid">
          {experiences.map(({ icon: Icon, title, text }) => (
            <article className="glass-card" key={title}>
              <div className="icon-box"><Icon /></div>
              <h3>{title}</h3>
              <p>{text}</p>
              <button className="text-btn" onClick={() => setView('product')}>View experience <ArrowRight size={15} /></button>
            </article>
          ))}
        </div>
      </section>

      <section className="flow-section" id="how">
        <div className="container">
          <div className="section-head compact">
            <div><span className="kicker">FROM CAMERA TO COMMERCE</span><h2>Four steps. No friction.</h2></div>
          </div>
          <div className="steps-grid">
            {steps.map(({ n, icon: Icon, title, text }) => (
              <article className="step-card" key={n}>
                <span className="step-number">{n}</span>
                <Icon className="step-icon" />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="business-section container" id="business">
        <div className="dashboard-preview">
          <div className="dashboard-top"><span>ASHES BUSINESS</span><span className="live-dot">● LIVE</span></div>
          <div className="metric-grid">
            <div className="metric"><span>QR SCANS</span><strong>8,204</strong><em>+28.4%</em></div>
            <div className="metric"><span>3D VIEWS</span><strong>6,911</strong><em>+19.8%</em></div>
            <div className="metric"><span>AR LAUNCHES</span><strong>3,482</strong><em>+34.1%</em></div>
          </div>
          <div className="fake-chart">
            {[28, 42, 35, 57, 49, 68, 62, 81, 71, 90, 78, 96].map((h, i) => <i key={i} style={{height: `${h}%`}} />)}
          </div>
        </div>
        <div className="business-copy">
          <span className="kicker">YOUR DIGITAL TWIN LAYER</span>
          <h2>Built to sell to the next hundred cafés — not rebuild for each one.</h2>
          <p>Every business gets its own profile, catalog, 3D assets, QR codes, analytics and billing while Ashes remains one platform.</p>
          <button className="primary-btn">Become an Ashes business <ArrowRight size={17} /></button>
        </div>
      </section>

      <footer className="footer container">
        <div className="brand"><span>ASHES</span><b>AI</b></div>
        <p>Scan reality. Experience products differently.</p>
        <span>© 2026 Ashes AI</span>
      </footer>
    </main>
  );
}
