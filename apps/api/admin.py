from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from apps.api.mongo_main import app, auth_user
from apps.api.mongo_db import clean_doc, clean_docs, collection
from apps.api.subscriptions import subscription_snapshot


def _admin_emails() -> set[str]:
    raw = os.getenv("ASHES_ADMIN_EMAILS", "")
    return {value.strip().lower() for value in raw.split(",") if value.strip()}


def require_admin(user: dict = Depends(auth_user)) -> dict:
    email = str(user.get("email") or "").strip().lower()
    if not email or email not in _admin_emails():
        raise HTTPException(status_code=403, detail="Ashes admin access required")
    return user


class BusinessAdminPayload(BaseModel):
    action: str


def _business_summary(business: dict[str, Any]) -> dict[str, Any]:
    business_id = business["id"]
    snapshot = subscription_snapshot(business_id)
    products = int(collection("products").count_documents({"business_id": business_id}))
    orders = int(collection("orders").count_documents({"business_id": business_id}))
    failed_3d = int(collection("products").count_documents({"business_id": business_id, "status": "failed"}))
    pending_3d = int(collection("products").count_documents({"business_id": business_id, "status": {"$in": ["queued", "processing", "awaiting-generator"]}}))
    order_total_pipeline = [
        {"$match": {"business_id": business_id, "status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}}},
    ]
    order_totals = list(collection("orders").aggregate(order_total_pipeline))
    order_value = float(order_totals[0].get("total", 0)) if order_totals else 0.0
    return {
        "id": business_id,
        "name": business.get("name"),
        "slug": business.get("slug"),
        "kind": business.get("kind"),
        "city": business.get("city"),
        "plan": snapshot.get("plan"),
        "subscription_status": snapshot.get("status"),
        "account_status": business.get("account_status", "active"),
        "products": products,
        "orders": orders,
        "order_value": order_value,
        "failed_3d": failed_3d,
        "pending_3d": pending_3d,
        "usage": snapshot.get("usage", {}),
        "limits": snapshot.get("limits", {}),
        "created_at": business.get("created_at"),
    }


@app.get("/api/admin/overview")
def admin_overview(_: dict = Depends(require_admin)):
    businesses = clean_docs(collection("businesses").find({}).sort("created_at", -1))
    total_businesses = len(businesses)
    active_businesses = sum(1 for b in businesses if b.get("account_status", "active") == "active")
    total_products = int(collection("products").count_documents({}))
    total_orders = int(collection("orders").count_documents({}))
    failed_3d = int(collection("products").count_documents({"status": "failed"}))
    pending_3d = int(collection("products").count_documents({"status": {"$in": ["queued", "processing", "awaiting-generator"]}}))
    pending_checkouts = int(collection("billing_checkouts").count_documents({"status": "pending"}))
    paid_businesses = int(collection("businesses").count_documents({"plan": {"$in": ["starter", "pro"]}, "subscription_status": "active"}))

    revenue_pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$total"}}},
    ]
    revenue_rows = list(collection("orders").aggregate(revenue_pipeline))
    gross_order_value = float(revenue_rows[0].get("total", 0)) if revenue_rows else 0.0

    plan_counts = {"free": 0, "starter": 0, "pro": 0}
    for business in businesses:
        key = str(business.get("plan") or "free").lower()
        if key in plan_counts:
            plan_counts[key] += 1

    return {
        "totals": {
            "businesses": total_businesses,
            "active_businesses": active_businesses,
            "products": total_products,
            "orders": total_orders,
            "gross_order_value": gross_order_value,
            "paid_businesses": paid_businesses,
            "failed_3d": failed_3d,
            "pending_3d": pending_3d,
            "pending_checkouts": pending_checkouts,
        },
        "plans": plan_counts,
        "businesses": [_business_summary(b) for b in businesses[:100]],
    }


@app.get("/api/admin/businesses/{business_id}")
def admin_business_detail(business_id: str, _: dict = Depends(require_admin)):
    business = clean_doc(collection("businesses").find_one({"id": business_id}))
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return {
        "business": _business_summary(business),
        "products": clean_docs(collection("products").find({"business_id": business_id}).sort("created_at", -1).limit(100)),
        "orders": clean_docs(collection("orders").find({"business_id": business_id}).sort("created_at", -1).limit(100)),
        "menu_imports": clean_docs(collection("menu_imports").find({"business_id": business_id}).sort("created_at", -1).limit(30)),
        "billing_checkouts": clean_docs(collection("billing_checkouts").find({"business_id": business_id}).sort("created_at", -1).limit(30)),
        "billing_events": clean_docs(collection("billing_events").find({"business_id": business_id}).sort("created_at", -1).limit(50)),
    }


@app.patch("/api/admin/businesses/{business_id}")
def admin_business_action(business_id: str, payload: BusinessAdminPayload, admin: dict = Depends(require_admin)):
    business = clean_doc(collection("businesses").find_one({"id": business_id}))
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    action = payload.action.strip().lower()
    if action not in {"suspend", "reactivate"}:
        raise HTTPException(status_code=400, detail="Unsupported admin action")

    status = "suspended" if action == "suspend" else "active"
    collection("businesses").update_one({"id": business_id}, {"$set": {"account_status": status}})
    collection("admin_events").insert_one({
        "business_id": business_id,
        "action": action,
        "admin_user_id": admin.get("id"),
        "admin_email": admin.get("email"),
    })
    updated = clean_doc(collection("businesses").find_one({"id": business_id}))
    return _business_summary(updated)


@app.get("/api/admin/jobs")
def admin_jobs(_: dict = Depends(require_admin)):
    query = {"status": {"$in": ["queued", "processing", "awaiting-generator", "failed"]}}
    rows = clean_docs(collection("products").find(query).sort("created_at", -1).limit(200))
    return {"jobs": [
        {
            "product_id": row.get("id"),
            "business_id": row.get("business_id"),
            "name": row.get("name"),
            "status": row.get("status"),
            "error_message": row.get("error_message"),
            "created_at": row.get("created_at"),
        }
        for row in rows
    ]}


@app.get("/api/admin/billing")
def admin_billing(_: dict = Depends(require_admin)):
    return {
        "pending_checkouts": clean_docs(collection("billing_checkouts").find({"status": "pending"}).sort("created_at", -1).limit(100)),
        "recent_events": clean_docs(collection("billing_events").find({}).sort("created_at", -1).limit(100)),
    }
