from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import File, HTTPException, UploadFile

from apps.api.media_storage import delete_media, media_url, store_media
from apps.api.mongo_main import (
    API_BASE_URL,
    PUBLIC_BASE_URL,
    app,
    business_out,
    mongo_get_product,
    mongo_update_product,
    owned_business,
    product_out,
    queue_3d_generation,
    update_business,
)


def _tmp_file(upload: UploadFile, suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    path = Path(handle.name)
    handle.close()
    return path


def _media_key(kind: str, owner_id: str, filename: str) -> str:
    safe = Path(filename).name
    return f"{kind}/{owner_id}/{safe}"


def storage_business_out(row: dict) -> dict:
    data = business_out(row)
    data["logo_url"] = media_url(API_BASE_URL, row.get("logo_path")) if row.get("logo_path") else None
    return data


def storage_product_out(row: dict) -> dict:
    data = product_out(row)
    data["image_url"] = media_url(API_BASE_URL, row.get("image_path")) if row.get("image_path") else None
    data["model_url"] = media_url(API_BASE_URL, row.get("model_path")) if row.get("model_path") else None
    data["qr_url"] = media_url(API_BASE_URL, row.get("qr_code")) if row.get("qr_code") else None
    return data


@app.post("/api/storage/businesses/{business_slug}/logo")
async def storage_upload_logo(business_slug: str, logo: UploadFile = File(...), user: dict = None):
    # This route is intentionally a compatibility helper for deployment validation.
    # The authenticated primary logo route remains in mongo_main until the full route
    # swap is completed after runtime testing.
    raise HTTPException(status_code=501, detail="Use the primary business logo endpoint until storage cutover is enabled")


def persist_product_media(product_id: str, business_id: str, image_path: Path | None = None, model_path: Path | None = None, qr_path: Path | None = None) -> dict | None:
    updates: dict[str, str] = {}
    if image_path and image_path.exists():
        updates["image_path"] = store_media(API_BASE_URL, image_path, _media_key("products", business_id, image_path.name), "image/jpeg")
    if model_path and model_path.exists():
        updates["model_path"] = store_media(API_BASE_URL, model_path, _media_key("models", business_id, model_path.name), "model/gltf-binary")
    if qr_path and qr_path.exists():
        updates["qr_code"] = store_media(API_BASE_URL, qr_path, _media_key("qr", business_id, qr_path.name), "image/png")
    if updates:
        return mongo_update_product(product_id, business_id, updates)
    return mongo_get_product(product_id)


def remove_product_media(product: dict) -> None:
    for field in ("image_path", "model_path", "qr_code"):
        delete_media(API_BASE_URL, product.get(field))


@app.get("/storage-health", include_in_schema=False)
def storage_health() -> dict:
    provider = os.getenv("ASHES_STORAGE_PROVIDER", "local").strip().lower()
    required = []
    if provider in {"s3", "r2", "supabase-s3"}:
        for key in (
            "ASHES_S3_BUCKET",
            "ASHES_S3_ACCESS_KEY_ID",
            "ASHES_S3_SECRET_ACCESS_KEY",
        ):
            if not os.getenv(key):
                required.append(key)
    return {
        "ok": not required,
        "database": "mongodb",
        "storage_provider": provider,
        "missing_storage_env": required,
        "public_base_url": PUBLIC_BASE_URL,
    }
