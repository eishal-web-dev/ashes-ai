from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_main import app


_INJECT = r'''
<!-- ASHES_BILLING_CLICK_FIX_V2 -->
<style>
.ashes-checkout-btn{display:block;margin-top:14px;width:100%;text-align:center;border:0;border-radius:11px;padding:11px 12px;font-weight:800;background:#f3f3f3;color:#090909;cursor:pointer}
.ashes-checkout-btn:hover{opacity:.9}.ashes-checkout-btn:disabled{opacity:.55;cursor:wait}
</style>
<script>
(function(){
  const ORDER = ['trial','starter','growth','pro','business','enterprise'];

  function getPlanData(){
    try { return (typeof planData !== 'undefined' && planData) ? planData : null; }
    catch (_) { return null; }
  }

  function decorateBillingCards(){
    const root = document.getElementById('plans');
    const data = getPlanData();
    if(!root || !data || !Array.isArray(data.plans)) return;
    const current = (data.current_plan || {}).key;
    const cards = Array.from(root.children || []);

    cards.forEach((card, index) => {
      const plan = data.plans[index] || data.plans.find(p => p.key === ORDER[index]);
      if(!plan || card.querySelector('.ashes-checkout-btn')) return;
      // Remove the older non-working injected action if present.
      card.querySelectorAll('.ashes-plan-action').forEach(el => el.remove());
      if(plan.key === current || plan.key === 'trial') return;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ashes-checkout-btn';
      btn.dataset.planKey = plan.key;
      btn.dataset.planName = plan.name;
      btn.textContent = plan.key === 'enterprise' ? 'Contact Ashes' : 'Choose ' + plan.name;
      card.appendChild(btn);
    });
  }

  async function startCheckout(button){
    const key = button.dataset.planKey;
    const name = button.dataset.planName || key;
    if(!key) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = key === 'enterprise' ? 'Opening…' : 'Opening Shopify checkout…';
    try {
      const response = await fetch('/api/shopify/billing/subscribe/' + encodeURIComponent(key), {
        method:'POST',
        headers:{'Accept':'application/json'},
        cache:'no-store'
      });
      let data = {};
      try { data = await response.json(); } catch (_) {}
      if(!response.ok){
        const detail = data && data.detail;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail || data || ('HTTP ' + response.status)));
      }
      const url = data.confirmation_url || data.url;
      if(!url) throw new Error('Shopify did not return a checkout URL for ' + name);
      // Embedded apps must escape the iframe for Shopify's billing approval screen.
      if(window.top) window.top.location.assign(url);
      else window.location.assign(url);
    } catch (error) {
      button.disabled = false;
      button.textContent = original;
      alert(error && error.message ? error.message : 'Could not open Shopify checkout');
    }
  }

  document.addEventListener('click', function(event){
    const button = event.target && event.target.closest ? event.target.closest('.ashes-checkout-btn') : null;
    if(!button) return;
    event.preventDefault();
    event.stopPropagation();
    startCheckout(button);
  }, true);

  const timer = setInterval(decorateBillingCards, 250);
  decorateBillingCards();
  window.addEventListener('beforeunload', () => clearInterval(timer), {once:true});
})();
</script>
'''


class ShopifyBillingClickFixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path != '/api/shopify/app' or response.status_code != 200:
            return response
        if 'text/html' not in response.headers.get('content-type', ''):
            return response
        body = b''
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode('utf-8', errors='replace')
        if 'ASHES_BILLING_CLICK_FIX_V2' not in text:
            text = text.replace('</body>', _INJECT + '</body>')
        headers = dict(response.headers)
        headers.pop('content-length', None)
        headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return Response(content=text, status_code=response.status_code, headers=headers, media_type='text/html')


app.add_middleware(ShopifyBillingClickFixMiddleware)
