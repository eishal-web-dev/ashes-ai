from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import requests

from apps.api.media_storage import store_media
from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import API_BASE_URL

MAX_GLB_BYTES = 120_000_000


def _shop() -> str:
    return (os.getenv("SHOPIFY_SHOP") or "ashes-stack.myshopify.com").strip().lower()


def _safe_shop_key() -> str:
    return re.sub(r"[^a-z0-9.-]+", "-", _shop()).strip("-") or "shopify-store"


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _download_and_store(product_id: str, model_url: str) -> tuple[str, int]:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
    temp_path = Path(handle.name)
    handle.close()
    size = 0
    try:
        with requests.get(model_url, headers=_headers(), timeout=120, stream=True) as response:
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
        key = store_media(
            API_BASE_URL,
            temp_path,
            f"models/shopify/{_safe_shop_key()}/{hashlib.sha256(product_id.encode('utf-8')).hexdigest()[:32]}.glb",
            "model/gltf-binary",
        )
        return key, size
    finally:
        temp_path.unlink(missing_ok=True)


def reconcile_completed_shopify_assets(limit: int = 3) -> dict[str, Any]:
    """Persist legacy completed Modal results that predate permanent Shopify storage.

    Idempotent: products with model_path already stored are skipped. A generation is
    counted only after the GLB exists in Ashes permanent storage.
    """
    migrated = 0
    errors: list[str] = []
    jobs = collection("shopify_generation_jobs").find(
        {
            "shop": _shop(),
            "status": {"$in": ["COMPLETED", "SUCCEEDED"]},
            "$or": [{"model_path": {"$exists": False}}, {"model_path": None}],
            "model_url": {"$exists": True, "$nin": [None, ""]},
        }
    ).sort("created_at", 1).limit(max(1, min(10, limit)))

    for job in jobs:
        task_id = str(job.get("task_id") or "")
        product_id = str(job.get("product_id") or "")
        model_url = str(job.get("model_url") or "")
        if not task_id or not product_id or not model_url:
            continue
        existing = collection("shopify_3d_assets").find_one(
            {"shop": _shop(), "product_id": product_id, "model_path": {"$exists": True, "$ne": None}}
        )
        try:
            if existing:
                model_path = str(existing["model_path"])
                size = int(existing.get("size_bytes") or 0)
            else:
                model_path, size = _download_and_store(product_id, model_url)
                collection("shopify_3d_assets").update_one(
                    {"shop": _shop(), "product_id": product_id},
                    {
                        "$set": {
                            "shop": _shop(),
                            "product_id": product_id,
                            "product_name": job.get("product_name"),
                            "model_path": model_path,
                            "source_task_id": task_id,
                            "size_bytes": size,
                            "storefront_enabled": True,
                            "updated_at": now_iso(),
                        },
                        "$setOnInsert": {"created_at": now_iso()},
                    },
                    upsert=True,
                )
            collection("shopify_generation_jobs").update_one(
                {"task_id": task_id, "shop": _shop()},
                {
                    "$set": {
                        "model_path": model_path,
                        "status": "COMPLETED",
                        "counted": True,
                        "completed_at": job.get("completed_at") or now_iso(),
                        "updated_at": now_iso(),
                    }
                },
            )
            migrated += 1
        except Exception as exc:
            errors.append(f"{task_id}: {str(exc)[:250]}")

    return {"migrated": migrated, "errors": errors}
