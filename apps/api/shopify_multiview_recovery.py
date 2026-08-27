from __future__ import annotations

import json
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import app
from apps.api.shopify_generation import _asset, _finish_job, _shop, _worker_status


def _repair_asset_from_job(product_id: str) -> dict[str, Any] | None:
    existing = _asset(product_id)
    if existing:
        return existing

    job = collection("shopify_generation_jobs").find_one(
        {"shop": _shop(), "product_id": product_id},
        sort=[("created_at", -1)],
    )
    if not job:
        return None

    task_id = str(job.get("task_id") or "").strip()
    status = str(job.get("status") or "").upper()

    # A browser refresh can happen after Modal finishes but before the polling
    # request persisted the GLB. STORAGE_FAILED is intentionally retryable here:
    # the expensive GPU work already completed, so after storage credentials are
    # repaired we should ask Modal for the same completed result and persist it
    # again instead of launching another generation.
    if task_id and status not in {"FAILED", "CANCELLED", "QUALITY_FAILED"} and not job.get("model_path"):
        try:
            worker_data = _worker_status(task_id)
            _finish_job(task_id, worker_data)
        except Exception:
            pass
        job = collection("shopify_generation_jobs").find_one(
            {"shop": _shop(), "product_id": product_id},
            sort=[("created_at", -1)],
        ) or job

    model_path = job.get("model_path")
    if str(job.get("status") or "").upper() != "COMPLETED" or not model_path:
        return None

    # Self-heal the canonical asset row from the completed job. This makes the
    # twin permanent and prevents a second GPU generation for the same product.
    doc = {
        "shop": _shop(),
        "product_id": product_id,
        "product_name": job.get("product_name"),
        "model_path": model_path,
        "source_task_id": job.get("task_id"),
        "storefront_enabled": True,
        "updated_at": now_iso(),
        "recovered_from_job": True,
    }
    collection("shopify_3d_assets").update_one(
        {"shop": _shop(), "product_id": product_id},
        {"$set": doc, "$setOnInsert": {"created_at": now_iso()}},
        upsert=True,
    )
    return _asset(product_id)


class ShopifyMultiViewRecoveryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method != "GET" or request.url.path != "/api/shopify/products-multiview" or response.status_code != 200:
            return response
        if "application/json" not in response.headers.get("content-type", ""):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return Response(content=body, status_code=response.status_code, headers=dict(response.headers), media_type="application/json")

        changed = False
        for product in payload.get("products") or []:
            product_id = str(product.get("id") or "").strip()
            state = product.get("ashes_3d") or {}
            if not product_id or state.get("ready"):
                continue
            asset = _repair_asset_from_job(product_id)
            if not asset:
                continue
            product["ashes_3d"] = {
                "ready": True,
                "viewer_url": f"/api/shopify/viewer/{product_id}",
                "updated_at": asset.get("updated_at"),
                "published": bool(asset.get("shopify_media_id")),
                "shopify_media_id": asset.get("shopify_media_id"),
                "shopify_media_status": asset.get("shopify_media_status"),
                "published_at": asset.get("shopify_published_at"),
            }
            changed = True

        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        if changed:
            headers["X-Ashes-Recovered-Twin"] = "1"
        return Response(content=encoded, status_code=response.status_code, headers=headers, media_type="application/json")


app.add_middleware(ShopifyMultiViewRecoveryMiddleware)
