from __future__ import annotations

import os
import time
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import app
from apps.api.shopify_routes import _access_token, _graphql, _shop
import apps.api.shopify_generation as generation


# Launch pricing: intentionally below the entry monthly price of the closest
# AI-3D / Shopify competitors while we measure real GPU cost in production.
ASHES_SHOPIFY_PLANS: list[dict[str, Any]] = [
    {
        "key": "trial",
        "name": "Free Trial",
        "price": "$0",
        "amount": 0.0,
        "generation_allowance": 2,
        "generation_period": "total",
        "active_product_guideline": 3,
        "features": ["2 total 3D generations", "3D + AR", "Reusable GLB assets", "Shopify integration"],
    },
    {
        "key": "starter",
        "name": "Starter",
        "price": "$7.99/mo",
        "amount": 7.99,
        "generation_allowance": 5,
        "generation_period": "month",
        "active_product_guideline": 15,
        "features": ["5 new twins / month", "~15 active 3D products", "3D + AR", "Reusable assets"],
    },
    {
        "key": "growth",
        "name": "Growth",
        "price": "$17.99/mo",
        "amount": 17.99,
        "generation_allowance": 20,
        "generation_period": "month",
        "active_product_guideline": 50,
        "features": ["20 new twins / month", "~50 active 3D products", "3D + AR", "Cross-channel reuse"],
    },
    {
        "key": "pro",
        "name": "Pro",
        "price": "$39.99/mo",
        "amount": 39.99,
        "generation_allowance": 75,
        "generation_period": "month",
        "active_product_guideline": 250,
        "features": ["75 new twins / month", "~250 active 3D products", "Priority generation", "3D + AR"],
    },
    {
        "key": "business",
        "name": "Business",
        "price": "$79.99/mo",
        "amount": 79.99,
        "generation_allowance": 200,
        "generation_period": "month",
        "active_product_guideline": 700,
        "features": ["200 new twins / month", "Large catalogs", "Priority generation", "3D + AR"],
    },
    {
        "key": "enterprise",
        "name": "Enterprise",
        "price": "Custom",
        "amount": None,
        "generation_allowance": None,
        "generation_period": "custom",
        "active_product_guideline": "Custom",
        "features": ["Custom catalog allowance", "API access", "Bulk workflows", "SLA / dedicated capacity"],
    },
]

# Last imported pricing module wins. Keep generation limits and the UI on one source.
generation.SHOPIFY_PLANS[:] = ASHES_SHOPIFY_PLANS


def _plan(key: str) -> dict[str, Any]:
    plan = next((p for p in ASHES_SHOPIFY_PLANS if p["key"] == key), None)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown Ashes plan")
    return plan


def _billing_test_mode() -> bool:
    return os.getenv("ASHES_SHOPIFY_BILLING_TEST", "true").strip().lower() in {"1", "true", "yes", "on"}


def _return_base(request: Request) -> str:
    configured = (os.getenv("ASHES_API_BASE_URL") or "").strip().rstrip("/")
    if configured.startswith("https://"):
        return configured
    return str(request.base_url).rstrip("/")


