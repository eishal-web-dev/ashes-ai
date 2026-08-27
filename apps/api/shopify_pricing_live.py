from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import app
from apps.api.shopify_routes import _access_token, _graphql, _shop
import apps.api.shopify_generation as generation


LIVE_SHOPIFY_PLANS: list[dict[str, Any]] = [
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
        "price": "$7.99/mo",
        "generation_allowance": 5,
        "generation_period": "month",
        "active_product_guideline": 15,
        "features": ["5 new twins / month", "~15 active 3D products", "3D + AR", "Reusable assets"],
    },
    {
        "key": "growth",
        "name": "Growth",
        "price": "$17.99/mo",
        "generation_allowance": 20,
        "generation_period": "month",
        "active_product_guideline": 50,
        "features": ["20 new twins / month", "~50 active 3D products", "3D + AR", "Cross-channel reuse"],
    },
    {
        "key": "pro",
        "name": "Pro",
        "price": "$39.99/mo",
        "generation_allowance": 75,
        "generation_period": "month",
        "active_product_guideline": 250,
        "features": ["75 new twins / month", "~250 active 3D products", "Priority generation", "3D + AR"],
    },
    {
        "key": "business",
        "name": "Business",
        "price": "$79.99/mo",
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

# One catalog for UI and generation enforcement.
generation.SHOPIFY_PLANS[:] = LIVE_SHOPIFY_PLANS


def _plan(key: str) -> dict[str, Any]:
    plan = next((p for p in LIVE_SHOPIFY_PLANS if p["key"] == key), None)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown Ashes Shopify App Pricing plan")
    return plan


def _store_handle(shop: str | None = None) -> str:
    domain = (shop or _shop()).strip().lower()
    return domain.split(".myshopify.com", 1)[0]


def _app_handle() -> str:
    return (os.getenv("ASHES_SHOPIFY_APP_HANDLE") or "ashes-ai").strip().strip("/")


def _pricing_url(shop: str | None = None) -> str:
    return f"https://admin.shopify.com/store/{_store_handle(shop)}/charges/{_app_handle()}/pricing_plans"


def _partner_org_id() -> str:
    return (os.getenv("ASHES_SHOPIFY_PARTNER_ORG_ID") or "5119562").strip()


def _partner_app_id() -> str:
    raw = (os.getenv("ASHES_SHOPIFY_PARTNER_APP_ID") or "411944124417").strip()
    return raw if raw.startswith("gid://") else f"gid://shopify/App/{raw}"


def _partner_token() -> str:
    token = (os.getenv("ASHES_SHOPIFY_PARTNER_ACCESS_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("ASHES_SHOPIFY_PARTNER_ACCESS_TOKEN is not configured")
    return token


def _shop_gid() -> str:
    token, _ = _access_token()
    result = _graphql(token, "query AshesShopId { shop { id } }")
    shop = ((result.get("data") or {}).get("shop") or {})
    shop_id = str(shop.get("id") or "").strip()
    if not shop_id:
        raise RuntimeError("Shopify Admin API did not return the shop ID")
    return shop_id


def _active_app_pricing_subscription() -> dict[str, Any] | None:
    query = """
    query AshesActiveSubscription($appId: ID!, $shopId: ID!) {
      activeSubscription(appId: $appId, shopId: $shopId) {
        shop { id myshopifyDomain }
        billingPeriod
        cancelAtEndOfCycle
        trialEndsAt
        currentBillingCycle { startTime endTime }
        items {
          handle
          description
          price {
            __typename
            active
            currency
            ... on FlatRatePrice { amount }
          }
        }
        legacySubscriptionId
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
            "query": query,
            "variables": {"appId": _partner_app_id(), "shopId": _shop_gid()},
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Shopify Partner API error: {payload['errors']}")
    return (payload.get("data") or {}).get("activeSubscription")


def _verified_plan_handle(subscription: dict[str, Any] | None, requested: str) -> str | None:
    if not subscription:
        return None
    valid = {p["key"] for p in LIVE_SHOPIFY_PLANS if p["key"] not in {"trial", "enterprise"}}
    requested = requested.strip().lower()
    if requested not in valid:
        return None

    # Shopify App Pricing identifies the chosen plan through plan_handle on redirect.
    # The Active Subscription API is the source of truth; for fixed-price plans, the
    # recurring subscription item handle is used to confirm the same configured handle.
    handles = {str(item.get("handle") or "").strip().lower() for item in subscription.get("items") or []}
    if requested in handles:
        return requested

    # Defensive fallback: verify by the exact fixed monthly amount configured in Ashes.
    expected = _plan(requested)
    expected_amount = float(str(expected["price"]).replace("$", "").replace("/mo", ""))
    for item in subscription.get("items") or []:
        price = item.get("price") or {}
        if not price.get("active", True):
            continue
        try:
            amount = float(price.get("amount"))
        except (TypeError, ValueError):
            continue
        if abs(amount - expected_amount) < 0.001:
            return requested
    return None


def _sync_managed_plan(plan_handle: str, shop_param: str | None = None) -> str:
    requested = plan_handle.strip().lower()
    _plan(requested)
    expected_shop = _shop().strip().lower()
    if shop_param and shop_param.strip().lower() != expected_shop:
        raise HTTPException(status_code=400, detail="Shop mismatch in Shopify App Pricing redirect")

    subscription = _active_app_pricing_subscription()
    verified = _verified_plan_handle(subscription, requested)
    if verified != requested:
        raise HTTPException(status_code=402, detail="Shopify App Pricing subscription could not be verified")

    cycle = (subscription or {}).get("currentBillingCycle") or {}
    collection("shopify_accounts").update_one(
        {"shop": expected_shop},
        {
            "$set": {
                "shop": expected_shop,
                "plan_key": requested,
                "billing_provider": "shopify_app_pricing",
                "shopify_plan_handle": requested,
                "shopify_billing_period": (subscription or {}).get("billingPeriod"),
                "shopify_billing_cycle_start": cycle.get("startTime"),
                "shopify_billing_cycle_end": cycle.get("endTime"),
                "shopify_cancel_at_end_of_cycle": bool((subscription or {}).get("cancelAtEndOfCycle")),
                "shopify_legacy_subscription_id": (subscription or {}).get("legacySubscriptionId"),
                "billing_activated_at": now_iso(),
                "updated_at": now_iso(),
            },
            "$setOnInsert": {"created_at": now_iso(), "connected": True},
        },
        upsert=True,
    )
    print(f"ASHES_SHOPIFY_APP_PRICING_SYNC shop={expected_shop} plan={requested}")
    return requested


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


@app.get("/api/shopify/app-pricing/sync")
def shopify_app_pricing_sync(plan_handle: str, shop: str | None = None) -> JSONResponse:
    verified = _sync_managed_plan(plan_handle, shop)
    return JSONResponse({"ok": True, "plan": verified, "provider": "shopify_app_pricing"}, headers={"Cache-Control": "no-store"})


_INJECT = r'''
<!-- ASHES_SHOPIFY_APP_PRICING_V2 -->
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
    if (!r.ok || !d.url) throw new Error((d && d.detail) || 'Shopify App Pricing is not configured');
    billingUrl = d.url;
    return billingUrl;
  }
  function leaveIframe(url){
    try { window.top.location.href = url; return; } catch (_) {}
    try { window.open(url, '_top'); return; } catch (_) {}
    window.location.href = url;
  }
  async function choosePlan(){
    try { leaveIframe(await getBillingUrl()); }
    catch (e) { alert(e && e.message ? e.message : 'Could not open Shopify App Pricing'); }
  }
  function getPlanData(){
    try { return (typeof planData !== 'undefined' && planData) ? planData : null; }
    catch (_) { return null; }
  }
  function decorate(){
    const data = getPlanData();
    const root = document.getElementById('plans');
    if (!data || !root || !Array.isArray(data.plans)) return;
    const cards = Array.from(root.children || []);
    const current = (data.current_plan || {}).key;
    cards.forEach((card, i) => {
      const plan = data.plans[i];
      if (!plan || card.querySelector('.ashes-plan-action')) return;
      card.querySelectorAll('.ashes-checkout-btn').forEach(el => el.remove());
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
      a.addEventListener('click', function(ev){ ev.preventDefault(); choosePlan(); });
      card.appendChild(a);
    });
  }
  setInterval(decorate, 400);
  decorate();
})();
</script>
'''


class ShopifyPricingLiveMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Shopify App Pricing appends plan_handle (and shop for external URLs)
        # after a merchant confirms a plan. Verify before rendering paid access.
        if request.url.path == "/api/shopify/app":
            plan_handle = request.query_params.get("plan_handle")
            shop_param = request.query_params.get("shop")
            if plan_handle:
                try:
                    _sync_managed_plan(plan_handle, shop_param)
                except Exception as exc:
                    print(f"ASHES_SHOPIFY_APP_PRICING_SYNC_FAILED plan={plan_handle} error={exc}")

        response = await call_next(request)
        if request.url.path != "/api/shopify/app" or response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode("utf-8", errors="replace")
        if "ASHES_SHOPIFY_APP_PRICING_V2" not in text:
            text = text.replace("</body>", _INJECT + "</body>")

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return Response(content=text, status_code=response.status_code, headers=headers, media_type="text/html")


app.add_middleware(ShopifyPricingLiveMiddleware)
