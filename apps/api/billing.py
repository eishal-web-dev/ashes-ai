from __future__ import annotations

from pydantic import BaseModel
from fastapi import Depends, HTTPException

from apps.api.mongo_main import app, auth_user, owned_business
from apps.api.subscriptions import public_plans, set_plan, subscription_snapshot


class PlanChangePayload(BaseModel):
    plan: str


@app.get("/api/billing/plans")
def billing_plans():
    return {"plans": public_plans()}


@app.get("/api/businesses/{business_slug}/billing")
def business_billing(business_slug: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    return subscription_snapshot(business["id"])


@app.post("/api/businesses/{business_slug}/billing/plan")
def change_business_plan(business_slug: str, payload: PlanChangePayload, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    try:
        return set_plan(business["id"], payload.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
