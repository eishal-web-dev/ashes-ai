from __future__ import annotations

import uuid
from typing import Any

import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import app
from apps.api.shopify_routes import _access_token, _graphql, _shop
from apps.api.shopify_generation import (
    _asset,
    _detail,
    _headers,
    _json,
    _month_key,
    _plan_snapshot,
    _reconcile_active,
    _timeout,
    _worker_url,
    mark_shopify_connected,
)

MIN_VIEWS = 3
MAX_VIEWS = 3


class ShopifyMultiViewGeneratePayload(BaseModel):
    product_id: str = Field(min_length=1, max_length=200)
    product_name: str = Field(default="Product", max_length=180)
    image_urls: list[str] = Field(min_length=MIN_VIEWS, max_length=MAX_VIEWS)


def _image_urls_from_media(product: dict[str, Any]) -> list[str]:
    media_nodes = ((product.get("media") or {}).get("nodes") or [])
    urls: list[str] = []
    for node in media_nodes:
        image = (node or {}).get("image") or {}
        url = str(image.get("url") or "").strip()
        if url.startswith("https://") and url not in urls:
            urls.append(url)
        if len(urls) >= MAX_VIEWS:
            break
    return urls


@app.get("/api/shopify/products-multiview")
def shopify_products_multiview() -> dict[str, Any]:
    token, token_payload = _access_token()
    data = _graphql(
        token,
        """
        query AshesMultiViewProducts {
          shop { name }
          products(first: 50) {
            nodes {
              id
              title
              handle
              status
              featuredMedia { preview { image { url } } }
              media(first: 12, query: "media_type:IMAGE") {
                nodes {
                  ... on MediaImage { image { url } }
                }
              }
            }
          }
        }
        """,
    )
    root = data.get("data") or {}
    products = ((root.get("products") or {}).get("nodes") or [])
    ids = [str(p.get("id")) for p in products if p.get("id")]
    assets = {
        str(row.get("product_id")): row
        for row in collection("shopify_3d_assets").find(
            {"shop": _shop().lower(), "product_id": {"$in": ids}, "model_path": {"$exists": True, "$ne": None}}
        )
    }
    for product in products:
        urls = _image_urls_from_media(product)
        product["ashes_images"] = urls
        product["ashes_image_count"] = len(urls)
        product_id = str(product.get("id") or "")
        asset = assets.get(product_id)
        product["ashes_3d"] = {
            "ready": bool(asset),
            "viewer_url": f"/api/shopify/viewer/{product_id}" if asset else None,
            "updated_at": asset.get("updated_at") if asset else None,
            "published": bool(asset and asset.get("shopify_media_id")),
            "shopify_media_id": asset.get("shopify_media_id") if asset else None,
            "shopify_media_status": asset.get("shopify_media_status") if asset else None,
            "published_at": asset.get("shopify_published_at") if asset else None,
        }
    return {
        "connected": True,
        "shop": _shop(),
        "store_name": (root.get("shop") or {}).get("name"),
        "token_expires_in": token_payload.get("expires_in"),
        "scopes": token_payload.get("scope"),
        "minimum_images": MIN_VIEWS,
        "products": products,
    }


@app.post("/api/shopify/generate-3d-multiview", status_code=202)
def shopify_start_multiview_generation(payload: ShopifyMultiViewGeneratePayload) -> dict[str, Any]:
    mark_shopify_connected()
    urls = []
    for raw in payload.image_urls:
        url = str(raw).strip()
        if not url.startswith("https://"):
            raise HTTPException(status_code=400, detail="All three Shopify product images must use public HTTPS URLs.")
        if url not in urls:
            urls.append(url)
    if len(urls) != MIN_VIEWS:
        raise HTTPException(status_code=400, detail="Ashes requires 3 different product images for 3D generation.")

    existing = _asset(payload.product_id)
    if existing:
        return {
            "task_id": str(existing.get("source_task_id") or f"stored:{payload.product_id}"),
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
        raise HTTPException(status_code=402, detail=f"{snapshot['current_plan']['name']} generation limit reached. Choose a paid package to generate more 3D products.")

    lock_id = f"starting:{uuid.uuid4().hex}"
    try:
        locked = collection("shopify_generation_state").find_one_and_update(
            {"shop": _shop().lower(), "$or": [{"active_task_id": None}, {"active_task_id": {"$exists": False}}]},
            {"$set": {"shop": _shop().lower(), "active_task_id": lock_id, "updated_at": now_iso()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        locked = None
    if not locked or locked.get("active_task_id") != lock_id:
        raise HTTPException(status_code=409, detail="Another product is already generating. Please wait for it to finish.")

    body = {
        "image_url": urls[0],
        "view_urls": urls,
        "product_name": payload.product_name,
        "reconstruction": {"mode": "multidiffusion", "views": 3},
    }
    try:
        response = requests.post(
            f"{_worker_url()}/v1/product-to-3d",
            json=body,
            headers=_headers(),
            timeout=_timeout(),
        )
        data = _json(response)
        if not response.ok:
            raise HTTPException(status_code=response.status_code, detail=_detail(data, "The TRELLIS worker could not start this multi-image generation."))
        task_id = str(data.get("task_id") or data.get("id") or "").strip()
        if not task_id:
            raise HTTPException(status_code=502, detail="The 3D worker did not return a task ID.")
    except Exception:
        collection("shopify_generation_state").update_one(
            {"shop": _shop().lower(), "active_task_id": lock_id},
            {"$set": {"active_task_id": None, "updated_at": now_iso()}},
        )
        raise

    collection("shopify_generation_jobs").insert_one({
        "task_id": task_id,
        "shop": _shop().lower(),
        "product_id": payload.product_id,
        "product_name": payload.product_name,
        "image_url": urls[0],
        "image_urls": urls,
        "view_count": 3,
        "reconstruction_mode": "TRELLIS_MULTIDIFFUSION",
        "status": str(data.get("status") or "QUEUED").upper(),
        "stage": data.get("stage") or "QUEUED",
        "progress": float(data.get("progress") or 0),
        "counted": False,
        "billing_month": _month_key(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    collection("shopify_generation_state").update_one(
        {"shop": _shop().lower(), "active_task_id": lock_id},
        {"$set": {"active_task_id": task_id, "product_id": payload.product_id, "updated_at": now_iso()}},
    )
    return {
        "task_id": task_id,
        "status": data.get("status") or "QUEUED",
        "stage": data.get("stage") or "QUEUED",
        "reused": False,
        "views": 3,
        "mode": "TRELLIS_MULTIDIFFUSION",
        "plan": snapshot["current_plan"]["key"],
    }
