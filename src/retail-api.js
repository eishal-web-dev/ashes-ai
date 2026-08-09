import { getToken } from './api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(path, options = {}, auth = false) {
  const headers = { ...(options.headers || {}) };
  if (auth) {
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

export function getPublicRetailMetadata(productId) {
  return request(`/api/products/${productId}/retail-metadata`);
}

export function getOwnerRetailMetadata(slug, productId) {
  return request(`/api/businesses/${slug}/products/${productId}/retail-metadata`, {}, true);
}

export function saveOwnerRetailMetadata(slug, productId, values) {
  return request(`/api/businesses/${slug}/products/${productId}/retail-metadata`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  }, true);
}
