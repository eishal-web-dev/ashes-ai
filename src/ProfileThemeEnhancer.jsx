import { useEffect } from 'react';

const BUSINESS_THEMES = [
  { key: 'ashes-pink', name: 'Ashes Pink', mood: 'Signature · Electric', colors: ['#07070b','#15111a','#ff2f9f','#8b5cf6','#f7f4fb'], accent: '#ff2f9f', bg: '#07070b', surface: '#15111a', secondary: '#8b5cf6', text: '#f7f4fb' },
  { key: 'midnight-gold', name: 'Midnight Gold', mood: 'Luxury · Premium', colors: ['#070705','#17150f','#d8a83e','#6f5824','#fff6dc'], accent: '#d8a83e', bg: '#070705', surface: '#17150f', secondary: '#6f5824', text: '#fff6dc' },
  { key: 'electric-violet', name: 'Electric Violet', mood: 'AI · Futuristic', colors: ['#070611','#151126','#8b5cf6','#22d3ee','#f5f3ff'], accent: '#8b5cf6', bg: '#070611', surface: '#151126', secondary: '#22d3ee', text: '#f5f3ff' },
  { key: 'ocean-glass', name: 'Ocean Glass', mood: 'Clean · Digital', colors: ['#031014','#0a2028','#19c7c9','#3978ff','#eaffff'], accent: '#19c7c9', bg: '#031014', surface: '#0a2028', secondary: '#3978ff', text: '#eaffff' },
  { key: 'emerald-noir', name: 'Emerald Noir', mood: 'Fresh · Modern', colors: ['#050b08','#101c16','#26d07c','#147a55','#effff6'], accent: '#26d07c', bg: '#050b08', surface: '#101c16', secondary: '#147a55', text: '#effff6' },
  { key: 'cherry-luxe', name: 'Cherry Luxe', mood: 'Bold · Fashion', colors: ['#100508','#211014','#ff416c','#8f1738','#fff0f4'], accent: '#ff416c', bg: '#100508', surface: '#211014', secondary: '#8f1738', text: '#fff0f4' },
  { key: 'warm-sand', name: 'Warm Sand', mood: 'Editorial · Soft', colors: ['#16110c','#292016','#d7a86e','#8c6743','#fff8ed'], accent: '#d7a86e', bg: '#16110c', surface: '#292016', secondary: '#8c6743', text: '#fff8ed' },
  { key: 'cyber-blue', name: 'Cyber Blue', mood: 'Tech · Sharp', colors: ['#030814','#0a1528','#2f80ff','#00d9ff','#edf7ff'], accent: '#2f80ff', bg: '#030814', surface: '#0a1528', secondary: '#00d9ff', text: '#edf7ff' },
  { key: 'monochrome', name: 'Monochrome', mood: 'Minimal · Timeless', colors: ['#060606','#171717','#f4f4f4','#777777','#ffffff'], accent: '#f4f4f4', bg: '#060606', surface: '#171717', secondary: '#777777', text: '#ffffff' },
  { key: 'rose-quartz', name: 'Rose Quartz', mood: 'Soft · Lifestyle', colors: ['#120b0f','#261820','#f39ab6','#b76a86','#fff1f6'], accent: '#f39ab6', bg: '#120b0f', surface: '#261820', secondary: '#b76a86', text: '#fff1f6' },
];

const ADMIN_THEMES = [
  { key: 'command-amber', name: 'Command Amber', mood: 'System · Authority', colors: ['#050505','#15130e','#ffb020','#6f4f13','#fff4d6'], accent: '#ffb020', bg: '#050505', surface: '#15130e', secondary: '#6f4f13', text: '#fff4d6' },
  { key: 'control-ice', name: 'Control Ice', mood: 'Operations · Clean', colors: ['#04090d','#0c1820','#5ce1e6','#2d75ff','#effdff'], accent: '#5ce1e6', bg: '#04090d', surface: '#0c1820', secondary: '#2d75ff', text: '#effdff' },
  { key: 'obsidian', name: 'Obsidian', mood: 'Executive · Minimal', colors: ['#030303','#111111','#d9d9d9','#565656','#ffffff'], accent: '#d9d9d9', bg: '#030303', surface: '#111111', secondary: '#565656', text: '#ffffff' },
  { key: 'signal-red', name: 'Signal Red', mood: 'Security · Critical', colors: ['#0b0506','#1b0d10','#ff4d5f','#8b1e2c','#fff1f2'], accent: '#ff4d5f', bg: '#0b0506', surface: '#1b0d10', secondary: '#8b1e2c', text: '#fff1f2' },
  { key: 'quantum-violet', name: 'Quantum Violet', mood: 'AI · Platform', colors: ['#070511','#161027','#a26cff','#365cff','#f7f2ff'], accent: '#a26cff', bg: '#070511', surface: '#161027', secondary: '#365cff', text: '#f7f2ff' },
  { key: 'matrix-green', name: 'Matrix Green', mood: 'Infra · Live', colors: ['#020805','#0c1711','#52e58a','#17824a','#ecfff4'], accent: '#52e58a', bg: '#020805', surface: '#0c1711', secondary: '#17824a', text: '#ecfff4' },
];

