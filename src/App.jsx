import { useMemo, useState } from 'react';
import { ArrowRight, Box, Camera, QrCode, ScanLine, Sparkles, Store, Utensils, Zap } from 'lucide-react';
import ProductExperience from './ProductExperience';
import BusinessOnboardingShell from './BusinessOnboardingShell';
import BusinessAuth from './BusinessAuth';
import MenuExperience from './MenuExperience';
import AdminDashboard from './AdminDashboard';
import { getStoredBusiness, getStoredUser, getToken } from './api';

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

function AiHeroArtwork() {
  return (
    <div className="hero-visual" aria-label="Ashes AI futuristic 3D commerce visual">
      <div className="hero-hud-top"><span>ASHES // VISION</span><span className="hud-online">● ONLINE</span></div>
      <div className="orb orb-one" /><div className="orb orb-two" /><div className="scan-grid" />
      <div className="ai-portrait" aria-hidden="true">
        <div className="ai-halo halo-one" /><div className="ai-halo halo-two" />
        <div className="ai-head"><div className="ai-face-line face-line-a"/><div className="ai-face-line face-line-b"/><div className="ai-eye eye-left"/><div className="ai-eye eye-right"/><div className="ai-mouth"/></div>
        <div className="ai-neck"/><div className="ai-shoulders"/>
        <div className="scan-beam"/>
      </div>
      <div className="data-chip chip-one"><span>AI RECONSTRUCTION</span><b>98.7%</b></div>
      <div className="data-chip chip-two"><span>3D ASSET</span><b>GLB READY</b></div>
      <div className="data-chip chip-three"><span>AR LAYER</span><b>ACTIVE</b></div>
      <div className="data-chip chip-four"><span>OBJECT DEPTH</span><b>SYNCED</b></div>
      <div className="hero-hud-bottom"><span>PHOTO</span><i/><span>AI</span><i/><span>3D</span><i/><span>AR</span></div>
    </div>
  );
}

