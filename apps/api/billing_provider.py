from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from apps.api.billing_settings import checkout_price
from apps.api.mongo_db import clean_doc, collection
from apps.api.subscriptions import PLANS, subscription_snapshot


def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()

def billing_provider() -> str: return os.getenv("ASHES_BILLING_PROVIDER", "manual").strip().lower() or "manual"

def _stripe_client():
    import stripe
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret: raise ValueError("STRIPE_SECRET_KEY is not configured")
    stripe.api_key = secret
    return stripe


def create_checkout_intent(business_id: str, plan_key: str, success_url: str, cancel_url: str) -> dict[str, Any]:
    key = "starter" if plan_key.strip().lower() in {"starter", "pro"} else plan_key.strip().lower()
    if key != "starter": raise ValueError("Choose the Ashes monthly membership")
    intent_id = str(uuid.uuid4()); provider = billing_provider()
    doc = {"id":intent_id,"business_id":business_id,"plan":"starter","provider":provider,"status":"pending","success_url":success_url,"cancel_url":cancel_url,"provider_session_id":None,"checkout_url":None,"created_at":_now_iso(),"updated_at":_now_iso()}
    if provider == "manual":
        doc["checkout_url"] = None
    elif provider == "stripe":
        stripe = _stripe_client()
        # Pakistan manual billing is Rs 1,400/month. Stripe/international billing is $5/month.
        currency, amount_minor = "usd", 500
        session = stripe.checkout.Session.create(
            mode="subscription", success_url=success_url, cancel_url=cancel_url,
            line_items=[{"price_data":{"currency":currency,"unit_amount":amount_minor,"recurring":{"interval":"month"},"product_data":{"name":"Ashes AI Monthly"}},"quantity":1}],
            metadata={"ashes_intent_id":intent_id,"ashes_business_id":business_id,"ashes_plan":"starter"},
            subscription_data={"metadata":{"ashes_intent_id":intent_id,"ashes_business_id":business_id,"ashes_plan":"starter"}},
        )
        doc["provider_session_id"] = session.id; doc["checkout_url"] = session.url
    else: raise ValueError(f"Unsupported billing provider: {provider}")
    collection("billing_checkout_intents").insert_one(doc); return clean_doc(doc)


def get_checkout_intent(intent_id: str, business_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    query: dict[str, Any] = {"id":intent_id}
    if business_id: query["business_id"] = business_id
    return clean_doc(collection("billing_checkout_intents").find_one(query))


def list_checkout_intents(business_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return [clean_doc(doc) for doc in collection("billing_checkout_intents").find({"business_id":business_id}).sort("created_at",-1).limit(limit)]


def complete_checkout_intent(intent_id: str, provider_session_id: Optional[str] = None, subscription_id: Optional[str] = None, customer_id: Optional[str] = None) -> dict[str, Any]:
    intent = get_checkout_intent(intent_id)
    if not intent: raise ValueError("Checkout intent not found")
    if intent.get("status") == "completed": return subscription_snapshot(intent["business_id"])
    collection("billing_checkout_intents").update_one({"id":intent_id},{"$set":{"status":"completed","provider_session_id":provider_session_id or intent.get("provider_session_id"),"provider_subscription_id":subscription_id,"provider_customer_id":customer_id,"updated_at":_now_iso()}})
    collection("businesses").update_one({"id":intent["business_id"]},{"$set":{"plan":"starter","subscription_status":"active","billing_provider":intent.get("provider") or billing_provider(),"billing_subscription_id":subscription_id,"billing_customer_id":customer_id,"billing_updated_at":_now_iso()}})
    record_subscription_event(intent["business_id"],"checkout.completed",{"intent_id":intent_id,"plan":"starter","provider_session_id":provider_session_id,"subscription_id":subscription_id,"customer_id":customer_id})
    return subscription_snapshot(intent["business_id"])


def cancel_checkout_intent(intent_id: str) -> Optional[dict[str, Any]]:
    intent = get_checkout_intent(intent_id)
    if not intent: return None
    collection("billing_checkout_intents").update_one({"id":intent_id},{"$set":{"status":"cancelled","updated_at":_now_iso()}}); return get_checkout_intent(intent_id)


def record_subscription_event(business_id: str, event_type: str, payload: Optional[dict[str, Any]] = None, provider_event_id: Optional[str] = None) -> dict[str, Any]:
    if provider_event_id:
        existing = clean_doc(collection("billing_events").find_one({"provider_event_id":provider_event_id}))
        if existing: return existing
    doc={"id":str(uuid.uuid4()),"business_id":business_id,"event_type":event_type,"provider_event_id":provider_event_id,"payload":payload or {},"created_at":_now_iso()}; collection("billing_events").insert_one(doc); return clean_doc(doc)


def subscription_history(business_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return [clean_doc(doc) for doc in collection("billing_events").find({"business_id":business_id}).sort("created_at",-1).limit(limit)]


def handle_stripe_webhook(payload: bytes, signature: str) -> dict[str, Any]:
    stripe = _stripe_client(); webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret: raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")
    event = stripe.Webhook.construct_event(payload,signature,webhook_secret); event_id=str(event.get("id") or ""); event_type=str(event.get("type") or ""); obj=event["data"]["object"]
    if event_id and collection("billing_events").find_one({"provider_event_id":event_id}): return {"ok":True,"duplicate":True,"type":event_type}
    if event_type == "checkout.session.completed":
        metadata=obj.get("metadata") or {}; intent_id=metadata.get("ashes_intent_id")
        if intent_id:
            complete_checkout_intent(intent_id,provider_session_id=obj.get("id"),subscription_id=obj.get("subscription"),customer_id=obj.get("customer")); intent=get_checkout_intent(intent_id)
            if intent: record_subscription_event(intent["business_id"],event_type,{"intent_id":intent_id},provider_event_id=event_id)
    elif event_type in {"customer.subscription.deleted","customer.subscription.paused"}:
        business_id=(obj.get("metadata") or {}).get("ashes_business_id")
        if business_id:
            collection("businesses").update_one({"id":business_id},{"$set":{"subscription_status":"cancelled","billing_updated_at":_now_iso()}}); record_subscription_event(business_id,event_type,{"subscription_id":obj.get("id")},provider_event_id=event_id)
    elif event_type == "invoice.payment_failed":
        subscription_id=obj.get("subscription"); business=clean_doc(collection("businesses").find_one({"billing_subscription_id":subscription_id})) if subscription_id else None
        if business:
            collection("businesses").update_one({"id":business["id"]},{"$set":{"subscription_status":"past_due","billing_updated_at":_now_iso()}}); record_subscription_event(business["id"],event_type,{"subscription_id":subscription_id},provider_event_id=event_id)
    else: record_subscription_event("system",event_type,{},provider_event_id=event_id)
    return {"ok":True,"duplicate":False,"type":event_type}
