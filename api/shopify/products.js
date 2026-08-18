const CLIENT_ID = process.env.SHOPIFY_CLIENT_ID || 'c32e874c004cd9ea236c6c4af326f03a';
const CLIENT_SECRET = process.env.SHOPIFY_CLIENT_SECRET;
const SHOP = process.env.SHOPIFY_SHOP || 'ashes-stack.myshopify.com';
const API_VERSION = '2026-07';

function send(res, status, body) {
  res.setHeader('Cache-Control', 'no-store');
  return res.status(status).json(body);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return send(res, 405, { error: 'Method not allowed' });
  }

  if (!CLIENT_SECRET) {
    return send(res, 500, { error: 'SHOPIFY_CLIENT_SECRET is not configured in Vercel.' });
  }

  try {
    const body = new URLSearchParams({
      grant_type: 'client_credentials',
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
    });

    const tokenResponse = await fetch(`https://${SHOP}/admin/oauth/access_token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      },
      body,
    });

    const tokenData = await tokenResponse.json().catch(() => ({}));
    if (!tokenResponse.ok || !tokenData.access_token) {
      return send(res, tokenResponse.status || 502, {
        error: 'Shopify client credentials grant failed.',
        detail: tokenData.error_description || tokenData.error || tokenData,
      });
    }

    const graphResponse = await fetch(`https://${SHOP}/admin/api/${API_VERSION}/graphql.json`, {
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
      const messages = Array.isArray(graphData.errors)
        ? graphData.errors.map((e) => e?.message).filter(Boolean)
        : [];
      const scopeDenied = messages.some((m) => /access denied for products/i.test(m));

      return send(res, graphResponse.ok ? 403 : graphResponse.status || 502, {
        error: scopeDenied ? 'Product access has not been granted to Ashes AI yet.' : 'Shopify GraphQL query failed.',
        detail: messages.length ? messages.join(' ') : graphData.errors || graphData,
        granted_scopes: tokenData.scope || null,
        action: scopeDenied
          ? 'Open Ashes AI from Shopify Admin and approve the updated read_products/write_products permissions, or reinstall/update the app grant.'
          : null,
      });
    }

    const products = graphData.data?.products?.nodes || [];
    return send(res, 200, {
      connected: true,
      shop: SHOP,
      store_name: graphData.data?.shop?.name || null,
      token_expires_in: tokenData.expires_in || null,
      scopes: tokenData.scope || null,
      products,
    });
  } catch (error) {
    return send(res, 500, {
      error: 'Shopify connection failed.',
      detail: error?.message || String(error),
    });
  }
}
