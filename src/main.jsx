import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import ProfileThemeEnhancer from './ProfileThemeEnhancer';
import DashboardUXEnhancer from './DashboardUXEnhancer';
import MerchantOperationsEnhancer from './MerchantOperationsEnhancer';
import CommerceSourceManager from './CommerceSourceManager';
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

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
    <ProfileThemeEnhancer />
    <DashboardUXEnhancer />
    <MerchantOperationsEnhancer />
    <CommerceSourceManager />
  </React.StrictMode>
);
