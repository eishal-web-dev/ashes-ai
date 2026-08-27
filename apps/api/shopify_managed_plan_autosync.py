from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.mongo_main import app
from apps.api.shopify_pricing_live import (
    LIVE_SHOPIFY_PLANS,
    _active_app_pricing_subscription,
    _sync_managed_plan,
)


_VALID_PAID_HANDLES = {
    str(plan["key"]).strip().lower()
    for plan in LIVE_SHOPIFY_PLANS
    if plan.get("key") not in {"trial", "enterprise"}
}


def _active_handle(subscription: dict | None) -> str | None:
    """Return the configured Shopify App Pricing handle from the active subscription."""
    if not subscription:
        return None

    for item in subscription.get("items") or []:
        handle = str(item.get("handle") or "").strip().lower()
        if handle in _VALID_PAID_HANDLES:
            return handle

    # Defensive fallback in case Shopify omits the item handle temporarily.
    amount_to_handle = {
        7.99: "starter",
        17.99: "growth",
        39.99: "pro",
        79.99: "business",
    }
    for item in subscription.get("items") or []:
        price = item.get("price") or {}
        if not price.get("active", True):
            continue
        try:
            amount = round(float(price.get("amount")), 2)
        except (TypeError, ValueError):
            continue
        if amount in amount_to_handle:
            return amount_to_handle[amount]

    return None


class ShopifyManagedPlanAutoSyncMiddleware(BaseHTTPMiddleware):
    """Keep Ashes entitlements aligned with Shopify even when callback params are absent."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/api/shopify/app":
            try:
                subscription = _active_app_pricing_subscription()
                handle = _active_handle(subscription)
                if handle:
                    _sync_managed_plan(handle, request.query_params.get("shop"))
                    print(f"ASHES_SHOPIFY_APP_PRICING_AUTO_SYNC plan={handle}")
                else:
                    print("ASHES_SHOPIFY_APP_PRICING_AUTO_SYNC no_active_paid_plan")
            except Exception as exc:
                # Never block App Home if Shopify's Partner API is temporarily unavailable.
                print(f"ASHES_SHOPIFY_APP_PRICING_AUTO_SYNC_FAILED error={exc}")

        return await call_next(request)


app.add_middleware(ShopifyManagedPlanAutoSyncMiddleware)
