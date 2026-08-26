from __future__ import annotations

import base64
import hashlib
import hmac
import os

from fastapi import HTTPException, Request

from apps.api.media_storage import delete_media
from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import API_BASE_URL, app


def _verify(raw_body: bytes, signature: str) -> None:
    secret = (os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("ASHES_SHOPIFY_CLIENT_SECRET") or "").strip()
    if not secret or not signature:
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")


def _shop_from_request(request: Request, payload: dict) -> str:
    return str(
        request.headers.get("x-shopify-shop-domain")
        or payload.get("shop_domain")
        or ""
    ).strip().lower()


def _delete_shop_data(shop: str) -> None:
    if not shop:
        return
    assets = list(collection("shopify_3d_assets").find({"shop": shop}))
    for asset in assets:
        try:
            delete_media(API_BASE_URL, asset.get("model_path"))
        except Exception:
            # Continue deleting database references even if a storage provider is temporarily unavailable.
            pass

    for name in (
        "shopify_3d_assets",
        "shopify_generation_jobs",
        "shopify_generation_state",
        "shopify_storefront_services",
        "shopify_accounts",
    ):
        collection(name).delete_many({"shop": shop})


@app.post("/api/shopify/webhooks/compliance", include_in_schema=False)
async def shopify_compliance_webhook(request: Request) -> dict[str, bool]:
    raw = await request.body()
    _verify(raw, request.headers.get("x-shopify-hmac-sha256", ""))
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    topic = request.headers.get("x-shopify-topic", "").strip().lower()
    shop = _shop_from_request(request, payload)

    # Ashes requests only product scopes and does not persist customer/order personal data.
    # We still acknowledge customer data-access/redaction requests as required for all public apps.
    if topic in {"customers/data_request", "customers/redact"}:
        collection("shopify_compliance_events").insert_one({
            "topic": topic,
            "shop": shop,
            "received_at": now_iso(),
            "status": "acknowledged_no_customer_data_stored",
        })
        return {"ok": True}

    if topic == "shop/redact":
        _delete_shop_data(shop)
        return {"ok": True}

    raise HTTPException(status_code=400, detail="Unsupported Shopify compliance topic")
