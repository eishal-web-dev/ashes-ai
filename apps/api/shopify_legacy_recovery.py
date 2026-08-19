from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import requests

from apps.api.media_storage import store_media
from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import API_BASE_URL

TARGET_HANDLE = "the-inventory-not-tracked-snowboard"


def _shop() -> str:
    return (os.getenv("SHOPIFY_SHOP") or "ashes-stack.myshopify.com").strip().lower()


def _worker_url() -> str:
    return os.getenv("ASHES_TRELLIS_WORKER_URL", "").strip().rstrip("/")


def _headers() -> dict[str, str]:
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def recover_first_legacy_shopify_asset() -> dict:
    # Only for the very first demo model created before Shopify jobs were tracked.
    if collection("shopify_3d_assets").count_documents({"shop": _shop()}) > 0:
        return {"recovered": 0, "reason": "assets already exist"}
    if collection("shopify_generation_jobs").count_documents({"shop": _shop(), "counted": True}) > 0:
        return {"recovered": 0, "reason": "usage already recorded"}

    from apps.api.shopify_routes import _access_token, _graphql

    token, _ = _access_token()
    data = _graphql(token, """
      query LegacyRecoveryProduct {
        products(first: 50) { nodes { id title handle } }
      }
    """)
    products = (((data.get("data") or {}).get("products") or {}).get("nodes") or [])
    product = next((p for p in products if p.get("handle") == TARGET_HANDLE), None)
    if not product:
        return {"recovered": 0, "reason": "target product not found"}

    response = requests.get(f"{_worker_url()}/v1/recovery/models", headers=_headers(), timeout=30)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models") or []
    if int(payload.get("count") or 0) != 1 or len(models) != 1:
        return {"recovered": 0, "reason": f"expected exactly one legacy model, found {payload.get('count')}"}

    model = models[0]
    model_url = str(model.get("model_url") or "")
    if not model_url:
        return {"recovered": 0, "reason": "legacy model URL missing"}

    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
    temp = Path(handle.name)
    handle.close()
    try:
        with requests.get(model_url, headers=_headers(), timeout=120, stream=True) as r:
            r.raise_for_status()
            with temp.open("wb") as out:
                for chunk in r.iter_content(1024 * 256):
                    if chunk:
                        out.write(chunk)
        raw = temp.read_bytes()[:12]
        if len(raw) < 12 or raw[:4] != b"glTF":
            raise RuntimeError("legacy model is not valid GLB")
        product_id = str(product["id"])
        key = store_media(
            API_BASE_URL,
            temp,
            f"models/shopify/{_shop().replace('.','-')}/{hashlib.sha256(product_id.encode()).hexdigest()[:32]}.glb",
            "model/gltf-binary",
        )
        collection("shopify_3d_assets").update_one(
            {"shop": _shop(), "product_id": product_id},
            {"$set": {
                "shop": _shop(), "product_id": product_id, "product_name": product.get("title"),
                "model_path": key, "source_task_id": "legacy-modal-recovery",
                "size_bytes": temp.stat().st_size, "storefront_enabled": True, "updated_at": now_iso(),
            }, "$setOnInsert": {"created_at": now_iso()}}, upsert=True,
        )
        collection("shopify_generation_jobs").insert_one({
            "task_id": "legacy-modal-recovery", "shop": _shop(), "product_id": product_id,
            "product_name": product.get("title"), "status": "COMPLETED", "counted": True,
            "model_path": key, "billing_month": now_iso()[:7], "created_at": now_iso(),
            "completed_at": now_iso(), "updated_at": now_iso(),
        })
        return {"recovered": 1, "product": TARGET_HANDLE, "size_bytes": temp.stat().st_size}
    finally:
        temp.unlink(missing_ok=True)
