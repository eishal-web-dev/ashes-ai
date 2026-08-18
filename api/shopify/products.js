const RAILWAY_API_BASE = (process.env.ASHES_RAILWAY_API_BASE || 'https://courteous-learning-production-d31e.up.railway.app').replace(/\/$/, '');

function send(res, status, body) {
  res.setHeader('Cache-Control', 'no-store');
  return res.status(status).json(body);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return send(res, 405, { error: 'Method not allowed' });
  }

  try {
    const upstream = await fetch(`${RAILWAY_API_BASE}/api/shopify/products`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    const text = await upstream.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { error: 'Ashes Railway API returned a non-JSON response.', detail: text.slice(0, 500) };
    }

    return send(res, upstream.status || 502, data);
  } catch (error) {
    return send(res, 502, {
      error: 'Could not reach the Ashes Railway API.',
      detail: error?.message || String(error),
    });
  }
}
