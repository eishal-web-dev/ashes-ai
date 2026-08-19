from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import app

MAX_ID_LENGTH = 160

# Pricing follows docs/business-model.md. Founder override: free trial = 2 total generations.
SHOPIFY_PLANS: list[dict[str, Any]] = [
    {
        "key": "trial",
        "name": "Free Trial",
        "price": "$0 / 30 days",
        "generation_allowance": 2,
        "generation_period": "total",
        "active_product_guideline": 3,
        "features": ["2 total 3D generations", "3D + AR", "Reusable GLB assets", "Shopify integration"],
    },
    {
        "key": "starter",
        "name": "Starter",
        "price": "$19.99/mo",
        "generation_allowance": 5,
        "generation_period": "month",
        "active_product_guideline": 15,
        "features": ["~5 new twins / month", "~15 active 3D products", "3D + AR", "Reusable assets"],
    },
    {
        "key": "standard",
        "name": "Standard",
        "price": "$45.99/mo",
        "generation_allowance": 20,
        "generation_period": "month",
        "active_product_guideline": 50,
        "features": ["~20 new twins / month", "~50 active 3D products", "3D + AR", "Cross-channel reuse"],
    },
    {
        "key": "pro",
        "name": "Pro",
        "price": "$149.99/mo",
        "generation_allowance": 75,
        "generation_period": "month",
        "active_product_guideline": 250,
        "features": ["~75 new twins / month", "~250 active 3D products", "Priority generation", "3D + AR"],
    },
    {
        "key": "enterprise",
        "name": "Enterprise",
        "price": "Custom",
        "generation_allowance": None,
        "generation_period": "custom",
        "active_product_guideline": "1,000+ / custom",
        "features": ["Custom catalog allowance", "API access", "Bulk workflows", "SLA / dedicated capacity"],
    },
]


def _shop() -> str:
    return (os.getenv("SHOPIFY_SHOP") or "ashes-stack.myshopify.com").strip().lower()


def _worker_url() -> str:
    value = os.getenv("ASHES_TRELLIS_WORKER_URL", "").strip().rstrip("/")
    if not value:
        raise HTTPException(status_code=503, detail="The Ashes 3D worker is offline.")
    if not value.startswith(("https://", "http://")):
        raise HTTPException(status_code=503, detail="The Ashes 3D worker URL is invalid.")
    return value


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _timeout() -> int:
    try:
        return min(60, max(10, int(os.getenv("ASHES_3D_HTTP_TIMEOUT", "30"))))
    except ValueError:
        return 30


def _json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else {"detail": payload}
    except ValueError:
        return {"detail": response.text[:500]}


def _detail(payload: dict[str, Any], fallback: str) -> str:
    value = payload.get("detail") or payload.get("message") or payload.get("error")
    return str(value)[:500] if value is not None else fallback


def _month_key() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def _ensure_indexes() -> None:
    collection("shopify_accounts").create_index("shop", unique=True)
    collection("shopify_generation_state").create_index("shop", unique=True)
    collection("shopify_generation_jobs").create_index("task_id", unique=True)
    collection("shopify_generation_jobs").create_index([("shop", 1), ("created_at", -1)])


try:
    _ensure_indexes()
except Exception:
    # Startup should not fail just because index creation is temporarily unavailable.
    pass


def _account() -> dict[str, Any]:
    shop = _shop()
    collection("shopify_accounts").update_one(
        {"shop": shop},
        {"$setOnInsert": {"shop": shop, "plan_key": "trial", "connected": True, "created_at": now_iso()}},
        upsert=True,
    )
    return collection("shopify_accounts").find_one({"shop": shop}) or {"shop": shop, "plan_key": "trial", "connected": True}


def mark_shopify_connected() -> None:
    collection("shopify_accounts").update_one(
        {"shop": _shop()},
        {"$set": {"connected": True, "last_connected_at": now_iso()}, "$setOnInsert": {"plan_key": "trial", "created_at": now_iso()}},
        upsert=True,
    )


def _plan(plan_key: str) -> dict[str, Any]:
    return next((plan for plan in SHOPIFY_PLANS if plan["key"] == plan_key), SHOPIFY_PLANS[0])


def _usage(plan: dict[str, Any]) -> int:
    query: dict[str, Any] = {"shop": _shop(), "status": "COMPLETED", "counted": True}
    if plan.get("generation_period") == "month":
        query["billing_month"] = _month_key()
    return int(collection("shopify_generation_jobs").count_documents(query))


