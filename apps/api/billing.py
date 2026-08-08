from __future__ import annotations

import os

from pydantic import BaseModel
from fastapi import Depends, HTTPException

from apps.api.billing_provider import (
    billing_provider,
    complete_checkout_intent,
    create_checkout_intent,
    get_checkout_intent,
    list_checkout_intents,
    subscription_history,
)
from apps.api.mongo_main import PUBLIC_BASE_URL, app, auth_user, owned_business
from apps.api.subscriptions import public_plans, subscription_snapshot


class CheckoutPayload(BaseModel):
    plan: str
    success_url: str | None = None
    cancel_url: str | None = None


@app.get("/api/billing/plans")
def billing_plans():
    return {"plans": public_plans(), "provider": billing_provider()}


@app.get("/api/businesses/{business_slug}/billing")
def business_billing(business_slug: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    snapshot = subscription_snapshot(business["id"])
    snapshot["provider"] = billing_provider()
    snapshot["checkout_intents"] = list_checkout_intents(business["id"], limit=5)
    return snapshot


@app.get("/api/businesses/{business_slug}/billing/history")
def billing_history(business_slug: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    return {"events": subscription_history(business["id"], limit=50)}


@app.post("/api/businesses/{business_slug}/billing/checkout")
def create_business_checkout(business_slug: str, payload: CheckoutPayload, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    success_url = payload.success_url or f"{PUBLIC_BASE_URL}/?billing=success"
    cancel_url = payload.cancel_url or f"{PUBLIC_BASE_URL}/?billing=cancelled"
    try:
        return create_checkout_intent(business["id"], payload.plan, success_url, cancel_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/businesses/{business_slug}/billing/checkout/{intent_id}")
def get_business_checkout(business_slug: str, intent_id: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    intent = get_checkout_intent(intent_id, business["id"])
    if not intent:
        raise HTTPException(status_code=404, detail="Checkout intent not found")
    return intent


@app.post("/api/businesses/{business_slug}/billing/checkout/{intent_id}/dev-complete")
def dev_complete_business_checkout(business_slug: str, intent_id: str, user: dict = Depends(auth_user)):
    if os.getenv("ASHES_ALLOW_DEV_BILLING", "false").strip().lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Development billing activation is disabled")
    business = owned_business(user["id"], business_slug)
    intent = get_checkout_intent(intent_id, business["id"])
    if not intent:
        raise HTTPException(status_code=404, detail="Checkout intent not found")
    try:
        return complete_checkout_intent(intent_id, provider_session_id=f"dev_{intent_id[:12]}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