@app.post("/api/shopify/billing/subscribe/{plan_key}")
def shopify_subscribe(plan_key: str, request: Request) -> dict[str, Any]:
    plan = _plan(plan_key)
    amount = plan.get("amount")
    if amount is None:
        return {
            "ok": True,
            "enterprise": True,
            "url": "mailto:ashes.ai.26@gmail.com?subject=Ashes%20AI%20Enterprise",
        }
    if float(amount) <= 0:
        raise HTTPException(status_code=400, detail="The free trial does not require checkout")

    token, _ = _access_token()
    return_url = f"{_return_base(request)}/api/shopify/billing/return?plan={plan_key}"
    mutation = """
    mutation AshesCreateSubscription(
      $name: String!,
      $returnUrl: URL!,
      $lineItems: [AppSubscriptionLineItemInput!]!,
      $test: Boolean
    ) {
      appSubscriptionCreate(
        name: $name,
        returnUrl: $returnUrl,
        lineItems: $lineItems,
        test: $test
      ) {
        appSubscription { id }
        confirmationUrl
        userErrors { field message }
      }
    }
    """
    result = _graphql(
        token,
        mutation,
        {
            "name": f"Ashes AI — {plan['name']}",
            "returnUrl": return_url,
            "test": _billing_test_mode(),
            "lineItems": [
                {
                    "plan": {
                        "appRecurringPricingDetails": {
                            "price": {"amount": float(amount), "currencyCode": "USD"},
                            "interval": "EVERY_30_DAYS",
                        }
                    }
                }
            ],
        },
    )
    payload = ((result.get("data") or {}).get("appSubscriptionCreate") or {})
    errors = payload.get("userErrors") or []
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    confirmation_url = str(payload.get("confirmationUrl") or "").strip()
    subscription_id = ((payload.get("appSubscription") or {}).get("id"))
    if not confirmation_url:
        raise HTTPException(status_code=502, detail="Shopify did not return a billing approval URL")

    collection("shopify_billing_intents").update_one(
        {"shop": _shop().lower(), "subscription_id": subscription_id},
        {
            "$set": {
                "shop": _shop().lower(),
                "subscription_id": subscription_id,
                "plan_key": plan_key,
                "amount": float(amount),
                "status": "PENDING_APPROVAL",
                "test": _billing_test_mode(),
                "updated_at": now_iso(),
            },
            "$setOnInsert": {"created_at": now_iso()},
        },
        upsert=True,
    )
    return {"ok": True, "plan": plan_key, "confirmation_url": confirmation_url}


def _active_subscription_for_intent(token: str, subscription_id: str, expected_name: str) -> dict[str, Any] | None:
    """Verify the exact subscription Ashes created instead of trusting callback query params."""
    query = """
    query AshesSubscriptionById($id: ID!) {
      node(id: $id) {
        ... on AppSubscription {
          id
          name
          status
          test
        }
      }
      currentAppInstallation {
        activeSubscriptions { id name status test }
      }
    }
    """
    result = _graphql(token, query, {"id": subscription_id})
    data = result.get("data") or {}
    node = data.get("node") or {}
    if (
        str(node.get("id") or "") == subscription_id
        and node.get("name") == expected_name
        and str(node.get("status") or "").upper() == "ACTIVE"
    ):
        return node

    subscriptions = ((data.get("currentAppInstallation") or {}).get("activeSubscriptions")) or []
    return next(
        (
            s
            for s in subscriptions
            if str(s.get("id") or "") == subscription_id
            and s.get("name") == expected_name
            and str(s.get("status") or "").upper() == "ACTIVE"
        ),
        None,
    )


