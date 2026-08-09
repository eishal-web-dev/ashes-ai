import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import ProfileThemeEnhancer from './ProfileThemeEnhancer';
import './styles.css';
import './ui-refresh.css';
import './app-polish.css';
import './dashboard-refresh.css';
import './website-refresh.css';
import './onboarding.css';
import './superadmin-refresh.css';
import './retail-warranty.css';
import './profile-themes.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
    <ProfileThemeEnhancer />
  </React.StrictMode>
);
