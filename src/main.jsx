import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import './ui-refresh.css';
import './app-polish.css';
import './dashboard-refresh.css';
import './website-refresh.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
