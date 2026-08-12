import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import ProfileThemeEnhancer from './ProfileThemeEnhancer';
import DashboardUXEnhancer from './DashboardUXEnhancer';
import MerchantOperationsEnhancer from './MerchantOperationsEnhancer';
import CommerceSourceManager from './CommerceSourceManager';
import PricingModelEnhancer from './PricingModelEnhancer';
import './styles.css';
import './ui-refresh.css';
import './app-polish.css';
import './dashboard-refresh.css';
import './website-refresh.css';
import './onboarding.css';
import './superadmin-refresh.css';
import './retail-warranty.css';
import './profile-themes.css';
import './consumer-checkout.css';
import './customer-cart.css';
import './product-configurator.css';
import './customer-storefront.css';
import './order-tracking.css';
import './qr-studio.css';
import './merchant-operations.css';
import './commerce-sources.css';
import './final-ui.css';
import './pricing-model.css';
import './prototype-studio.css';


// The public prototype changes rapidly during demos. Remove older PWA bundles on
// this route so customers never see a stale product viewer after a deployment.
if ('serviceWorker' in navigator && window.location.pathname.startsWith('/prototype')) {
  Promise.all([
    navigator.serviceWorker.getRegistrations().then(registrations=>Promise.all(registrations.map(registration=>registration.unregister()))),
    'caches' in window ? caches.keys().then(keys=>Promise.all(keys.filter(key=>/workbox|precache|ashes/i.test(key)).map(key=>caches.delete(key)))) : Promise.resolve()
  ]).then(()=>{
    if(navigator.serviceWorker.controller&&!sessionStorage.getItem('ashes-prototype-cache-cleared')){
      sessionStorage.setItem('ashes-prototype-cache-cleared','1');
      window.location.reload();
    }
  });
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
    <ProfileThemeEnhancer />
    <DashboardUXEnhancer />
    <MerchantOperationsEnhancer />
    <CommerceSourceManager />
    <PricingModelEnhancer />
  </React.StrictMode>
);
