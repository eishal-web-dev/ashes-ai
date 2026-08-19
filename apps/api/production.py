from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Load project-local environment before importing Mongo/storage modules.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(override=False)

# Import storage-aware Mongo routes only after environment is loaded.
from apps.api.storage_main import app
import apps.api.storage_menu_import  # noqa: F401
import apps.api.billing  # noqa: F401
import apps.api.admin  # noqa: F401
import apps.api.manual_payments  # noqa: F401
import apps.api.retail_products  # noqa: F401
import apps.api.table_qr_routes  # noqa: F401
import apps.api.order_operations  # noqa: F401
import apps.api.commerce_sources  # noqa: F401
import apps.api.prototype  # noqa: F401
import apps.api.prototype_generate_3d  # noqa: F401
import apps.api.shopify_routes  # noqa: F401
import apps.api.shopify_generation  # noqa: F401
from apps.api.mongo_db import database


def _allowed_origins() -> list[str]:
    raw = os.getenv("ASHES_ALLOWED_ORIGINS", "http://localhost:5173")
    values = [value.strip().rstrip("/") for value in raw.split(",") if value.strip()]
    return values or ["http://localhost:5173"]


def _storage_info() -> dict:
    provider = os.getenv("ASHES_STORAGE_PROVIDER", "local").strip().lower()
    info = {"provider": provider, "configured": True}
    if provider in {"s3", "r2", "supabase-s3"}:
        required = ["ASHES_S3_BUCKET", "ASHES_S3_ACCESS_KEY_ID", "ASHES_S3_SECRET_ACCESS_KEY"]
        missing = [name for name in required if not os.getenv(name)]
        info["configured"] = not missing
        info["missing"] = missing
        info["public_base_url"] = os.getenv("ASHES_S3_PUBLIC_BASE_URL")
    return info


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/production-health", include_in_schema=False)
def production_health() -> dict:
    mongo_ok = False
    mongo_error = None
    try:
        database().command("ping")
        mongo_ok = True
    except Exception as exc:
        mongo_error = str(exc)[:300]

    storage_info = _storage_info()
    overall = mongo_ok and bool(storage_info.get("configured"))
    return {
        "ok": overall,
        "service": "ashes-api",
        "database": {"provider": "mongodb", "ok": mongo_ok, "error": mongo_error},
        "storage": storage_info,
        "mode": "production",
        "allowed_origins": _allowed_origins(),
    }