def _plan_snapshot() -> dict[str, Any]:
    account = _account()
    plan = _plan(str(account.get("plan_key") or "trial"))
    used = _usage(plan)
    allowance = plan.get("generation_allowance")
    remaining = None if allowance is None else max(0, int(allowance) - used)
    return {
        "shop": _shop(),
        "connected": bool(account.get("connected", True)),
        "current_plan": plan,
        "used": used,
        "remaining": remaining,
        "plans": SHOPIFY_PLANS,
        "generation_policy": "one_at_a_time",
        "additional_generation_packs": "Coming after measured GPU cost; see docs/business-model.md",
    }


def _worker_status(task_id: str) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{_worker_url()}/v1/product-to-3d/{task_id}",
            headers=_headers(),
            timeout=_timeout(),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"TRELLIS worker request failed: {str(exc)[:180]}") from exc
    data = _json(response)
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=_detail(data, "Could not read 3D generation status."))
    return data


def _finish_job(task_id: str, data: dict[str, Any]) -> None:
    status = str(data.get("status") or "PROCESSING").upper()
    updates: dict[str, Any] = {
        "status": status,
        "stage": data.get("stage"),
        "progress": float(data.get("progress") or 0),
        "updated_at": now_iso(),
    }
    model_url = data.get("model_url") or (data.get("output") or {}).get("glb_url")
    if model_url:
        updates["model_url"] = model_url
    if data.get("error"):
        updates["error"] = str(data.get("error"))[:1000]
    collection("shopify_generation_jobs").update_one({"task_id": task_id, "shop": _shop()}, {"$set": updates})

    if status in {"SUCCEEDED", "COMPLETED", "FAILED", "CANCELLED"}:
        collection("shopify_generation_state").update_one(
            {"shop": _shop(), "active_task_id": task_id},
            {"$set": {"active_task_id": None, "updated_at": now_iso()}},
        )

    if status in {"SUCCEEDED", "COMPLETED"}:
        result = collection("shopify_generation_jobs").update_one(
            {"task_id": task_id, "shop": _shop(), "counted": {"$ne": True}},
            {"$set": {"counted": True, "status": "COMPLETED", "completed_at": now_iso()}},
        )
        if result.modified_count and model_url:
            job = collection("shopify_generation_jobs").find_one({"task_id": task_id, "shop": _shop()}) or {}
            collection("shopify_3d_assets").update_one(
                {"shop": _shop(), "product_id": job.get("product_id")},
                {"$set": {
                    "shop": _shop(),
                    "product_id": job.get("product_id"),
                    "product_name": job.get("product_name"),
                    "model_url": model_url,
                    "storefront_enabled": True,
                    "updated_at": now_iso(),
                }},
                upsert=True,
            )


def _reconcile_active() -> dict[str, Any] | None:
    state = collection("shopify_generation_state").find_one({"shop": _shop()}) or {}
    task_id = str(state.get("active_task_id") or "").strip()
    if not task_id or task_id.startswith("starting:"):
        return state if task_id else None
    try:
        data = _worker_status(task_id)
    except HTTPException:
        return state
    _finish_job(task_id, data)
    refreshed = collection("shopify_generation_state").find_one({"shop": _shop()}) or {}
    return refreshed if refreshed.get("active_task_id") else None


class ShopifyGeneratePayload(BaseModel):
    product_id: str = Field(min_length=1, max_length=200)
    product_name: str = Field(default="Product", max_length=180)
    image_url: str


@app.get("/api/shopify/plans")
def shopify_plans() -> dict[str, Any]:
    mark_shopify_connected()
    snapshot = _plan_snapshot()
    active = _reconcile_active()
    snapshot["active_generation"] = active.get("active_task_id") if active else None
    return snapshot


