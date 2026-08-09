import { useState } from 'react';
import { ArrowLeft, ArrowRight, Building2, LockKeyhole, Mail, MapPin, Sparkles, Store, User } from 'lucide-react';
import { loginBusiness, signupBusiness } from './api';

const selectStyle = {
  color: '#f7fbff',
  backgroundColor: '#111522',
  border: '1px solid rgba(98,239,255,.18)',
  borderRadius: '13px',
  minHeight: '48px',
  width: '100%',
  padding: '0 14px',
  outline: 'none',
  colorScheme: 'dark',
};

const optionStyle = { backgroundColor: '#0b0f18', color: '#f7fbff' };

export default function BusinessAuth({ onBack, onAuthenticated }) {
  const [mode, setMode] = useState('signup');
  const [form, setForm] = useState({ owner_name: '', email: '', password: '', business_name: '', kind: 'restaurant', city: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const session = mode === 'signup'
        ? await signupBusiness(form)
        : await loginBusiness(form.email, form.password);
      onAuthenticated(session);
    } catch (err) {
      setError(err.message || 'Could not continue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-shell">
      <div className="noise" />
      <div className="auth-topbar container">
        <button className="icon-button" onClick={onBack}><ArrowLeft size={18} /></button>
        <div className="brand"><span>ASHES</span><b>BUSINESS</b></div>
        <span className="business-badge">PARTNER ACCESS</span>
      </div>

      <section className="auth-layout container">
        <div className="auth-copy">
          <div className="eyebrow"><Sparkles size={14} /> BUILD YOUR DIGITAL TWIN CATALOG</div>
          <h1>Your business.<br/><span>Inside Ashes.</span></h1>
          <p>Create one account, add your café, restaurant or brand, upload products and let customers scan into 3D/AR experiences.</p>
          <div className="auth-benefits">
            <div><Store size={18}/><span>One Ashes account can power multiple businesses.</span></div>
            <div><Building2 size={18}/><span>Products stay separated by business tenant.</span></div>
            <div><Sparkles size={18}/><span>Every upload can flow into 3D + QR automatically.</span></div>
          </div>
        </div>

        <form className="auth-card glass-panel" onSubmit={submit}>
          <div className="auth-tabs">
            <button type="button" className={mode === 'signup' ? 'active' : ''} onClick={() => { setMode('signup'); setError(''); }}>Create account</button>
            <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError(''); }}>Sign in</button>
          </div>

          {mode === 'signup' && (
            <>
              <label><span><User size={14}/> Owner name</span><input value={form.owner_name} onChange={(e) => set('owner_name', e.target.value)} placeholder="Your name" required /></label>
              <label><span><Store size={14}/> Business name</span><input value={form.business_name} onChange={(e) => set('business_name', e.target.value)} placeholder="Neon Bites" required /></label>
              <div className="field-row two">
                <label>
                  <span><Building2 size={14}/> Business type</span>
                  <select style={selectStyle} value={form.kind} onChange={(e) => set('kind', e.target.value)}>
                    <option style={optionStyle} value="restaurant">Restaurant</option>
                    <option style={optionStyle} value="cafe">Café</option>
                    <option style={optionStyle} value="retail">Retail brand</option>
                    <option style={optionStyle} value="furniture">Furniture</option>
                    <option style={optionStyle} value="other">Other</option>
                  </select>
                </label>
                <label><span><MapPin size={14}/> City</span><input value={form.city} onChange={(e) => set('city', e.target.value)} placeholder="Peshawar" /></label>
              </div>
            </>
          )}

          <label><span><Mail size={14}/> Email</span><input type="email" value={form.email} onChange={(e) => set('email', e.target.value)} placeholder="owner@business.com" required /></label>
          <label><span><LockKeyhole size={14}/> Password</span><input type="password" value={form.password} onChange={(e) => set('password', e.target.value)} placeholder="8+ characters" minLength={8} required /></label>

          {error && <div className="auth-error">{error}</div>}

          <button className="primary-btn wide" disabled={loading}>{loading ? 'Connecting...' : mode === 'signup' ? 'Create Ashes business' : 'Enter dashboard'} <ArrowRight size={17}/></button>
          <p className="auth-footnote">MVP authentication. Before production launch we’ll add email verification, password reset and stricter deployment secrets.</p>
        </form>
      </section>
    </main>
  );
}
