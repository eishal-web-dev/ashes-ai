from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from apps.api.media_storage import media_url, store_media
from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import API_BASE_URL, app

MAX_ID_LENGTH = 160
MAX_GLB_BYTES = 120_000_000

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


def _headers(content_type: bool = True) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = "application/json"
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


def _safe_shop_key() -> str:
    return re.sub(r"[^a-z0-9.-]+", "-", _shop()).strip("-") or "shopify-store"


def _ensure_indexes() -> None:
    collection("shopify_accounts").create_index("shop", unique=True)
    collection("shopify_generation_state").create_index("shop", unique=True)
    collection("shopify_generation_jobs").create_index("task_id", unique=True)
    collection("shopify_generation_jobs").create_index([("shop", 1), ("created_at", -1)])
    collection("shopify_3d_assets").create_index([("shop", 1), ("product_id", 1)], unique=True)


try:
    _ensure_indexes()
except Exception:
    pass


def _account() -> dict[str, Any]:
    shop = _shop()
    collection("shopify_accounts").update_one(
        {"shop": shop},
        {"$setOnInsert": {"shop": shop, "plan_key": "trial", "connected": True, "created_at": now_iso()}},
        upsert=True,
    )
    return collection("shopify_accounts").find_one({"shop": shop}) or {"shop": shop, "plan_key": "trial", "connected": True}


def _require_connected() -> dict[str, Any]:
    account = _account()
    if not bool(account.get("connected", True)):
        raise HTTPException(status_code=403, detail="Ashes is disconnected from this Shopify store.")
    return account


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


def _asset(product_id: str) -> dict[str, Any] | None:
    return collection("shopify_3d_assets").find_one({"shop": _shop(), "product_id": product_id, "model_path": {"$exists": True, "$ne": None}})


def shopify_assets_for_products(product_ids: list[str]) -> dict[str, dict[str, Any]]:
    ids = [str(value) for value in product_ids if value]
    if not ids:
        return {}
    rows = collection("shopify_3d_assets").find({"shop": _shop(), "product_id": {"$in": ids}, "model_path": {"$exists": True, "$ne": None}})
    return {
        str(row.get("product_id")): {
            "ready": True,
            "viewer_url": f"/api/shopify/viewer/{row.get('product_id')}",
            "updated_at": row.get("updated_at"),
            "storefront_enabled": bool(row.get("storefront_enabled", True)),
        }
        for row in rows
    }


def _worker_status(task_id: str) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{_worker_url()}/v1/product-to-3d/{task_id}",
            headers=_headers(False),
            timeout=_timeout(),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"TRELLIS worker request failed: {str(exc)[:180]}") from exc
    data = _json(response)
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=_detail(data, "Could not read 3D generation status."))
    return data


def _persist_modal_glb(task_id: str, model_url: str) -> tuple[str, dict[str, Any]]:
    job = collection("shopify_generation_jobs").find_one({"task_id": task_id, "shop": _shop()}) or {}
    product_id = str(job.get("product_id") or "").strip()
    if not product_id:
        raise RuntimeError("Shopify generation job is missing product identity")

    existing = _asset(product_id)
    if existing and existing.get("model_path"):
        return str(existing["model_path"]), existing

    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
    temp_path = Path(handle.name)
    handle.close()
    size = 0
    try:
        with requests.get(model_url, headers=_headers(False), timeout=120, stream=True) as response:
            response.raise_for_status()
            with temp_path.open("wb") as output:
                for chunk in response.iter_content(1024 * 256):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_GLB_BYTES:
                        raise RuntimeError("Generated GLB exceeds Ashes storage safety limit")
                    output.write(chunk)
        raw = temp_path.read_bytes()[:12]
        if len(raw) < 12 or raw[:4] != b"glTF":
            raise RuntimeError("Generated model is not a valid GLB binary")

        model_key = store_media(
            API_BASE_URL,
            temp_path,
            f"models/shopify/{_safe_shop_key()}/{hashlib.sha256(product_id.encode('utf-8')).hexdigest()[:32]}.glb",
            "model/gltf-binary",
        )
        doc = {
            "shop": _shop(),
            "product_id": product_id,
            "product_name": job.get("product_name"),
            "model_path": model_key,
            "source_task_id": task_id,
            "size_bytes": size,
            "storefront_enabled": True,
            "updated_at": now_iso(),
        }
        collection("shopify_3d_assets").update_one(
            {"shop": _shop(), "product_id": product_id},
            {"$set": doc, "$setOnInsert": {"created_at": now_iso()}},
            upsert=True,
        )
        return model_key, doc
    finally:
        temp_path.unlink(missing_ok=True)