function readLocal(key) { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { return null; } }

function setNativeInputValue(input, value) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

function applyTheme(root, theme, mode) {
  if (!root || !theme) return;
  root.style.setProperty(mode === 'admin' ? '--admin-accent' : '--business-accent', theme.accent);
  root.style.setProperty('--profile-theme-bg', theme.bg);
  root.style.setProperty('--profile-theme-surface', theme.surface);
  root.style.setProperty('--profile-theme-secondary', theme.secondary);
  root.style.setProperty('--profile-theme-text', theme.text);
  root.dataset.profileTheme = theme.key;
  localStorage.setItem(mode === 'admin' ? 'ashes_admin_theme' : 'ashes_business_theme', theme.key);
}

function themeCard(theme, current, onPick) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `palette-card${theme.key === current ? ' selected' : ''}`;
  button.innerHTML = `
    <div class="palette-art">
      <div class="palette-art-nav"></div>
      <div class="palette-art-hero" style="background:linear-gradient(135deg,${theme.surface},${theme.bg})">
        <i style="background:${theme.accent}"></i><i style="background:${theme.secondary}"></i>
      </div>
      <div class="palette-art-row"><i style="background:${theme.colors[0]}"></i><i style="background:${theme.colors[1]}"></i><i style="background:${theme.colors[2]}"></i><i style="background:${theme.colors[3]}"></i><i style="background:${theme.colors[4]}"></i></div>
    </div>
    <div class="palette-card-copy"><strong>${theme.name}</strong><span>${theme.mood}</span></div>
    <span class="palette-check">✓</span>`;
  button.addEventListener('click', () => onPick(theme));
  return button;
}

function mountBusinessProfileHeader() {
  const panel = document.querySelector('.business-shell #business-settings');
  if (!panel || panel.querySelector('.business-profile-studio')) return;
  const business = readLocal('ashes_business') || {};
  const user = readLocal('ashes_user') || {};
  const logo = panel.querySelector('.brand-logo-preview img')?.src || '';
  const initial = (business.name || user.name || 'A').slice(0,1).toUpperCase();
  const themeKey = localStorage.getItem('ashes_business_theme') || 'ashes-pink';
  const theme = BUSINESS_THEMES.find(t => t.key === themeKey) || BUSINESS_THEMES[0];
  const card = document.createElement('div');
  card.className = 'business-profile-studio';
  card.innerHTML = `
    <div class="business-profile-cover"><div class="profile-cover-glow one"></div><div class="profile-cover-glow two"></div><div class="profile-cover-grid"></div></div>
    <div class="business-profile-main">
      <div class="business-profile-avatar">${logo ? `<img src="${logo}" alt="${business.name || 'Business'}">` : `<span>${initial}</span>`}<b>✓</b></div>
      <div class="business-profile-copy"><span>ASHES BUSINESS PROFILE</span><h2>${business.name || 'Your business'}</h2><p>@${business.slug || 'business'} · ${business.kind || 'business'}${business.city ? ` · ${business.city}` : ''}</p><div class="profile-chip-row"><i>LIVE PROFILE</i><i>${user.email || 'Owner account'}</i><i>${theme.name}</i></div></div>
      <div class="business-profile-score"><span>PROFILE</span><strong>${business.logo_url && business.city ? '90%' : business.city ? '75%' : '60%'}</strong><small>Brand readiness</small></div>
    </div>
    <div class="business-profile-preview-strip"><span>QR EXPERIENCE THEME</span><div class="profile-palette-dots">${theme.colors.map(c => `<i style="background:${c}"></i>`).join('')}</div><b>${theme.name}</b></div>`;
  panel.prepend(card);
}

