from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from apps.api.mongo_db import collection, clean_doc

TRIAL_DAYS = 30

# Keep stable internal keys for backwards compatibility, but Ashes now sells one product:
# 30-day full trial -> Ashes monthly membership. Resource limits are generous guardrails,
# not product-based pricing tiers.
PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "key": "free",
        "name": "30-Day Trial",
        "price_monthly_usd": 0,
        "product_limit": 1000,
        "ai_generations_monthly": 1000,
        "menu_imports_monthly": 500,
        "table_qr_limit": 1000,
        "analytics_days": 3650,
        "features": ["Full Ashes platform", "3D + AR", "Smart QR", "Commerce Source", "Orders OS", "Analytics"],
    },
    "starter": {
        "key": "starter",
        "name": "Ashes",
        "price_monthly_usd": 5,
        "product_limit": 10000,
        "ai_generations_monthly": 10000,
        "menu_imports_monthly": 5000,
        "table_qr_limit": 10000,
        "analytics_days": 3650,
        "features": ["Everything in Ashes", "Unlimited-style catalog", "3D + AR experiences", "Smart QR Studio", "Website/store integration", "Orders & analytics"],
    },
    # Legacy key retained so older database rows do not break. It is not sold publicly.
    "pro": {
        "key": "pro",
        "name": "Ashes",
        "price_monthly_usd": 5,
        "product_limit": 10000,
        "ai_generations_monthly": 10000,
        "menu_imports_monthly": 5000,
        "table_qr_limit": 10000,
        "analytics_days": 3650,
        "features": ["Everything in Ashes"],
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_key() -> str:
    now = _now()
    return f"{now.year:04d}-{now.month:02d}"


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def plan_for_business(business: dict[str, Any]) -> dict[str, Any]:
    key = str(business.get("plan") or "free").lower()
    if key == "pro": key = "starter"
    return PLANS.get(key, PLANS["free"])


def ensure_subscription_defaults(business_id: str) -> dict[str, Any]:
    business = clean_doc(collection("businesses").find_one({"id": business_id}))
    if not business:
        raise ValueError("Business not found")
    updates: dict[str, Any] = {}
    created = _parse_dt(business.get("created_at")) or _now()
    if not business.get("trial_started_at"):
        updates["trial_started_at"] = created.isoformat()
    if not business.get("trial_ends_at"):
        updates["trial_ends_at"] = (created + timedelta(days=TRIAL_DAYS)).isoformat()
    if not business.get("plan"):
        updates["plan"] = "free"
    if not business.get("subscription_status"):
        updates["subscription_status"] = "trialing"
    if "billing_customer_id" not in business: updates["billing_customer_id"] = None
    if "billing_subscription_id" not in business: updates["billing_subscription_id"] = None
    if updates:
        collection("businesses").update_one({"id": business_id}, {"$set": updates})
        business = clean_doc(collection("businesses").find_one({"id": business_id}))
    return business


def trial_state(business: dict[str, Any]) -> dict[str, Any]:
    plan_key = "starter" if str(business.get("plan") or "free").lower() in {"starter", "pro"} else "free"
    end = _parse_dt(business.get("trial_ends_at"))
    active_paid = plan_key == "starter" and business.get("subscription_status") in {"active", "paid"}
    if active_paid:
        return {"is_trial": False, "trial_active": False, "trial_expired": False, "trial_days_left": 0, "trial_ends_at": end.isoformat() if end else None}
    remaining = max(0, int(((end or _now()) - _now()).total_seconds() // 86400) + (1 if end and end > _now() else 0))
    expired = bool(end and _now() >= end)
    return {"is_trial": True, "trial_active": not expired, "trial_expired": expired, "trial_days_left": remaining, "trial_ends_at": end.isoformat() if end else None}


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
    trial = trial_state(business)
    paid = str(business.get("plan") or "free").lower() in {"starter", "pro"} and business.get("subscription_status") in {"active", "paid"}
    plan = PLANS["starter"] if paid else PLANS["free"]
    usage = usage_snapshot(business_id)
    return {
        "business_id": business_id,
        "plan": plan,
        "status": "active" if paid else ("trialing" if trial["trial_active"] else "trial_expired"),
        "usage": usage,
        "limits": {
            "products": plan["product_limit"], "ai_generations": plan["ai_generations_monthly"],
            "menu_imports": plan["menu_imports_monthly"], "table_qrs": plan["table_qr_limit"],
        },
        "billing_ready": bool(business.get("billing_customer_id")),
        "month": _month_key(),
        **trial,
    }


def _usage_collection_update(business_id: str, field: str, amount: int) -> None:
    collection("usage_monthly").update_one(
        {"business_id": business_id, "month": _month_key()},
        {"$inc": {field: amount}, "$setOnInsert": {"business_id": business_id, "month": _month_key()}}, upsert=True,
    )


def increment_usage(business_id: str, field: str, amount: int = 1) -> None:
    if field not in {"ai_generations", "menu_imports"}: raise ValueError("Unsupported metered usage field")
    _usage_collection_update(business_id, field, amount)


def assert_capacity(business_id: str, resource: str, amount: int = 1) -> None:
    snapshot = subscription_snapshot(business_id)
    if snapshot.get("trial_expired"):
        raise ValueError("Your 30-day Ashes trial has ended. Subscribe for Rs 1,400/month to continue.")
    current = int(snapshot["usage"].get(resource, 0)); limit = int(snapshot["limits"].get(resource, 0))
    if current + amount > limit:
        raise ValueError("Ashes fair-use capacity reached. Contact support so we can expand your workspace.")


def set_plan(business_id: str, plan_key: str, status: str = "active") -> dict[str, Any]:
    key = plan_key.lower().strip()
    if key not in {"starter", "pro"}: raise ValueError("Unknown plan")
    collection("businesses").update_one({"id": business_id}, {"$set": {"plan": "starter", "subscription_status": status}})
    return subscription_snapshot(business_id)


def public_plans() -> list[dict[str, Any]]:
    return [PLANS["free"], PLANS["starter"]]