@app.get("/api/shopify/billing/return")
def shopify_billing_return(plan: str, request: Request, charge_id: str | None = None):
    selected = _plan(plan)
    if selected.get("amount") is None:
        return RedirectResponse("/api/shopify/app", status_code=302)

    shop = _shop().lower()
    intent = collection("shopify_billing_intents").find_one(
        {"shop": shop, "plan_key": plan, "status": "PENDING_APPROVAL"},
        sort=[("updated_at", -1)],
    )
    if not intent or not intent.get("subscription_id"):
        return HTMLResponse(
            "<h2>Ashes could not verify this billing approval.</h2>"
            "<p>No matching pending checkout was found. Return to Shopify and choose the plan again.</p>",
            status_code=402,
        )

    subscription_id = str(intent["subscription_id"])
    expected_name = f"Ashes AI — {selected['name']}"
    token, _ = _access_token()

    # Shopify can redirect back a moment before activeSubscriptions has propagated.
    # Verify the exact subscription ID several times before deciding the approval failed.
    match: dict[str, Any] | None = None
    for attempt in range(6):
        try:
            match = _active_subscription_for_intent(token, subscription_id, expected_name)
        except Exception as exc:
            print(
                f"ASHES_SHOPIFY_BILLING_VERIFY attempt={attempt + 1} "
                f"plan={plan} subscription={subscription_id} error={exc}"
            )
        if match:
            break
        if attempt < 5:
            time.sleep(1.0)

    # Development stores sometimes return a legacy-looking charge_id for a GraphQL
    # test subscription before the subscription appears in activeSubscriptions.
    # Permit that fallback ONLY for an Ashes-created pending TEST intent. Production
    # billing never trusts charge_id by itself.
    test_callback_fallback = bool(
        not match
        and charge_id
        and bool(intent.get("test"))
        and _billing_test_mode()
    )
    if test_callback_fallback:
        match = {
            "id": subscription_id,
            "name": expected_name,
            "status": "ACTIVE",
            "test": True,
        }
        print(
            f"ASHES_SHOPIFY_BILLING_TEST_APPROVED plan={plan} "
            f"subscription={subscription_id} charge_id={charge_id}"
        )

    if not match:
        return HTMLResponse(
            "<h2>Ashes billing is still being confirmed by Shopify.</h2>"
            "<p>Return to Shopify and reopen Ashes in a few seconds. You do not need to approve the charge again.</p>",
            status_code=202,
        )

    collection("shopify_accounts").update_one(
        {"shop": shop},
        {
            "$set": {
                "shop": shop,
                "plan_key": plan,
                "shopify_subscription_id": match.get("id"),
                "shopify_subscription_name": match.get("name"),
                "shopify_subscription_test": bool(match.get("test")),
                "shopify_charge_id": charge_id,
                "billing_activated_at": now_iso(),
                "updated_at": now_iso(),
            },
            "$setOnInsert": {"created_at": now_iso(), "connected": True},
        },
        upsert=True,
    )
    collection("shopify_billing_intents").update_one(
        {"_id": intent["_id"]},
        {
            "$set": {
                "status": "ACTIVE",
                "shopify_charge_id": charge_id,
                "activated_at": now_iso(),
                "updated_at": now_iso(),
            }
        },
    )

    print(
        f"ASHES_SHOPIFY_BILLING_ACTIVATED shop={shop} plan={plan} "
        f"subscription={match.get('id')} test={bool(match.get('test'))}"
    )

    # Return into the embedded app through Shopify admin instead of leaving the merchant on Railway.
    store_handle = _shop().split(".myshopify.com", 1)[0]
    app_handle = (os.getenv("ASHES_SHOPIFY_APP_HANDLE") or "ashes-ai").strip().strip("/")
    return RedirectResponse(f"https://admin.shopify.com/store/{store_handle}/apps/{app_handle}", status_code=302)


_INJECT = r'''
<!-- ASHES_NATIVE_BILLING_V1 -->
<script>
(function(){
  async function openAshesCheckout(plan){
    const r = await fetch('/api/shopify/billing/subscribe/' + encodeURIComponent(plan.key), {
      method: 'POST',
      headers: {'Accept':'application/json'}
    });
    const d = await r.json();
    if(!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail || d));
    const url = d.confirmation_url || d.url;
    if(!url) throw new Error('Shopify did not return a checkout URL');
    window.top.location.href = url;
  }

  document.addEventListener('click', function(ev){
    const button = ev.target && ev.target.closest ? ev.target.closest('.ashes-plan-action') : null;
    if(!button || !window.planData) return;
    ev.preventDefault();
    ev.stopImmediatePropagation();
    const label = (button.textContent || '').replace(/^Choose\s+/i,'').trim();
    const plans = window.planData.plans || [];
    const plan = plans.find(p => p.name === label) || (label.includes('Shopify') ? plans.find(p => p.key === 'enterprise') : null);
    if(!plan) { alert('Could not identify this Ashes plan.'); return; }
    button.style.pointerEvents='none';
    button.textContent = plan.key === 'enterprise' ? 'Opening…' : 'Opening Shopify checkout…';
    openAshesCheckout(plan).catch(err => {
      button.style.pointerEvents='';
      button.textContent = plan.key === 'enterprise' ? 'Contact Ashes' : 'Choose ' + plan.name;
      alert(err && err.message ? err.message : 'Could not open Shopify checkout');
    });
  }, true);
})();
</script>
'''


class ShopifyNativeBillingMiddleware(BaseHTTPMiddleware):
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
        if "ASHES_NATIVE_BILLING_V1" not in text:
            text = text.replace("</body>", _INJECT + "</body>")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return Response(content=text, status_code=response.status_code, headers=headers, media_type="text/html")


app.add_middleware(ShopifyNativeBillingMiddleware)
