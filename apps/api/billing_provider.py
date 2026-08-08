from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from apps.api.mongo_db import clean_doc, collection
from apps.api.subscriptions import PLANS, subscription_snapshot


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def billing_provider() -> str:
    return os.getenv("ASHES_BILLING_PROVIDER", "manual").strip().lower() or "manual"


def create_checkout_intent(business_id: str, plan_key: str, success_url: str, cancel_url: str) -> dict[str, Any]:
    key = plan_key.strip().lower()
    if key not in PLANS or key == "free":
        raise ValueError("Choose a paid plan")

    intent_id = str(uuid.uuid4())
    provider = billing_provider()
    doc = {
        "id": intent_id,
        "business_id": business_id,
        "plan": key,
        "provider": provider,
        "status": "pending",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "provider_session_id": None,
        "checkout_url": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    if provider == "manual":
        # Development mode: no card is charged. The frontend gets an explicit
        # pending checkout state instead of silently upgrading the business.
        doc["checkout_url"] = None
    elif provider == "stripe":
        # Stripe integration is intentionally isolated here. Once STRIPE_* env
        # values are configured, this function can create a Checkout Session
        # without changing routes, dashboard code, or subscription storage.
        raise ValueError("Stripe provider is configured but checkout is not enabled yet")
    else:
        raise ValueError(f"Unsupported billing provider: {provider}")

    collection("billing_checkout_intents").insert_one(doc)
    return clean_doc(doc)


def get_checkout_intent(intent_id: str, business_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    query: dict[str, Any] = {"id": intent_id}
    if business_id:
        query["business_id"] = business_id
    return clean_doc(collection("billing_checkout_intents").find_one(query))


def list_checkout_intents(business_id: str, limit: int = 20) -> list[dict[str, Any]]:
    docs = collection("billing_checkout_intents").find({"business_id": business_id}).sort("created_at", -1).limit(limit)
    return [clean_doc(doc) for doc in docs]


def complete_checkout_intent(intent_id: str, provider_session_id: Optional[str] = None) -> dict[str, Any]:
    intent = get_checkout_intent(intent_id)
    if not intent:
        raise ValueError("Checkout intent not found")
    collection("billing_checkout_intents").update_one(
        {"id": intent_id},
        {"$set": {
            "status": "completed",
            "provider_session_id": provider_session_id or intent.get("provider_session_id"),
            "updated_at": _now_iso(),
        }},
    )
    collection("businesses").update_one(
        {"id": intent["business_id"]},
        {"$set": {
            "plan": intent["plan"],
            "subscription_status": "active",
            "billing_provider": intent.get("provider") or billing_provider(),
            "billing_updated_at": _now_iso(),
        }},
    )
    record_subscription_event(
        intent["business_id"],
        "checkout.completed",
        {"intent_id": intent_id, "plan": intent["plan"], "provider_session_id": provider_session_id},
    )
    return subscription_snapshot(intent["business_id"])


def cancel_checkout_intent(intent_id: str) -> Optional[dict[str, Any]]:
    intent = get_checkout_intent(intent_id)
    if not intent:
        return None
    collection("billing_checkout_intents").update_one(
        {"id": intent_id},
        {"$set": {"status": "cancelled", "updated_at": _now_iso()}},
    )
    return get_checkout_intent(intent_id)


def record_subscription_event(business_id: str, event_type: str, payload: Optional[dict[str, Any]] = None, provider_event_id: Optional[str] = None) -> dict[str, Any]:
    if provider_event_id:
        existing = clean_doc(collection("billing_events").find_one({"provider_event_id": provider_event_id}))
        if existing:
            return existing
    doc = {
        "id": str(uuid.uuid4()),
        "business_id": business_id,
        "event_type": event_type,
        "provider_event_id": provider_event_id,
        "payload": payload or {},
        "created_at": _now_iso(),
    }
    collection("billing_events").insert_one(doc)
    return clean_doc(doc)


def subscription_history(business_id: str, limit: int = 50) -> list[dict[str, Any]]:
    docs = collection("billing_events").find({"business_id": business_id}).sort("created_at", -1).limit(limit)
    return [clean_doc(doc) for doc in docs]
