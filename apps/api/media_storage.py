from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from apps.api.storage import build_storage

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STORAGE_ROOT = DATA_DIR / "storage"


def storage(api_base_url: str):
    return build_storage(STORAGE_ROOT, api_base_url)


def store_media(api_base_url: str, source: Path, key: str, content_type: Optional[str] = None) -> str:
    backend = storage(api_base_url)
    return backend.put_file(source, key, content_type)


def _modal_proxy_key(model_id: str) -> str:
    secret = os.getenv("JWT_SECRET", "ashes-internal-media")
    return hashlib.sha256(f"{secret}:modal-recovery:{model_id}".encode("utf-8")).hexdigest()


def media_url(api_base_url: str, key_or_path: Optional[str]) -> Optional[str]:
    if not key_or_path:
        return None
    value = str(key_or_path)
    if value.startswith("modal-recovery://"):
        model_id = value.split("://", 1)[1].strip()
        if not model_id:
            return None
        return f"{api_base_url.rstrip('/')}/api/internal/modal-recovery/{quote(model_id, safe='')}?key={_modal_proxy_key(model_id)}"
    if value.startswith(("https://", "http://")):
        return value
    return storage(api_base_url).public_url(value)


def delete_media(api_base_url: str, key_or_path: Optional[str]) -> None:
    if not key_or_path:
        return
    value = str(key_or_path)
    if value.startswith(("modal-recovery://", "https://", "http://")):
        return
    storage(api_base_url).delete(value)