function mountBusinessGallery() {
  const field = document.querySelector('.business-shell .accent-field');
  const root = document.querySelector('.business-shell');
  if (!field || !root || field.dataset.galleryMounted === 'true') return;
  field.dataset.galleryMounted = 'true';
  field.classList.add('accent-field-upgraded');

  const input = field.querySelector('input[type="color"]');
  const oldValue = input?.value?.toLowerCase();
  let selected = localStorage.getItem('ashes_business_theme') || BUSINESS_THEMES.find(t => t.accent.toLowerCase() === oldValue)?.key || 'ashes-pink';
  const initialTheme = BUSINESS_THEMES.find(t => t.key === selected) || BUSINESS_THEMES[0];
  applyTheme(root, initialTheme, 'business');

  const wrapper = document.createElement('div');
  wrapper.className = 'theme-gallery business-theme-gallery';
  wrapper.innerHTML = `<div class="theme-gallery-head"><div><span>BRAND THEME</span><h3>Choose your visual world</h3><p>Pick a complete palette instead of a single color. Your Ashes profile, QR experience and dashboard preview adapt instantly.</p></div><b>${BUSINESS_THEMES.length} themes</b></div><div class="palette-grid"></div><div class="custom-palette-row"><div><strong>Need your exact brand color?</strong><span>Use Custom only when none of the curated palettes fit.</span></div><label class="custom-color-button">Custom <input type="color" value="${oldValue || '#ff2f9f'}"></label></div>`;

  const grid = wrapper.querySelector('.palette-grid');
  const render = () => {
    grid.innerHTML = '';
    BUSINESS_THEMES.forEach(theme => grid.appendChild(themeCard(theme, selected, picked => {
      selected = picked.key;
      applyTheme(root, picked, 'business');
      if (input) setNativeInputValue(input, picked.accent);
      const custom = wrapper.querySelector('.custom-color-button input');
      if (custom) custom.value = picked.accent;
      const strip = root.querySelector('.business-profile-preview-strip');
      if (strip) { strip.querySelector('b').textContent = picked.name; strip.querySelector('.profile-palette-dots').innerHTML = picked.colors.map(c => `<i style="background:${c}"></i>`).join(''); }
      render();
    })));
  };
  render();

  wrapper.querySelector('.custom-color-button input')?.addEventListener('input', e => {
    selected = 'custom';
    const custom = { key: 'custom', accent: e.target.value, bg: '#07070b', surface: '#15111a', secondary: e.target.value, text: '#ffffff' };
    applyTheme(root, custom, 'business');
    if (input) setNativeInputValue(input, e.target.value);
    render();
  });

  field.querySelector(':scope > span')?.remove();
  const legacy = field.querySelector(':scope > div');
  if (legacy) legacy.style.display = 'none';
  field.appendChild(wrapper);
}

function mountAdminProfile() {
  const shell = document.querySelector('.admin-shell');
  const main = shell?.querySelector('.admin-main');
  if (!shell || !main || main.querySelector('.superadmin-profile-studio')) return;
  let selected = localStorage.getItem('ashes_admin_theme') || 'command-amber';
  applyTheme(shell, ADMIN_THEMES.find(t => t.key === selected) || ADMIN_THEMES[0], 'admin');

  const user = readLocal('ashes_user');
  const name = user?.name || 'Super Admin';
  const email = user?.email || 'Platform owner';
  const initials = name.split(/\s+/).map(x => x[0]).join('').slice(0,2).toUpperCase() || 'SA';

  const studio = document.createElement('section');
  studio.className = 'superadmin-profile-studio';
  studio.innerHTML = `<div class="admin-profile-card"><div class="admin-profile-avatar">${initials}<i>✓</i></div><div class="admin-profile-copy"><span>PLATFORM OWNER</span><h2>${name}</h2><p>${email}</p></div><div class="admin-profile-badge">SUPER ADMIN</div><div class="admin-owner-stats"><span><b>FULL</b> ACCESS</span><span><b>LIVE</b> PLATFORM</span><span><b>2FA</b> READY</span></div><div class="admin-security-note"><strong>Owner console</strong><span>Theme and platform controls are isolated from merchant accounts.</span></div></div><div class="admin-theme-studio"><div class="theme-gallery-head"><div><span>CONTROL CENTER APPEARANCE</span><h3>Command themes</h3><p>Your admin console has its own identity, separate from every merchant.</p></div><b>${ADMIN_THEMES.length} systems</b></div><div class="palette-grid admin-palette-grid"></div></div>`;
  const grid = studio.querySelector('.palette-grid');
  const render = () => {
    grid.innerHTML = '';
    ADMIN_THEMES.forEach(theme => grid.appendChild(themeCard(theme, selected, picked => {
      selected = picked.key;
      applyTheme(shell, picked, 'admin');
      render();
    })));
  };
  render();
  main.prepend(studio);
}

export default function ProfileThemeEnhancer() {
  useEffect(() => {
    const sync = () => { mountBusinessProfileHeader(); mountBusinessGallery(); mountAdminProfile(); };
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);
  return null;
}
