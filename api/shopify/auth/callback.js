import crypto from 'node:crypto';

const CLIENT_ID = process.env.SHOPIFY_CLIENT_ID || 'c32e874c004cd9ea236c6c4af326f03a';
const CLIENT_SECRET = process.env.SHOPIFY_CLIENT_SECRET;
const API_VERSION = '2026-07';

function validShop(shop) {
  return /^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$/.test(String(shop || ''));
}

function parseCookies(header = '') {
  return Object.fromEntries(
    String(header)
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const index = part.indexOf('=');
        return index === -1 ? [part, ''] : [part.slice(0, index), decodeURIComponent(part.slice(index + 1))];
      }),
  );
}

function safeEqual(a, b) {
  const left = Buffer.from(String(a || ''), 'utf8');
  const right = Buffer.from(String(b || ''), 'utf8');
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function verifyShopifyHmac(query, secret) {
  const provided = String(query.hmac || '');
  if (!provided || !secret) return false;

  const message = Object.keys(query)
    .filter((key) => key !== 'hmac' && key !== 'signature')
    .sort()
    .map((key) => `${key}=${Array.isArray(query[key]) ? query[key].join(',') : query[key]}`)
    .join('&');

  const digest = crypto.createHmac('sha256', secret).update(message).digest('hex');
  return safeEqual(digest, provided);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');

  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  if (!CLIENT_SECRET) {
    return res.status(500).json({
      error: 'SHOPIFY_CLIENT_SECRET is not configured in Vercel.',
    });
  }

  const shop = String(req.query?.shop || '').toLowerCase();
  const code = String(req.query?.code || '');
  const state = String(req.query?.state || '');
  const cookies = parseCookies(req.headers.cookie || '');

  if (!validShop(shop) || !code || !state) {
    return res.status(400).json({ error: 'Invalid Shopify OAuth callback.' });
  }

  if (!safeEqual(state, cookies.ashes_shopify_state || '')) {
    return res.status(403).json({ error: 'OAuth state validation failed.' });
  }

  if (!verifyShopifyHmac(req.query || {}, CLIENT_SECRET)) {
    return res.status(403).json({ error: 'Shopify HMAC validation failed.' });
  }

  try {
    const tokenResponse = await fetch(`https://${shop}/admin/oauth/access_token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET,
        code,
      }),
    });

    const tokenData = await tokenResponse.json().catch(() => ({}));
    if (!tokenResponse.ok || !tokenData.access_token) {
      return res.status(502).json({
        error: 'Shopify access-token exchange failed.',
        detail: tokenData.error_description || tokenData.error || null,
      });
    }

    const graphResponse = await fetch(`https://${shop}/admin/api/${API_VERSION}/graphql.json`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': tokenData.access_token,
      },
      body: JSON.stringify({
        query: `query AshesProducts {
          shop { name }
          products(first: 10) {
            nodes {
              id
              title
              handle
              status
              featuredMedia {
                preview { image { url } }
              }
            }
          }
        }`,
      }),
    });

    const graphData = await graphResponse.json().catch(() => ({}));
    if (!graphResponse.ok || graphData.errors) {
      return res.status(502).json({
        error: 'Shopify GraphQL product query failed.',
        detail: graphData.errors || null,
      });
    }

    res.setHeader(
      'Set-Cookie',
      'ashes_shopify_state=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0',
    );
    res.setHeader('Content-Type', 'text/html; charset=utf-8');

    const storeName = graphData.data?.shop?.name || shop;
    const products = graphData.data?.products?.nodes || [];
    const rows = products.length
      ? products
          .map(
            (product) => `<li style="margin:14px 0;padding:14px;border:1px solid #333;border-radius:12px;list-style:none">
              <strong>${escapeHtml(product.title)}</strong><br>
              <small>${escapeHtml(product.status)} · ${escapeHtml(product.handle)}</small>
            </li>`,
          )
          .join('')
      : '<li>No products found in this store yet.</li>';

    return res.status(200).send(`<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ashes Shopify Connected</title></head>
<body style="margin:0;background:#090909;color:#f5f5f5;font-family:Inter,Arial,sans-serif">
  <main style="max-width:760px;margin:60px auto;padding:24px">
    <p style="color:#ff7043;font-weight:700">ASHES × SHOPIFY</p>
    <h1 style="font-size:42px;margin-bottom:10px">Connected successfully 🔥</h1>
    <p>Ashes can now read products from <strong>${escapeHtml(storeName)}</strong>.</p>
    <h2 style="margin-top:36px">First ${products.length} products</h2>
    <ul style="padding:0">${rows}</ul>
    <p style="margin-top:36px;color:#aaa">OAuth works. The next milestone is saving the store token securely and sending a selected product image into the Ashes 3D engine.</p>
  </main>
</body>
</html>`);
  } catch (error) {
    return res.status(500).json({
      error: 'Shopify connection failed.',
      detail: error?.message || String(error),
    });
  }
}
