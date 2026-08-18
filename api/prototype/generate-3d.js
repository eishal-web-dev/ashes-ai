const RAILWAY_API_BASE = 'https://courteous-learning-production-d31e.up.railway.app';

function send(res, status, body) {
  res.setHeader('Cache-Control', 'no-store');
  return res.status(status).json(body);
}

export default async function handler(req, res) {
  if (!['GET', 'POST'].includes(req.method)) {
    res.setHeader('Allow', 'GET, POST');
    return send(res, 405, { detail: 'Method not allowed.' });
  }

  try {
    const params = new URLSearchParams();
    if (req.method === 'GET' && req.query?.id) params.set('id', String(req.query.id));
    const suffix = params.toString() ? `?${params.toString()}` : '';

    const upstream = await fetch(`${RAILWAY_API_BASE}/api/prototype/generate-3d${suffix}`, {
      method: req.method,
      headers: {
        Accept: 'application/json',
        ...(req.method === 'POST' ? { 'Content-Type': 'application/json' } : {}),
      },
      body: req.method === 'POST' ? JSON.stringify(req.body || {}) : undefined,
      cache: 'no-store',
    });

    const text = await upstream.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { detail: 'Ashes Railway 3D API returned a non-JSON response.', upstream: text.slice(0, 500) };
    }

    return send(res, upstream.status || 502, data);
  } catch (error) {
    return send(res, 502, {
      detail: 'Could not reach the Ashes Railway 3D API.',
      error: error?.message || String(error),
    });
  }
}