def _finish_job(task_id: str, data: dict[str, Any]) -> None:
    status = str(data.get("status") or "PROCESSING").upper()
    updates: dict[str, Any] = {
        "status": status,
        "stage": data.get("stage"),
        "progress": float(data.get("progress") or 0),
        "updated_at": now_iso(),
    }
    model_url = data.get("model_url") or (data.get("output") or {}).get("glb_url")
    if data.get("error"):
        updates["error"] = str(data.get("error"))[:1000]
    collection("shopify_generation_jobs").update_one({"task_id": task_id, "shop": _shop()}, {"$set": updates})

    terminal = status in {"SUCCEEDED", "COMPLETED", "FAILED", "CANCELLED"}
    if status in {"SUCCEEDED", "COMPLETED"}:
        if not model_url:
            collection("shopify_generation_jobs").update_one(
                {"task_id": task_id, "shop": _shop()},
                {"$set": {"status": "STORAGE_FAILED", "error": "3D worker completed without a model URL", "updated_at": now_iso()}},
            )
            terminal = True
        else:
            try:
                model_path, _ = _persist_modal_glb(task_id, str(model_url))
            except Exception as exc:
                collection("shopify_generation_jobs").update_one(
                    {"task_id": task_id, "shop": _shop()},
                    {"$set": {"status": "STORAGE_FAILED", "error": f"Ashes storage persistence failed: {str(exc)[:700]}", "updated_at": now_iso()}},
                )
                terminal = True
            else:
                collection("shopify_generation_jobs").update_one(
                    {"task_id": task_id, "shop": _shop(), "counted": {"$ne": True}},
                    {"$set": {"counted": True, "status": "COMPLETED", "model_path": model_path, "completed_at": now_iso(), "updated_at": now_iso()}},
                )
                terminal = True

    if terminal:
        collection("shopify_generation_state").update_one(
            {"shop": _shop(), "active_task_id": task_id},
            {"$set": {"active_task_id": None, "updated_at": now_iso()}},
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
    active = _reconcile_active()
    snapshot = _plan_snapshot()
    snapshot["active_generation"] = active.get("active_task_id") if active else None
    return snapshot


@app.get("/api/shopify/assets")
def shopify_assets() -> dict[str, Any]:
    _require_connected()
    rows = list(collection("shopify_3d_assets").find({"shop": _shop(), "model_path": {"$exists": True, "$ne": None}}))
    return {
        "assets": [
            {
                "product_id": row.get("product_id"),
                "product_name": row.get("product_name"),
                "viewer_url": f"/api/shopify/viewer/{row.get('product_id')}",
                "ready": True,
                "updated_at": row.get("updated_at"),
            }
            for row in rows
        ]
    }


@app.post("/api/shopify/generate-3d", status_code=202)
def shopify_start_generation(payload: ShopifyGeneratePayload) -> dict[str, Any]:
    mark_shopify_connected()
    image_url = payload.image_url.strip()
    if not image_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Provide a public HTTPS product image URL.")

    existing = _asset(payload.product_id)
    if existing:
        return {
            "task_id": str(existing.get("source_task_id") or f"stored:{hashlib.sha1(payload.product_id.encode()).hexdigest()[:16]}"),
            "status": "COMPLETED",
            "stage": "REUSED_STORED_TWIN",
            "reused": True,
            "viewer_url": f"/api/shopify/viewer/{payload.product_id}",
            "plan": _plan_snapshot()["current_plan"]["key"],
        }

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
    return {"task_id": task_id, "status": data.get("status") or "QUEUED", "stage": data.get("stage") or "QUEUED", "reused": False, "plan": snapshot["current_plan"]["key"]}


@app.get("/api/shopify/generate-3d")
def shopify_generation_status(id: str = Query(..., min_length=1, max_length=MAX_ID_LENGTH)) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", id):
        raise HTTPException(status_code=400, detail="Invalid generation task.")
    job = collection("shopify_generation_jobs").find_one({"task_id": id, "shop": _shop()})
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found for this Shopify store.")

    if str(job.get("status") or "").upper() == "COMPLETED" and job.get("model_path"):
        snapshot = _plan_snapshot()
        return {
            "task_id": id,
            "status": "COMPLETED",
            "stage": "STORED_IN_ASHES",
            "progress": 100,
            "viewer_url": f"/api/shopify/viewer/{job.get('product_id')}",
            "reused": True,
            "plan_usage": {"used": snapshot["used"], "remaining": snapshot["remaining"]},
        }

    data = _worker_status(id)
    _finish_job(id, data)
    refreshed = collection("shopify_generation_jobs").find_one({"task_id": id, "shop": _shop()}) or {}
    snapshot = _plan_snapshot()
    final_status = str(refreshed.get("status") or data.get("status") or "PROCESSING").upper()
    return {
        "task_id": id,
        "status": final_status,
        "stage": "STORED_IN_ASHES" if final_status == "COMPLETED" and refreshed.get("model_path") else (refreshed.get("stage") or data.get("stage")),
        "progress": 100 if final_status == "COMPLETED" else float(refreshed.get("progress") or data.get("progress") or 0),
        "viewer_url": f"/api/shopify/viewer/{refreshed.get('product_id')}" if final_status == "COMPLETED" and refreshed.get("model_path") else None,
        "error": refreshed.get("error") or data.get("error"),
        "plan_usage": {"used": snapshot["used"], "remaining": snapshot["remaining"]},
    }


@app.get("/api/shopify/viewer/{product_id}", response_class=HTMLResponse)
def shopify_3d_viewer(product_id: str) -> HTMLResponse:
    _require_connected()
    asset = _asset(product_id)
    if not asset or not bool(asset.get("storefront_enabled", True)):
        raise HTTPException(status_code=404, detail="This Ashes 3D product is not available.")
    title = str(asset.get("product_name") or "Product").replace("<", "&lt;").replace(">", "&gt;")
    model_src = f"/api/shopify/model/{product_id}"
    html = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Ashes 3D</title><script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.1.0/model-viewer.min.js"></script><style>html,body{{margin:0;width:100%;height:100%;background:#090909;color:#fff;font-family:Inter,system-ui,sans-serif}}main{{height:100%;display:grid;grid-template-rows:auto 1fr}}header{{padding:14px 18px;border-bottom:1px solid #252525;background:#111;display:flex;justify-content:space-between;align-items:center}}b{{letter-spacing:.04em}}span{{font-size:12px;color:#999}}model-viewer{{width:100%;height:100%;background:radial-gradient(circle at 50% 45%,#202020,#090909 65%);--poster-color:transparent}}</style></head><body><main><header><b>{title}</b><span>ASHES 3D · drag to rotate · scroll to zoom</span></header><model-viewer src="{model_src}" camera-controls auto-rotate shadow-intensity="1" environment-image="neutral" interaction-prompt="auto"></model-viewer></main></body></html>'''
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "Content-Security-Policy": "frame-ancestors https://admin.shopify.com https://*.myshopify.com; default-src 'self' https://ajax.googleapis.com; script-src 'self' https://ajax.googleapis.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self';"})


@app.get("/api/shopify/model/{product_id}")
def shopify_3d_model(product_id: str) -> StreamingResponse:
    _require_connected()
    asset = _asset(product_id)
    if not asset or not bool(asset.get("storefront_enabled", True)):
        raise HTTPException(status_code=404, detail="This Ashes 3D product is not available.")
    source = media_url(API_BASE_URL, asset.get("model_path"))
    if not source:
        raise HTTPException(status_code=404, detail="Stored model is unavailable.")
    try:
        upstream = requests.get(source, timeout=60, stream=True)
        upstream.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Ashes could not load this stored 3D asset.") from exc

    def body():
        try:
            for chunk in upstream.iter_content(1024 * 256):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return StreamingResponse(
        body(),
        media_type="model/gltf-binary",
        headers={"Cache-Control": "private, max-age=300", "Content-Disposition": "inline"},
    )


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
    # Keep permanent Ashes assets for future reuse, but disable delivery while disconnected.
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
