from __future__ import annotations

import os

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_main import app
import apps.api.shopify_generation as generation


LIVE_SHOPIFY_PLANS = [
    {
        "key": "trial",
        "name": "Free Trial",
        "price": "$0",
        "generation_allowance": 2,
        "generation_period": "total",
        "active_product_guideline": 3,
        "features": ["2 total 3D generations", "3D + AR", "Reusable GLB assets", "Shopify integration"],
    },
    {
        "key": "starter",
        "name": "Starter",
        "price": "$9.99/mo",
        "generation_allowance": 5,
        "generation_period": "month",
        "active_product_guideline": 15,
        "features": ["5 new twins / month", "~15 active 3D products", "3D + AR", "Reusable assets"],
    },
    {
        "key": "growth",
        "name": "Growth",
        "price": "$24.99/mo",
        "generation_allowance": 20,
        "generation_period": "month",
        "active_product_guideline": 50,
        "features": ["20 new twins / month", "~50 active 3D products", "3D + AR", "Cross-channel reuse"],
    },
    {
        "key": "pro",
        "name": "Pro",
        "price": "$59.99/mo",
        "generation_allowance": 75,
        "generation_period": "month",
        "active_product_guideline": 250,
        "features": ["75 new twins / month", "~250 active 3D products", "Priority generation", "3D + AR"],
    },
    {
        "key": "business",
        "name": "Business",
        "price": "$119/mo",
        "generation_allowance": 200,
        "generation_period": "month",
        "active_product_guideline": 700,
        "features": ["200 new twins / month", "Large catalogs", "Priority generation", "3D + AR"],
    },
    {
        "key": "enterprise",
        "name": "Enterprise",
        "price": "Custom",
        "generation_allowance": None,
        "generation_period": "custom",
        "active_product_guideline": "Custom",
        "features": ["Custom catalog allowance", "API access", "Bulk workflows", "SLA / dedicated capacity"],
    },
]

# Replace the original launch catalog without touching generation/reuse logic.
generation.SHOPIFY_PLANS[:] = LIVE_SHOPIFY_PLANS


def _shop() -> str:
    return (os.getenv("SHOPIFY_SHOP") or "ashes-stack.myshopify.com").strip().lower()


def _store_handle() -> str:
    return _shop().split(".myshopify.com", 1)[0]


def _app_handle() -> str:
    return (os.getenv("ASHES_SHOPIFY_APP_HANDLE") or "ashes-ai").strip().strip("/")


def _pricing_url() -> str:
    return f"https://admin.shopify.com/store/{_store_handle()}/charges/{_app_handle()}/pricing_plans"


@app.get("/api/shopify/billing-url")
def shopify_billing_url() -> JSONResponse:
    return JSONResponse(
        {
            "provider": "shopify_app_pricing",
            "shop": _shop(),
            "app_handle": _app_handle(),
            "url": _pricing_url(),
            "plans": LIVE_SHOPIFY_PLANS,
        },
        headers={"Cache-Control": "no-store"},
    )


_INJECT = r'''
<style>
.ashes-plan-action{display:block;margin-top:14px;width:100%;text-align:center;text-decoration:none;border-radius:11px;padding:10px 12px;font-weight:800;background:#f3f3f3;color:#090909}
.ashes-plan-action:hover{opacity:.9}.ashes-plan-note{margin-top:8px;color:#747474;font-size:11px;line-height:1.4}
</style>
<script>
(function(){
  let billingUrl = null;
  async function getBillingUrl(){
    if (billingUrl) return billingUrl;
    const r = await fetch('/api/shopify/billing-url', {cache:'no-store'});
    const d = await r.json();
    if (!r.ok || !d.url) throw new Error((d && d.detail) || 'Shopify billing is not configured');
    billingUrl = d.url;
    return billingUrl;
  }
  async function choosePlan(plan){
    try {
      const url = await getBillingUrl();
      // Shopify hosts the pricing/approval screen. Top navigation avoids iframe blocking.
      window.top.location.href = url;
    } catch (e) {
      alert(e && e.message ? e.message : 'Could not open Shopify pricing');
    }
  }
  function decorate(){
    if (!window.planData || !document.getElementById('plans')) return;
    const cards = Array.from(document.getElementById('plans').children || []);
    const current = (window.planData.current_plan || {}).key;
    const plans = window.planData.plans || [];
    cards.forEach((card, i) => {
      const plan = plans[i];
      if (!plan || card.querySelector('.ashes-plan-action')) return;
      if (plan.key === current) {
        const note = document.createElement('div');
        note.className = 'ashes-plan-note';
        note.textContent = 'Your current Ashes plan';
        card.appendChild(note);
        return;
      }
      if (plan.key === 'trial') return;
      const a = document.createElement('a');
      a.href = '#';
      a.className = 'ashes-plan-action';
      a.textContent = plan.key === 'enterprise' ? 'View Shopify plans' : 'Choose ' + plan.name;
      a.addEventListener('click', function(ev){ ev.preventDefault(); choosePlan(plan); });
      card.appendChild(a);
    });
  }
  setInterval(decorate, 500);
  decorate();
})();
</script>
'''


class ShopifyPricingLiveMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path != "/api/shopify/app" or response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode("utf-8", errors="replace")
        if "ashes-plan-action" not in text:
            text = text.replace("</body>", _INJECT + "</body>")

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return Response(content=text, status_code=response.status_code, headers=headers, media_type="text/html")


app.add_middleware(ShopifyPricingLiveMiddleware)
