from __future__ import annotations

import html
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_main import app


_INJECT = r'''
<div id="ashesBuildMarker" style="position:fixed;right:12px;bottom:12px;z-index:10000;background:#111;border:1px solid #333;color:#8f8f8f;border-radius:999px;padding:6px 9px;font:11px system-ui">Ashes Shopify build 2026.08.26-session-auth</div>
<script>
(function(){
  const grid = document.getElementById('products');
  if (!grid || grid.dataset.ashesPublishFix === '1') return;
  grid.dataset.ashesPublishFix = '1';

  grid.addEventListener('click', async function(event){
    const button = event.target.closest('[data-publish]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();

    const index = Number(button.dataset.publish);
    const product = Array.isArray(productsCache) ? productsCache[index] : null;
    const state = document.getElementById('state-' + index);
    if (!product || !product.id) {
      if (state) { state.className = 'state err'; state.textContent = 'Ashes could not identify this Shopify product.'; }
      return;
    }

    button.disabled = true;
    button.textContent = 'Publishing…';
    if (state) { state.className = 'state warn'; state.textContent = 'Uploading existing GLB to Shopify…'; }

    try {
      const response = await fetch('/api/shopify/publish-3d', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({product_id: product.id, product_name: product.title})
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = data && data.detail;
        const message = typeof detail === 'string' ? detail : JSON.stringify(detail || data || {});
        throw new Error(message || 'Shopify publish failed');
      }
      if (state) { state.className = 'state ok'; state.textContent = 'Published to Shopify · ' + (data.status || 'PROCESSING'); }
      button.textContent = 'Published ✓';
      if (typeof loadProducts === 'function') await loadProducts();
    } catch (error) {
      button.disabled = false;
      button.textContent = 'Publish to Shopify';
      if (state) { state.className = 'state err'; state.textContent = error && error.message ? error.message : 'Shopify publish failed'; }
    }
  }, true);
})();
</script>
'''

_SESSION_FETCH = r'''
<script>
(function () {
  const originalFetch = window.fetch.bind(window);
  const protectedPaths = [
    '/api/shopify/products',
    '/api/shopify/plans',
    '/api/shopify/generate-3d',
    '/api/shopify/publish-3d',
    '/api/shopify/assets'
  ];

  window.fetch = async function(input, init) {
    init = init ? Object.assign({}, init) : {};
    const raw = typeof input === 'string' ? input : (input && input.url ? input.url : '');
    let url;
    try { url = new URL(raw, window.location.origin); } catch (_) { return originalFetch(input, init); }
    const needsToken = url.origin === window.location.origin && protectedPaths.some(path => url.pathname.startsWith(path));
    if (needsToken) {
      if (!window.shopify || typeof window.shopify.idToken !== 'function') {
        throw new Error('Shopify App Bridge session is unavailable. Reopen Ashes AI from Shopify Admin.');
      }
      const token = await window.shopify.idToken();
      const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined) || {});
      headers.set('Authorization', 'Bearer ' + token);
      init.headers = headers;
    }
    return originalFetch(input, init);
  };
})();
</script>
'''


class ShopifyPublishClickFixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path != '/api/shopify/app' or response.status_code != 200:
            return response

        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type:
            return response

        body = b''
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode('utf-8', errors='replace')

        client_id = (os.getenv('SHOPIFY_CLIENT_ID') or os.getenv('ASHES_SHOPIFY_CLIENT_ID') or '').strip()
        app_bridge_head = (
            '<meta name="shopify-api-key" content="' + html.escape(client_id, quote=True) + '">'
            '<script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>'
            + _SESSION_FETCH
        )
        if 'cdn.shopify.com/shopifycloud/app-bridge.js' not in text:
            text = text.replace('<head>', '<head>' + app_bridge_head, 1)
        if 'ashesBuildMarker' not in text:
            text = text.replace('</body>', _INJECT + '</body>')

        headers = dict(response.headers)
        headers.pop('content-length', None)
        headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        headers['Pragma'] = 'no-cache'
        headers['Expires'] = '0'
        return Response(
            content=text,
            status_code=response.status_code,
            headers=headers,
            media_type='text/html',
        )


app.add_middleware(ShopifyPublishClickFixMiddleware)
