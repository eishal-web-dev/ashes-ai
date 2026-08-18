import crypto from 'node:crypto';

const CLIENT_ID = process.env.SHOPIFY_CLIENT_ID || 'c32e874c004cd9ea236c6c4af326f03a';
const SCOPES = 'read_products,write_products';
const REDIRECT_URI = 'https://ashes-ai.vercel.app/api/shopify/auth/callback';

function validShop(shop) {
  return /^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$/.test(String(shop || ''));
}

export default function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const shop = String(req.query?.shop || '').toLowerCase();
  if (!validShop(shop)) {
    return res.status(400).json({
      error: 'Missing or invalid shop. Use ?shop=your-store.myshopify.com',
    });
  }

  const state = crypto.randomBytes(24).toString('hex');
  res.setHeader(
    'Set-Cookie',
    `ashes_shopify_state=${state}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
  );
  res.setHeader('Cache-Control', 'no-store');

  const installUrl = new URL(`https://${shop}/admin/oauth/authorize`);
  installUrl.searchParams.set('client_id', CLIENT_ID);
  installUrl.searchParams.set('scope', SCOPES);
  installUrl.searchParams.set('redirect_uri', REDIRECT_URI);
  installUrl.searchParams.set('state', state);

  return res.redirect(302, installUrl.toString());
}
