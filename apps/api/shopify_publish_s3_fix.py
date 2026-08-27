from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

import apps.api.shopify_publish as publish
from apps.api.storage import S3Storage


def _download_model_from_storage(asset: dict[str, Any], product_id: str) -> tuple[Path, int, str]:
    model_path = str(asset.get("model_path") or "").strip().lstrip("/")
    provider = os.getenv("ASHES_STORAGE_PROVIDER", "local").strip().lower()

    # For S3/R2/Supabase-S3, the object URL is private and must be fetched with
    # authenticated S3 credentials rather than a raw public HTTP GET.
    if provider in {"s3", "r2", "supabase-s3"} and model_path and not model_path.startswith("modal-recovery://"):
        filename = f"ashes-{hashlib.sha256(product_id.encode('utf-8')).hexdigest()[:20]}.glb"
        target = Path(tempfile.gettempdir()) / filename
        size = 0
        storage = S3Storage()
        try:
            response = storage.client.get_object(Bucket=storage.bucket, Key=model_path)
            body = response["Body"]
            with target.open("wb") as output:
                while True:
                    chunk = body.read(1024 * 512)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > publish.MAX_MODEL_BYTES:
                        raise HTTPException(status_code=413, detail="3D model is too large for Shopify publishing.")
                    output.write(chunk)
            try:
                body.close()
            except Exception:
                pass
        except HTTPException:
            target.unlink(missing_ok=True)
            raise
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=502, detail=f"Ashes could not read the stored GLB from S3: {str(exc)[:220]}") from exc

        raw_head = target.read_bytes()[:12]
        if size < 20 or raw_head[:4] != b"glTF":
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Stored Ashes model is not a valid GLB.")
        return target, size, filename

    return _ORIGINAL_DOWNLOAD(asset, product_id)


_ORIGINAL_DOWNLOAD = publish._download_model
publish._download_model = _download_model_from_storage
