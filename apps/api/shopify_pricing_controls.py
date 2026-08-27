from __future__ import annotations

import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import app
from apps.api.shopify_routes import _shop
from apps.api.shopify_pricing_live import (
    _app_handle,
    _embedded_app_url,
    _partner_app_id,
    _partner_org_id,
    _partner_token,
    _shop_gid,
)


def _cancel_managed_subscription() -> dict:
    mutation = """
    mutation AshesCancelSubscription(
      $appId: ID!,
      $shopId: ID!,
      $deferCancellation: Boolean!,
      $prorate: Boolean!,
      $skipFinalUsageCharge: Boolean!
    ) {
      appSubscriptionCancel(
        appId: $appId,
        shopId: $shopId,
        deferCancellation: $deferCancellation,
        prorate: $prorate,
        skipFinalUsageCharge: $skipFinalUsageCharge
      ) {
        appSubscription {
          cancelAtEndOfCycle
          cancelledAt
          billingPeriod
          currentBillingCycle { startTime endTime }
        }
        userErrors { field message }
      }
    }
    """
    url = f"https://partners.shopify.com/{_partner_org_id()}/api/2026-07/graphql.json"
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": _partner_token(),
        },
        json={
            "query": mutation,
            "variables": {
                "appId": _partner_app_id(),
                "shopId": _shop_gid(),
                # Keep access through the already-paid billing cycle.
                "deferCancellation": True,
                "prorate": False,
                "skipFinalUsageCharge": False,
            },
        },
        timeout=20,
    )
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if response.status_code >= 400:
        detail = payload.get("errors") or payload or response.text[:500]
        raise RuntimeError(f"Shopify Partner API cancellation failed ({response.status_code}): {detail}")
    if payload.get("errors"):
        raise RuntimeError(f"Shopify Partner API cancellation error: {payload['errors']}")
    result = ((payload.get("data") or {}).get("appSubscriptionCancel") or {})
    user_errors = result.get("userErrors") or []
    if user_errors:
        raise RuntimeError("; ".join(str(err.get("message") or err) for err in user_errors))
    subscription = result.get("appSubscription") or {}
    if not subscription:
        raise RuntimeError("Shopify did not return the cancelled subscription")
    return subscription


@app.post("/api/shopify/app-pricing/cancel")
def shopify_app_pricing_cancel() -> JSONResponse:
    try:
        subscription = _cancel_managed_subscription()
    except Exception as exc:
        message = str(exc)
        if "permission" in message.lower() or "access" in message.lower() or "forbidden" in message.lower():
            raise HTTPException(
                status_code=403,
                detail="Cancellation requires the Partner API client to have View financials permission.",
            ) from exc
        raise HTTPException(status_code=502, detail=message[:700]) from exc

    shop = _shop().strip().lower()
    cycle = subscription.get("currentBillingCycle") or {}
    collection("shopify_accounts").update_one(
        {"shop": shop},
        {
            "$set": {
                "shopify_cancel_at_end_of_cycle": bool(subscription.get("cancelAtEndOfCycle")),
                "shopify_cancelled_at": subscription.get("cancelledAt"),
                "shopify_billing_cycle_end": cycle.get("endTime"),
                "billing_cancel_requested_at": now_iso(),
                "updated_at": now_iso(),
            }
        },
        upsert=False,
    )
    print(
        "ASHES_SHOPIFY_APP_PRICING_CANCEL "
        f"shop={shop} defer={bool(subscription.get('cancelAtEndOfCycle'))}"
    )
    return JSONResponse(
        {
            "ok": True,
            "cancel_at_end_of_cycle": bool(subscription.get("cancelAtEndOfCycle")),
            "cycle_end": cycle.get("endTime"),
        },
        headers={"Cache-Control": "no-store"},
    )


_INJECT = r'''
<!-- ASHES_SHOPIFY_PRICING_CONTROLS_V1 -->
<style>
.ashes-cancel-subscription{display:block;margin-top:10px;width:100%;text-align:center;border:1px solid #444;border-radius:11px;padding:9px 12px;font-weight:700;background:transparent;color:#aaa;cursor:pointer}
.ashes-cancel-subscription:hover{color:#fff;border-color:#777}.ashes-cancel-subscription:disabled{opacity:.55;cursor:wait}
</style>
<script>
(function(){
  // Final safety net: the Shopify App Pricing welcome URL can occasionally be
  // opened as a top-level app URL. Never leave merchants stranded outside Admin.
  if (window.top === window.self) {
    fetch('/api/shopify/billing-url', {cache:'no-store'})
      .then(r => r.json())
      .then(d => {
        if (!d || !d.shop || !d.app_handle) return;
        const store = String(d.shop).replace(/\.myshopify\.com$/i, '');
        const target = 'https://admin.shopify.com/store/' + encodeURIComponent(store) + '/apps/' + encodeURIComponent(d.app_handle);
        if (window.location.href !== target) window.location.replace(target);
      })
      .catch(() => {});
  }

  function getPlanData(){
    try { return (typeof planData !== 'undefined' && planData) ? planData : null; }
    catch (_) { return null; }
  }

  function decorateCancel(){
    const data = getPlanData();
    const root = document.getElementById('plans');
    if (!data || !root || !Array.isArray(data.plans)) return;
    const current = (data.current_plan || {}).key;
    if (!current || current === 'trial' || current === 'enterprise') return;
    const cards = Array.from(root.children || []);
    const idx = data.plans.findIndex(p => p && p.key === current);
    const card = idx >= 0 ? cards[idx] : null;
    if (!card || card.querySelector('.ashes-cancel-subscription')) return;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ashes-cancel-subscription';
    btn.textContent = 'Cancel subscription';
    btn.addEventListener('click', async function(){
      if (!window.confirm('Cancel this subscription at the end of the current billing cycle? You will keep access until then.')) return;
      const original = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Scheduling cancellation…';
      try {
        const r = await fetch('/api/shopify/app-pricing/cancel', {
          method:'POST', headers:{'Accept':'application/json'}, cache:'no-store'
        });
        let d = {};
        try { d = await r.json(); } catch (_) {}
        if (!r.ok) throw new Error((d && d.detail) || 'Could not cancel subscription');
        btn.textContent = 'Cancellation scheduled';
        alert('Your Ashes subscription will cancel at the end of the current billing cycle.');
      } catch (e) {
        btn.disabled = false;
        btn.textContent = original;
        alert(e && e.message ? e.message : 'Could not cancel subscription');
      }
    });
    card.appendChild(btn);
  }

  const timer = setInterval(decorateCancel, 500);
  decorateCancel();
  window.addEventListener('beforeunload', () => clearInterval(timer), {once:true});
})();
</script>
'''


class ShopifyPricingControlsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path != "/api/shopify/app" or response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode("utf-8", errors="replace")
        if "ASHES_SHOPIFY_PRICING_CONTROLS_V1" not in text:
            text = text.replace("</body>", _INJECT + "</body>")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return Response(content=text, status_code=response.status_code, headers=headers, media_type="text/html")


app.add_middleware(ShopifyPricingControlsMiddleware)
