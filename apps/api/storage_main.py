from __future__ import annotations

import mimetypes
import os
import tempfile
import threading
from pathlib import Path

import qrcode
from fastapi import Depends, File, HTTPException, UploadFile

from apps.api.media_storage import delete_media, media_url, store_media
from apps.api.mongo_main import (
    API_BASE_URL,
    PUBLIC_BASE_URL,
    app,
    auth_user,
    business_out,
    mongo_create_product,
    mongo_delete_product,
    mongo_get_product,
    mongo_update_product,
    owned_business,
    product_out,
    update_business,
)
from apps.api.services.three_d import generate_3d
from apps.api.subscriptions import assert_capacity, increment_usage


def _tmp_path(suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    path = Path(handle.name)
    handle.close()
    return path


def _media_key(kind: str, owner_id: str, filename: str) -> str:
    return f"{kind}/{owner_id}/{Path(filename).name}"


def _content_type(filename: str, fallback: str) -> str:
    return mimetypes.guess_type(filename)[0] or fallback


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


def persist_product_media(product_id: str, business_id: str, image_path: Path | None = None, model_path: Path | None = None, qr_path: Path | None = None) -> dict | None:
    updates: dict[str, str] = {}
    if image_path and image_path.exists():
        updates["image_path"] = store_media(API_BASE_URL, image_path, _media_key("products", business_id, image_path.name), _content_type(image_path.name, "image/jpeg"))
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


def _run_storage_generation_job(product_id: str, business_id: str, image_path: Path) -> None:
    mongo_update_product(product_id, business_id, {"status": "processing", "error_message": None})
    try:
        model_path = generate_3d(product_id, image_path)
        if not model_path:
            mongo_update_product(product_id, business_id, {"status": "awaiting-generator", "error_message": "No 3D generator configured."})
            return
        model_key = store_media(API_BASE_URL, model_path, _media_key("models", business_id, f"{product_id}.glb"), "model/gltf-binary")
        product = mongo_get_product(product_id)
        old_model = product.get("model_path") if product else None
        mongo_update_product(product_id, business_id, {"model_path": model_key, "status": "ready", "error_message": None})
        if old_model and old_model != model_key:
            delete_media(API_BASE_URL, old_model)
    except Exception as exc:
        mongo_update_product(product_id, business_id, {"status": "failed", "error_message": str(exc)[:600]})
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass


def queue_storage_3d_generation(product_id: str, business_id: str, image_path: Path) -> None:
    threading.Thread(target=_run_storage_generation_job, args=(product_id, business_id, image_path), daemon=True, name=f"ashes-storage-3d-{product_id[:8]}").start()


@app.post("/api/storage/businesses/{business_slug}/logo")
async def storage_upload_logo(business_slug: str, logo: UploadFile = File(...), user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    if not logo.content_type or not logo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Logo must be an image")
    ext = Path(logo.filename or "logo.png").suffix.lower() or ".png"
    temp_path = _tmp_path(ext)
    try:
        temp_path.write_bytes(await logo.read())
        old_key = business.get("logo_path")
        key = store_media(API_BASE_URL, temp_path, _media_key("logos", business["id"], f"logo{ext}"), logo.content_type)
        updated = update_business(business["id"], {"logo_path": key})
        if old_key and old_key != key:
            delete_media(API_BASE_URL, old_key)
        return storage_business_out(updated)
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/storage/businesses/{business_slug}/products")
async def storage_create_product(
    business_slug: str,
    name: str,
    price: float,
    category: str = "Main",
    calories: str = "",
    protein: str = "",
    carbs: str = "",
    fat: str = "",
    tags: str = "",
    image: UploadFile = File(...),
    user: dict = Depends(auth_user),
):
    business = owned_business(user["id"], business_slug)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image")
    try:
        assert_capacity(business["id"], "products")
        assert_capacity(business["id"], "ai_generations")
    except ValueError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    import uuid
    product_id = str(uuid.uuid4())
    ext = Path(image.filename or "product.jpg").suffix.lower() or ".jpg"
    temp_image = _tmp_path(ext)
    temp_qr = _tmp_path(".png")
    generation_started = False
    try:
        temp_image.write_bytes(await image.read())
        qrcode.make(f"{PUBLIC_BASE_URL}/?product={product_id}").save(temp_qr)
        image_key = store_media(API_BASE_URL, temp_image, _media_key("products", business["id"], f"{product_id}{ext}"), image.content_type)
        qr_key = store_media(API_BASE_URL, temp_qr, _media_key("qr", business["id"], f"{product_id}.png"), "image/png")
        row = mongo_create_product({
            "id": product_id,
            "business_id": business["id"],
            "name": name,
            "category": category,
            "price": price,
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "tags": tags,
            "image_path": image_key,
            "status": "queued",
            "qr_code": qr_key,
            "is_published": False,
        })
        queue_storage_3d_generation(product_id, business["id"], temp_image)
        increment_usage(business["id"], "ai_generations")
        generation_started = True
        return storage_product_out(row)
    finally:
        temp_qr.unlink(missing_ok=True)
        if not generation_started:
            temp_image.unlink(missing_ok=True)


@app.post("/api/storage/businesses/{business_slug}/products/{product_id}/image")
async def storage_attach_product_image(
    business_slug: str,
    product_id: str,
    image: UploadFile = File(...),
    user: dict = Depends(auth_user),
):
    business = owned_business(user["id"], business_slug)
    product = mongo_get_product(product_id)
    if not product or product.get("business_id") != business["id"]:
        raise HTTPException(status_code=404, detail="Product not found")
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image")
    try:
        assert_capacity(business["id"], "ai_generations")
    except ValueError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    ext = Path(image.filename or "product.jpg").suffix.lower() or ".jpg"
    temp_path = _tmp_path(ext)
    generation_started = False
    try:
        temp_path.write_bytes(await image.read())
        old_image = product.get("image_path")
        old_model = product.get("model_path")
        key = store_media(API_BASE_URL, temp_path, _media_key("products", business["id"], f"{product_id}{ext}"), image.content_type)
        row = mongo_update_product(product_id, business["id"], {"image_path": key, "model_path": None, "status": "queued", "error_message": None})
        if old_image and old_image != key:
            delete_media(API_BASE_URL, old_image)
        if old_model:
            delete_media(API_BASE_URL, old_model)
        queue_storage_3d_generation(product_id, business["id"], temp_path)
        increment_usage(business["id"], "ai_generations")
        generation_started = True
        return storage_product_out(row)
    finally:
        if not generation_started:
            temp_path.unlink(missing_ok=True)


@app.delete("/api/storage/businesses/{business_slug}/products/{product_id}")
def storage_delete_product(business_slug: str, product_id: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    product = mongo_get_product(product_id)
    if not product or product.get("business_id") != business["id"]:
        raise HTTPException(status_code=404, detail="Product not found")
    remove_product_media(product)
    deleted = mongo_delete_product(product_id, business["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.get("/storage-health", include_in_schema=False)
def storage_health() -> dict:
    provider = os.getenv("ASHES_STORAGE_PROVIDER", "local").strip().lower()
    required = []
    if provider in {"s3", "r2", "supabase-s3"}:
        for key in ("ASHES_S3_BUCKET", "ASHES_S3_ACCESS_KEY_ID", "ASHES_S3_SECRET_ACCESS_KEY"):
            if not os.getenv(key):
                required.append(key)
    return {"ok": not required, "database": "mongodb", "storage_provider": provider, "missing_storage_env": required, "public_base_url": PUBLIC_BASE_URL}
