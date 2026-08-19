from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException
from pydantic import BaseModel

from apps.api.media_storage import media_url
from apps.api.mongo_db import collection, now_iso
from apps.api.mongo_main import API_BASE_URL, app
from apps.api.shopify_routes import _access_token, _graphql, _shop


MAX_MODEL_BYTES = 150 * 1024 * 1024


class Publish3DPayload(BaseModel):
    product_id: str
    product_name: str | None = None


def _asset(product_id: str) -> dict[str, Any]:
    row = collection("shopify_3d_assets").find_one(
        {
            "shop": _shop().lower(),
            "product_id": product_id,
            "model_path": {"$exists": True, "$ne": None},
        }
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generate this product in Ashes before publishing it to Shopify.")
    return row


def _modal_headers() -> dict[str, str]:
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _modal_recovery_url() -> str:
    return os.getenv(
        "ASHES_TRELLIS_RECOVERY_URL",
        "https://ashes-ai-26--ashes-trellis-recovery-web.modal.run",
    ).strip().rstrip("/")


def _asset_source(asset: dict[str, Any]) -> tuple[str, dict[str, str]]:
    model_path = str(asset.get("model_path") or "").strip()
    if model_path.startswith("modal-recovery://"):
        model_id = model_path.split("modal-recovery://", 1)[1].strip()
        if not model_id:
            raise HTTPException(status_code=404, detail="Recovered Ashes model is unavailable.")
        return f"{_modal_recovery_url()}/v1/files/{model_id}/model.glb", _modal_headers()
    source = media_url(API_BASE_URL, model_path)
    if not source:
        raise HTTPException(status_code=404, detail="Stored Ashes model is unavailable.")
    return source, {}


def _download_model(asset: dict[str, Any], product_id: str) -> tuple[Path, int, str]:
    source, headers = _asset_source(asset)
    filename = f"ashes-{hashlib.sha256(product_id.encode('utf-8')).hexdigest()[:20]}.glb"
    target = Path(tempfile.gettempdir()) / filename
    size = 0
    try:
        with requests.get(source, headers=headers, timeout=90, stream=True) as response:
            response.raise_for_status()
            with target.open("wb") as output:
                for chunk in response.iter_content(1024 * 512):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_MODEL_BYTES:
                        raise HTTPException(status_code=413, detail="3D model is too large for Shopify publishing.")
                    output.write(chunk)
    except requests.RequestException as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"Ashes could not load the stored GLB: {str(exc)[:180]}") from exc

    raw_head = target.read_bytes()[:12]
    if size < 20 or raw_head[:4] != b"glTF":
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Stored Ashes model is not a valid GLB.")
    return target, size, filename


def _staged_target(token: str, filename: str, size: int) -> dict[str, Any]:
    mutation = """
    mutation AshesStage3D($input: [StagedUploadInput!]!) {
      stagedUploadsCreate(input: $input) {
        stagedTargets {
          url
          resourceUrl
          parameters { name value }
        }
        userErrors { field message }
      }
    }
    """
    result = _graphql(
        token,
        mutation,
        {
            "input": [
                {
                    "resource": "MODEL_3D",
                    "filename": filename,
                    "mimeType": "model/gltf-binary",
                    "httpMethod": "POST",
                    "fileSize": str(size),
                }
            ]
        },
    )
    payload = ((result.get("data") or {}).get("stagedUploadsCreate") or {})
    errors = payload.get("userErrors") or []
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    targets = payload.get("stagedTargets") or []
    if not targets:
        raise HTTPException(status_code=502, detail="Shopify did not return a staged upload target.")
    return targets[0]


def _upload_to_staged_target(target: dict[str, Any], path: Path, filename: str) -> str:
    upload_url = str(target.get("url") or "")
    resource_url = str(target.get("resourceUrl") or "")
    if not upload_url or not resource_url:
        raise HTTPException(status_code=502, detail="Shopify returned an incomplete staged upload target.")
    fields = {str(item.get("name")): str(item.get("value")) for item in (target.get("parameters") or [])}
    try:
        with path.open("rb") as handle:
            response = requests.post(
                upload_url,
                data=fields,
                files={"file": (filename, handle, "model/gltf-binary")},
                timeout=180,
            )
        if not response.ok:
            raise HTTPException(
                status_code=502,
                detail=f"Shopify staged GLB upload failed ({response.status_code}): {response.text[:250]}",
            )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Shopify staged GLB upload failed: {str(exc)[:180]}") from exc
    return resource_url


def _attach_model(token: str, product_id: str, product_name: str, resource_url: str) -> dict[str, Any]:
    mutation = """
    mutation AshesPublish3D($product: ProductUpdateInput!, $media: [CreateMediaInput!]) {
      productUpdate(product: $product, media: $media) {
        product {
          id
          title
          media(first: 50) {
            nodes { id alt mediaContentType status }
          }
        }
        userErrors { field message }
      }
    }
    """
    result = _graphql(
        token,
        mutation,
        {
            "product": {"id": product_id},
            "media": [
                {
                    "originalSource": resource_url,
                    "mediaContentType": "MODEL_3D",
                    "alt": f"Ashes 3D · {product_name}"[:500],
                }
            ],
        },
    )
    payload = ((result.get("data") or {}).get("productUpdate") or {})
    errors = payload.get("userErrors") or []
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    product = payload.get("product") or {}
    media_nodes = ((product.get("media") or {}).get("nodes") or [])
    candidates = [m for m in media_nodes if m.get("mediaContentType") == "MODEL_3D"]
    media = candidates[-1] if candidates else {}
    return {
        "product": product,
        "media_id": media.get("id"),
        "media_status": media.get("status") or "PROCESSING",
    }


@app.post("/api/shopify/publish-3d")
def publish_shopify_3d(payload: Publish3DPayload) -> dict[str, Any]:
    product_id = payload.product_id.strip()
    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")
    asset = _asset(product_id)
    if asset.get("shopify_media_id"):
        return {
            "ok": True,
            "reused": True,
            "product_id": product_id,
            "media_id": asset.get("shopify_media_id"),
            "status": asset.get("shopify_media_status") or "PROCESSING",
            "published_at": asset.get("shopify_published_at"),
        }

    product_name = (payload.product_name or asset.get("product_name") or "Product").strip()[:200]
    token, _ = _access_token()
    path, size, filename = _download_model(asset, product_id)
    try:
        target = _staged_target(token, filename, size)
        resource_url = _upload_to_staged_target(target, path, filename)
        published = _attach_model(token, product_id, product_name, resource_url)
    finally:
        path.unlink(missing_ok=True)

    now = now_iso()
    collection("shopify_3d_assets").update_one(
        {"shop": _shop().lower(), "product_id": product_id},
        {
            "$set": {
                "shopify_media_id": published.get("media_id"),
                "shopify_media_status": published.get("media_status") or "PROCESSING",
                "shopify_published_at": now,
                "shopify_resource_url": resource_url,
                "updated_at": now,
            }
        },
    )
    return {
        "ok": True,
        "reused": False,
        "product_id": product_id,
        "media_id": published.get("media_id"),
        "status": published.get("media_status") or "PROCESSING",
        "published_at": now,
    }


@app.get("/api/shopify/publish-status")
def shopify_publish_status(product_id: str) -> dict[str, Any]:
    asset = _asset(product_id)
    return {
        "product_id": product_id,
        "published": bool(asset.get("shopify_media_id")),
        "media_id": asset.get("shopify_media_id"),
        "status": asset.get("shopify_media_status"),
        "published_at": asset.get("shopify_published_at"),
    }