export default function App() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const deepLinkedProductId = params.get('product');
  const tableCode = params.get('table');
  const menuBusinessSlug = params.get('business');
  const adminPath = window.location.pathname === '/admin';
  const initialBusiness = getStoredBusiness();
  const initialUser = getStoredUser();
  const hasSession = Boolean(getToken() && initialBusiness);
  const initialView = adminPath ? 'admin' : (deepLinkedProductId ? 'product' : (tableCode && menuBusinessSlug ? 'menu' : 'home'));
  const [view, setView] = useState(initialView);
  const [business, setBusiness] = useState(initialBusiness);
  const [user, setUser] = useState(initialUser);
  const [activeProductId, setActiveProductId] = useState(deepLinkedProductId || null);

  const goHome = () => { if (window.location.pathname === '/admin' || window.location.search) window.history.replaceState({}, '', '/'); setActiveProductId(null); setView('home'); };
  const openBusiness = () => setView(hasSession || (business && getToken()) ? 'business' : 'auth');
  const handleAuthenticated = (session) => { setBusiness(session.business); setUser(session.user); setView(adminPath ? 'admin' : 'business'); };
  const openProduct = (productId) => { setActiveProductId(productId || null); setView('product'); };
  const logout = () => { setBusiness(null); setUser(null); setView('home'); };

  if (view === 'admin') { if (!getToken()) return <BusinessAuth onBack={goHome} onAuthenticated={handleAuthenticated} />; return <AdminDashboard onBack={goHome} />; }
  if (view === 'menu') return <MenuExperience businessSlug={menuBusinessSlug} tableCode={tableCode} onBack={goHome} onOpenProduct={openProduct} />;
  if (view === 'product') return <ProductExperience onBack={tableCode && menuBusinessSlug ? () => setView('menu') : goHome} productId={activeProductId || undefined} />;
  if (view === 'auth') return <BusinessAuth onBack={goHome} onAuthenticated={handleAuthenticated} />;
  if (view === 'business') return <BusinessOnboardingShell onBack={goHome} onOpenProduct={openProduct} business={business} user={user} onLogout={logout} onBusinessUpdated={setBusiness} />;

  return (
    <main className="site-shell">
      <div className="noise" />
      <nav className="nav container">
        <a className="brand" href="#top"><span>ASHES</span><b>AI</b></a>
        <div className="nav-links"><a href="#experiences">Experiences</a><a href="#how">How it works</a><a href="#business">For business</a></div>
        <button className="ghost-btn" onClick={openBusiness}>{business ? 'Dashboard' : 'Join Ashes'} <ArrowRight size={16} /></button>
      </nav>

      <section className="hero container" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><Zap size={14} /> AI COMMERCE, REBUILT</div>
          <h1>TURN PRODUCTS<br /><span>INTO EXPERIENCES.</span></h1>
          <p>One photo becomes an interactive 3D experience customers can scan, explore and place in their world.</p>
          <div className="hero-actions"><button className="primary-btn" onClick={() => openProduct(null)}>Try live scan demo <ArrowRight size={17} /></button><button className="secondary-btn" onClick={openBusiness}>{business ? 'Open dashboard' : 'Join as a business'}</button></div>
          <div className="proof-row"><div><strong>1</strong><span>photo to start</span></div><div><strong>3D</strong><span>web-ready output</span></div><div><strong>0</strong><span>apps to install</span></div></div>
        </div>
        <AiHeroArtwork />
      </section>

      <section className="experience-section container" id="experiences"><div className="section-head"><div><span className="kicker">BUILT FOR THE PHYSICAL WORLD</span><h2>One Ashes. Hundreds of businesses.</h2></div><p>Restaurants, cafés and shopping brands join the same platform. Their customers only need a QR scan.</p></div><div className="experience-grid">{experiences.map(({ icon: Icon, title, text }) => <article className="glass-card" key={title}><div className="icon-box"><Icon /></div><h3>{title}</h3><p>{text}</p><button className="text-btn" onClick={() => openProduct(null)}>View experience <ArrowRight size={15} /></button></article>)}</div></section>

      <section className="flow-section" id="how"><div className="container"><div className="section-head compact"><div><span className="kicker">FROM CAMERA TO COMMERCE</span><h2>Four steps. No friction.</h2></div></div><div className="steps-grid">{steps.map(({ n, icon: Icon, title, text }) => <article className="step-card" key={n}><span className="step-number">{n}</span><Icon className="step-icon" /><h3>{title}</h3><p>{text}</p></article>)}</div></div></section>

      <section className="business-section container" id="business"><div className="dashboard-preview"><div className="dashboard-top"><span>ASHES BUSINESS</span><span className="live-dot">● LIVE</span></div><div className="metric-grid"><div className="metric"><span>QR SCANS</span><strong>8,204</strong><em>+28.4%</em></div><div className="metric"><span>3D VIEWS</span><strong>6,911</strong><em>+19.8%</em></div><div className="metric"><span>AR LAUNCHES</span><strong>3,482</strong><em>+34.1%</em></div></div><div className="fake-chart">{[28,42,35,57,49,68,62,81,71,90,78,96].map((h,i)=><i key={i} style={{height:`${h}%`}} />)}</div></div><div className="business-copy"><span className="kicker">YOUR DIGITAL TWIN LAYER</span><h2>Built to sell to the next hundred cafés — not rebuild for each one.</h2><p>Every business gets its own profile, catalog, 3D assets, QR codes, analytics and billing while Ashes remains one platform.</p><button className="primary-btn" onClick={openBusiness}>{business ? 'Open your dashboard' : 'Become an Ashes business'} <ArrowRight size={17} /></button></div></section>

      <footer className="footer container"><div className="brand"><span>ASHES</span><b>AI</b></div><p>Scan reality. Experience products differently.</p><span>© 2026 Ashes AI</span></footer>
    </main>
  );
}
