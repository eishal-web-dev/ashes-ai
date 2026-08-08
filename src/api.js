const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function getBusinessProducts(slug = 'neon-bites') {
  const response = await fetch(`${API_BASE}/api/businesses/${slug}/products`);
  if (!response.ok) throw new Error('Could not load products');
  return response.json();
}

export async function createBusinessProduct(slug = 'neon-bites', values, imageFile) {
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

  const response = await fetch(`${API_BASE}/api/businesses/${slug}/products`, {
    method: 'POST',
    body: form,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Could not create product');
  }

  return response.json();
}

export async function getProduct(productId) {
  const response = await fetch(`${API_BASE}/api/products/${productId}`);
  if (!response.ok) throw new Error('Product not found');
  return response.json();
}

export function absoluteApiUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}