@app.post("/api/shopify/generate-3d", status_code=202)
def shopify_start_generation(payload: ShopifyGeneratePayload) -> dict[str, Any]:
    mark_shopify_connected()
    image_url = payload.image_url.strip()
    if not image_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Provide a public HTTPS product image URL.")

    active = _reconcile_active()
    if active and active.get("active_task_id"):
        raise HTTPException(status_code=409, detail="Another product is already generating. Ashes generates one 3D product at a time for this store.")

    snapshot = _plan_snapshot()
    allowance = snapshot["current_plan"].get("generation_allowance")
    if allowance is not None and int(snapshot["used"]) >= int(allowance):
        raise HTTPException(
            status_code=402,
            detail=f"{snapshot['current_plan']['name']} generation limit reached. Choose a paid package to generate more 3D products.",
        )

    lock_id = f"starting:{uuid.uuid4().hex}"
    try:
        locked = collection("shopify_generation_state").find_one_and_update(
            {"shop": _shop(), "$or": [{"active_task_id": None}, {"active_task_id": {"$exists": False}}]},
            {"$set": {"shop": _shop(), "active_task_id": lock_id, "updated_at": now_iso()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        locked = None
    if not locked or locked.get("active_task_id") != lock_id:
        raise HTTPException(status_code=409, detail="Another product is already generating. Please wait for it to finish.")

    body = {"image_url": image_url, "product_name": payload.product_name}
    try:
        response = requests.post(
            f"{_worker_url()}/v1/product-to-3d",
            json=body,
            headers=_headers(),
            timeout=_timeout(),
        )
        data = _json(response)
        if not response.ok:
            raise HTTPException(status_code=response.status_code, detail=_detail(data, "The TRELLIS worker could not start this generation."))
        task_id = str(data.get("task_id") or data.get("id") or "").strip()
        if not task_id:
            raise HTTPException(status_code=502, detail="The 3D worker did not return a task ID.")
    except Exception:
        collection("shopify_generation_state").update_one(
            {"shop": _shop(), "active_task_id": lock_id}, {"$set": {"active_task_id": None, "updated_at": now_iso()}}
        )
        raise

    collection("shopify_generation_jobs").insert_one({
        "task_id": task_id,
        "shop": _shop(),
        "product_id": payload.product_id,
        "product_name": payload.product_name,
        "image_url": image_url,
        "status": str(data.get("status") or "QUEUED").upper(),
        "stage": data.get("stage") or "QUEUED",
        "progress": float(data.get("progress") or 0),
        "counted": False,
        "billing_month": _month_key(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    collection("shopify_generation_state").update_one(
        {"shop": _shop(), "active_task_id": lock_id},
        {"$set": {"active_task_id": task_id, "product_id": payload.product_id, "updated_at": now_iso()}},
    )
    return {"task_id": task_id, "status": data.get("status") or "QUEUED", "stage": data.get("stage") or "QUEUED", "plan": snapshot["current_plan"]["key"]}


@app.get("/api/shopify/generate-3d")
def shopify_generation_status(id: str = Query(..., min_length=1, max_length=MAX_ID_LENGTH)) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", id):
        raise HTTPException(status_code=400, detail="Invalid generation task.")
    job = collection("shopify_generation_jobs").find_one({"task_id": id, "shop": _shop()})
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found for this Shopify store.")
    data = _worker_status(id)
    _finish_job(id, data)
    snapshot = _plan_snapshot()
    return {
        "task_id": id,
        "status": str(data.get("status") or "PROCESSING").upper(),
        "stage": data.get("stage"),
        "progress": float(data.get("progress") or 0),
        "model_url": data.get("model_url") or (data.get("output") or {}).get("glb_url"),
        "thumbnail_url": data.get("thumbnail_url") or (data.get("output") or {}).get("thumbnail_url"),
        "error": data.get("error"),
        "plan_usage": {"used": snapshot["used"], "remaining": snapshot["remaining"]},
    }


def _verify_shopify_webhook(raw_body: bytes, signature: str) -> bool:
    secret = (os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("ASHES_SHOPIFY_CLIENT_SECRET") or "").strip()
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


def _disconnect_shop(shop: str) -> None:
    shop = shop.strip().lower() or _shop()
    collection("shopify_accounts").update_one(
        {"shop": shop}, {"$set": {"connected": False, "disconnected_at": now_iso()}}, upsert=True
    )
    collection("shopify_generation_state").update_one(
        {"shop": shop}, {"$set": {"active_task_id": None, "updated_at": now_iso()}}, upsert=True
    )
    # Generated GLBs stay in Ashes for reuse, but storefront service links are disabled/removed.
    collection("shopify_3d_assets").update_many(
        {"shop": shop}, {"$set": {"storefront_enabled": False, "disconnected_at": now_iso()}}
    )
    collection("shopify_storefront_services").delete_many({"shop": shop})


@app.post("/api/shopify/webhooks/app-uninstalled", include_in_schema=False)
async def shopify_app_uninstalled(request: Request) -> dict[str, bool]:
    raw = await request.body()
    signature = request.headers.get("x-shopify-hmac-sha256", "")
    if not _verify_shopify_webhook(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")
    webhook_shop = request.headers.get("x-shopify-shop-domain", _shop())
    _disconnect_shop(webhook_shop)
    return {"ok": True}
