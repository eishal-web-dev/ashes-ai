const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const TOKEN_KEY = 'ashes_token';
const BUSINESS_KEY = 'ashes_business';
const USER_KEY = 'ashes_user';

export function getToken() { return localStorage.getItem(TOKEN_KEY); }
export function getStoredBusiness() { try { return JSON.parse(localStorage.getItem(BUSINESS_KEY) || 'null'); } catch { return null; } }
export function getStoredUser() { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; } }
export function saveSession(session) {
  if (session?.token) localStorage.setItem(TOKEN_KEY, session.token);
  if (session?.business) localStorage.setItem(BUSINESS_KEY, JSON.stringify(session.business));
  if (session?.user) localStorage.setItem(USER_KEY, JSON.stringify(session.user));
}
export function updateStoredBusiness(business) {
  if (business) localStorage.setItem(BUSINESS_KEY, JSON.stringify(business));
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
  const session = await apiFetch('/api/auth/signup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) });
  saveSession(session); return session;
}
export async function loginBusiness(email, password) {
  const session = await apiFetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
  saveSession(session); return session;
}
export async function getMe() { return apiFetch('/api/auth/me', {}, true); }
export async function getBusinessProfile(slug) { return apiFetch(`/api/businesses/${slug}`); }
export async function updateBusinessProfile(slug, values) {
  const business = await apiFetch(`/api/businesses/${slug}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
  }, true);
  updateStoredBusiness(business);
  return business;
}
export async function uploadBusinessLogo(slug, file) {
  const form = new FormData(); form.append('logo', file);
  const business = await apiFetch(`/api/storage/businesses/${slug}/logo`, { method: 'POST', body: form }, true);
  updateStoredBusiness(business);
  return business;
}
export async function importMenuCard(slug, file) {
  const form = new FormData();
  form.append('image', file);
  return apiFetch(`/api/storage/businesses/${slug}/import-menu-card`, { method: 'POST', body: form }, true);
}
export async function getMenuImports(slug) { return apiFetch(`/api/businesses/${slug}/menu-imports`, {}, true); }
export async function getProductBusiness(productId) { return apiFetch(`/api/products/${productId}/business`); }
export async function getBusinessProducts(slug, includeUnpublished = false) {
  return apiFetch(`/api/businesses/${slug}/products${includeUnpublished ? '?include_unpublished=true' : ''}`, {}, includeUnpublished);
}
export async function getBusinessAnalytics(slug) { return apiFetch(`/api/businesses/${slug}/analytics`, {}, true); }
export async function getBusinessOrders(slug) { return apiFetch(`/api/businesses/${slug}/orders`, {}, true); }
export async function getOrderNotifications(slug) { return apiFetch(`/api/businesses/${slug}/order-notifications`, {}, true); }
export async function updateOrderStatus(slug, orderId, status) {
  return apiFetch(`/api/businesses/${slug}/orders/${orderId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) }, true);
}
export async function getTableQrs(slug) { return apiFetch(`/api/businesses/${slug}/table-qrs`, {}, true); }
export async function createTableQr(slug, tableCode, productId = null) {
  return apiFetch(`/api/businesses/${slug}/table-qrs`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ table_code: tableCode, product_id: productId || null }),
  }, true);
}
export async function createOrder(values) {
  return apiFetch('/api/orders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) });
}
export async function getOrder(orderId) { return apiFetch(`/api/orders/${orderId}`); }
export async function createBusinessProduct(slug, values, imageFile) {
  const form = new FormData();
  form.append('name', values.name); form.append('price', values.price); form.append('category', values.category || 'Main');
  form.append('calories', values.calories || ''); form.append('protein', values.protein || ''); form.append('carbs', values.carbs || ''); form.append('fat', values.fat || ''); form.append('tags', values.tags || ''); form.append('image', imageFile);
  return apiFetch(`/api/storage/businesses/${slug}/products`, { method: 'POST', body: form }, true);
}
export async function attachBusinessProductPhoto(slug, productId, imageFile) {
  const form = new FormData();
  form.append('image', imageFile);
  return apiFetch(`/api/storage/businesses/${slug}/products/${productId}/image`, { method: 'POST', body: form }, true);
}
export async function updateBusinessProduct(slug, productId, values) {
  return apiFetch(`/api/businesses/${slug}/products/${productId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
  }, true);
}
export async function deleteBusinessProduct(slug, productId) {
  return apiFetch(`/api/storage/businesses/${slug}/products/${productId}`, { method: 'DELETE' }, true);
}
export async function getOwnedProduct(slug, productId) {
  return apiFetch(`/api/businesses/${slug}/products/${productId}`, {}, true);
}
export async function getProduct(productId) { return apiFetch(`/api/products/${productId}`); }
export async function trackProductEvent(productId, eventType) {
  if (!productId) return null;
  return apiFetch(`/api/products/${productId}/analytics`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_type: eventType }) });
}
export async function getBillingPlans() { return apiFetch('/api/billing/plans'); }
export async function getBusinessBilling(slug) { return apiFetch(`/api/businesses/${slug}/billing`, {}, true); }
export async function getBillingHistory(slug) { return apiFetch(`/api/businesses/${slug}/billing/history`, {}, true); }
export async function createBillingCheckout(slug, plan, successUrl = null, cancelUrl = null) {
  return apiFetch(`/api/businesses/${slug}/billing/checkout`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan, success_url: successUrl, cancel_url: cancelUrl }),
  }, true);
}
export async function getBillingCheckout(slug, intentId) {
  return apiFetch(`/api/businesses/${slug}/billing/checkout/${intentId}`, {}, true);
}
export async function devCompleteBillingCheckout(slug, intentId) {
  return apiFetch(`/api/businesses/${slug}/billing/checkout/${intentId}/dev-complete`, { method: 'POST' }, true);
}
export async function getManualPaymentMethods() { return apiFetch('/api/billing/manual-methods'); }
export async function submitManualPaymentProof(slug, values) {
  const form = new FormData();
  form.append('plan', values.plan);
  form.append('method', values.method);
  form.append('transaction_reference', values.transaction_reference || '');
  form.append('note', values.note || '');
  form.append('receipt', values.receipt);
  return apiFetch(`/api/businesses/${slug}/billing/manual-proof`, { method: 'POST', body: form }, true);
}
export async function getBusinessManualPaymentProofs(slug) { return apiFetch(`/api/businesses/${slug}/billing/manual-proofs`, {}, true); }

export async function getAdminOverview() { return apiFetch('/api/admin/overview', {}, true); }
export async function getAdminBusiness(businessId) { return apiFetch(`/api/admin/businesses/${businessId}`, {}, true); }
export async function setAdminBusinessStatus(businessId, action) {
  return apiFetch(`/api/admin/businesses/${businessId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }),
  }, true);
}
export async function getAdminJobs() { return apiFetch('/api/admin/jobs', {}, true); }
export async function getAdminBilling() { return apiFetch('/api/admin/billing', {}, true); }
export async function updateAdminBillingSettings(values) {
  return apiFetch('/api/admin/billing/settings', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
  }, true);
}
export async function getAdminManualPayments() { return apiFetch('/api/admin/manual-payments', {}, true); }
export async function updateAdminManualPaymentSettings(values) {
  return apiFetch('/api/admin/manual-payments/settings', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
  }, true);
}
export async function reviewAdminManualPayment(proofId, action, note = '') {
  return apiFetch(`/api/admin/manual-payments/${proofId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, note }),
  }, true);
}

export function absoluteApiUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}
