from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from apps.api.mongo_db import collection, clean_doc

PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "key": "free",
        "name": "Free",
        "price_monthly_usd": 0,
        "product_limit": 5,
        "ai_generations_monthly": 5,
        "menu_imports_monthly": 2,
        "table_qr_limit": 3,
        "analytics_days": 7,
        "features": ["3D/AR viewer", "Basic QR ordering", "7-day analytics"],
    },
    "starter": {
        "key": "starter",
        "name": "Starter",
        "price_monthly_usd": 29,
        "product_limit": 50,
        "ai_generations_monthly": 50,
        "menu_imports_monthly": 20,
        "table_qr_limit": 30,
        "analytics_days": 90,
        "features": ["50 products", "50 AI generations/month", "90-day analytics", "Business branding"],
    },
    "pro": {
        "key": "pro",
        "name": "Pro",
        "price_monthly_usd": 79,
        "product_limit": 250,
        "ai_generations_monthly": 250,
        "menu_imports_monthly": 100,
        "table_qr_limit": 200,
        "analytics_days": 3650,
        "features": ["250 products", "250 AI generations/month", "Unlimited-style analytics history", "Priority generation queue", "Advanced branding"],
    },
}


def _month_key() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def plan_for_business(business: dict[str, Any]) -> dict[str, Any]:
    key = str(business.get("plan") or "free").lower()
    return PLANS.get(key, PLANS["free"])


def ensure_subscription_defaults(business_id: str) -> dict[str, Any]:
    business = clean_doc(collection("businesses").find_one({"id": business_id}))
    if not business:
        raise ValueError("Business not found")
    updates: dict[str, Any] = {}
    if not business.get("plan"):
        updates["plan"] = "free"
    if not business.get("subscription_status"):
        updates["subscription_status"] = "active"
    if "billing_customer_id" not in business:
        updates["billing_customer_id"] = None
    if "billing_subscription_id" not in business:
        updates["billing_subscription_id"] = None
    if updates:
        collection("businesses").update_one({"id": business_id}, {"$set": updates})
        business = clean_doc(collection("businesses").find_one({"id": business_id}))
    return business


def usage_snapshot(business_id: str) -> dict[str, int]:
    month = _month_key()
    usage = clean_doc(collection("usage_monthly").find_one({"business_id": business_id, "month": month})) or {}
    return {
        "products": int(collection("products").count_documents({"business_id": business_id})),
        "ai_generations": int(usage.get("ai_generations", 0)),
        "menu_imports": int(usage.get("menu_imports", 0)),
        "table_qrs": int(collection("table_qrs").count_documents({"business_id": business_id})),
    }


def subscription_snapshot(business_id: str) -> dict[str, Any]:
    business = ensure_subscription_defaults(business_id)
    plan = plan_for_business(business)
    usage = usage_snapshot(business_id)
    return {
        "business_id": business_id,
        "plan": plan,
        "status": business.get("subscription_status", "active"),
        "usage": usage,
        "limits": {
            "products": plan["product_limit"],
            "ai_generations": plan["ai_generations_monthly"],
            "menu_imports": plan["menu_imports_monthly"],
            "table_qrs": plan["table_qr_limit"],
        },
        "billing_ready": bool(business.get("billing_customer_id")),
        "month": _month_key(),
    }


def _usage_collection_update(business_id: str, field: str, amount: int) -> None:
    collection("usage_monthly").update_one(
        {"business_id": business_id, "month": _month_key()},
        {"$inc": {field: amount}, "$setOnInsert": {"business_id": business_id, "month": _month_key()}},
        upsert=True,
    )


def increment_usage(business_id: str, field: str, amount: int = 1) -> None:
    if field not in {"ai_generations", "menu_imports"}:
        raise ValueError("Unsupported metered usage field")
    _usage_collection_update(business_id, field, amount)


def assert_capacity(business_id: str, resource: str, amount: int = 1) -> None:
    snapshot = subscription_snapshot(business_id)
    current = int(snapshot["usage"].get(resource, 0))
    limit = int(snapshot["limits"].get(resource, 0))
    if current + amount > limit:
        plan_name = snapshot["plan"]["name"]
        raise ValueError(f"{plan_name} plan limit reached for {resource.replace('_', ' ')}. Upgrade to continue.")


def set_plan(business_id: str, plan_key: str, status: str = "active") -> dict[str, Any]:
    key = plan_key.lower().strip()
    if key not in PLANS:
        raise ValueError("Unknown plan")
    collection("businesses").update_one(
        {"id": business_id},
        {"$set": {"plan": key, "subscription_status": status}},
    )
    return subscription_snapshot(business_id)


def public_plans() -> list[dict[str, Any]]:
    return [PLANS[key] for key in ("free", "starter", "pro")]
