from __future__ import annotations

from pathlib import Path
from typing import Optional

from apps.api.storage import build_storage

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STORAGE_ROOT = DATA_DIR / "storage"


def storage(api_base_url: str):
    return build_storage(STORAGE_ROOT, api_base_url)


def store_media(api_base_url: str, source: Path, key: str, content_type: Optional[str] = None) -> str:
    backend = storage(api_base_url)
    return backend.put_file(source, key, content_type)


def media_url(api_base_url: str, key_or_path: Optional[str]) -> Optional[str]:
    if not key_or_path:
        return None
    return storage(api_base_url).public_url(key_or_path)


def delete_media(api_base_url: str, key_or_path: Optional[str]) -> None:
    if not key_or_path:
        return
    storage(api_base_url).delete(key_or_path)
