from __future__ import annotations

import json
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import app
import apps.api.shopify_generation as generation


def _repair_asset_from_job(product_id: str) -> dict[str, Any] | None:
    existing = generation._asset(product_id)
    if existing:
        return existing

    job = collection("shopify_generation_jobs").find_one(
        {"shop": generation._shop(), "product_id": product_id},
        sort=[("created_at", -1)],
    )
    if not job:
        return None

    task_id = str(job.get("task_id") or "").strip()
    status = str(job.get("status") or "").upper()
    model_url = str(job.get("model_url") or "").strip()

    # If Modal already finished and only storage failed, retry the saved GLB URL
    # directly. This performs zero new GPU work.
    if task_id and status == "STORAGE_FAILED" and model_url and not job.get("model_path"):
        try:
            print(f"ASHES_SHOPIFY_STORAGE_RETRY product={product_id} task={task_id} source=saved_model_url")
            generation._finish_job(
                task_id,
                {
                    "status": "SUCCEEDED",
                    "stage": "RETRYING_STORAGE",
                    "progress": 100,
                    "model_url": model_url,
                },
            )
        except Exception as exc:
            print(f"ASHES_SHOPIFY_STORAGE_RETRY_FAILED product={product_id} task={task_id} error={str(exc)[:500]}")
        job = collection("shopify_generation_jobs").find_one(
            {"shop": generation._shop(), "product_id": product_id},
            sort=[("created_at", -1)],
        ) or job

    status = str(job.get("status") or "").upper()
    model_url = str(job.get("model_url") or "").strip()

    # Older failed jobs may predate durable model_url storage. Ask Modal for the
    # same task once; if it still exists, _finish_job now records model_url before
    # attempting storage so all future retries are durable.
    if task_id and status not in {"FAILED", "CANCELLED", "QUALITY_FAILED"} and not job.get("model_path"):
        try:
            print(f"ASHES_SHOPIFY_RECOVERY_POLL product={product_id} task={task_id} status={status}")
            worker_data = generation._worker_status(task_id)
            generation._finish_job(task_id, worker_data)
        except Exception as exc:
            print(f"ASHES_SHOPIFY_RECOVERY_POLL_FAILED product={product_id} task={task_id} error={str(exc)[:500]}")
        job = collection("shopify_generation_jobs").find_one(
            {"shop": generation._shop(), "product_id": product_id},
            sort=[("created_at", -1)],
        ) or job

    model_path = job.get("model_path")
    if str(job.get("status") or "").upper() != "COMPLETED" or not model_path:
        return None

    doc = {
        "shop": generation._shop(),
        "product_id": product_id,
        "product_name": job.get("product_name"),
        "model_path": model_path,
        "source_task_id": job.get("task_id"),
        "storefront_enabled": True,
        "updated_at": now_iso(),
        "recovered_from_job": True,
    }
    collection("shopify_3d_assets").update_one(
        {"shop": generation._shop(), "product_id": product_id},
        {"$set": doc, "$setOnInsert": {"created_at": now_iso()}},
        upsert=True,
    )
    print(f"ASHES_SHOPIFY_RECOVERED product={product_id} task={task_id}")
    return generation._asset(product_id)


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
