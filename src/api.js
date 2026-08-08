const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const TOKEN_KEY = 'ashes_token';
const BUSINESS_KEY = 'ashes_business';
const USER_KEY = 'ashes_user';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredBusiness() {
  try { return JSON.parse(localStorage.getItem(BUSINESS_KEY) || 'null'); } catch { return null; }
}

export function getStoredUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; }
}

export function saveSession(session) {
  if (session?.token) localStorage.setItem(TOKEN_KEY, session.token);
  if (session?.business) localStorage.setItem(BUSINESS_KEY, JSON.stringify(session.business));
  if (session?.user) localStorage.setItem(USER_KEY, JSON.stringify(session.user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(BUSINESS_KEY);
  localStorage.removeItem(USER_KEY);
}

async function apiFetch(path, options = {}, authenticated = false) {
  const headers = { ...(options.headers || {}) };
  if (authenticated) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export async function signupBusiness(values) {
  const session = await apiFetch('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  });
  saveSession(session);
  return session;
}

export async function loginBusiness(email, password) {
  const session = await apiFetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  saveSession(session);
  return session;
}

export async function getMe() {
  return apiFetch('/api/auth/me', {}, true);
}

export async function getBusinessProducts(slug) {
  return apiFetch(`/api/businesses/${slug}/products`);
}

export async function getBusinessAnalytics(slug) {
  return apiFetch(`/api/businesses/${slug}/analytics`, {}, true);
}

export async function getBusinessOrders(slug) {
  return apiFetch(`/api/businesses/${slug}/orders`, {}, true);
}

export async function updateOrderStatus(slug, orderId, status) {
  return apiFetch(`/api/businesses/${slug}/orders/${orderId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }, true);
}

export async function createOrder(values) {
  return apiFetch('/api/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  });
}

export async function getOrder(orderId) {
  return apiFetch(`/api/orders/${orderId}`);
}

export async function createBusinessProduct(slug, values, imageFile) {
  const form = new FormData();
  form.append('name', values.name);
  form.append('price', values.price);
  form.append('category', values.category || 'Main');
  form.append('calories', values.calories || '');
  form.append('protein', values.protein || '');
  form.append('carbs', values.carbs || '');
  form.append('fat', values.fat || '');
  form.append('tags', values.tags || '');
  form.append('image', imageFile);
  return apiFetch(`/api/businesses/${slug}/products`, { method: 'POST', body: form }, true);
}

export async function getProduct(productId) {
  return apiFetch(`/api/products/${productId}`);
}

export async function trackProductEvent(productId, eventType) {
  if (!productId) return null;
  return apiFetch(`/api/products/${productId}/analytics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_type: eventType }),
  });
}

export function absoluteApiUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}
