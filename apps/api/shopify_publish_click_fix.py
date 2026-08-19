from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_main import app


_INJECT = r'''
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
        if 'ashesPublishFix' not in text:
            text = text.replace('</body>', _INJECT + '</body>')

        headers = dict(response.headers)
        headers.pop('content-length', None)
        return Response(
            content=text,
            status_code=response.status_code,
            headers=headers,
            media_type='text/html',
        )


app.add_middleware(ShopifyPublishClickFixMiddleware)
