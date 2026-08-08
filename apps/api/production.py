from __future__ import annotations

import os

from fastapi.middleware.cors import CORSMiddleware

from apps.api.mongo_main import app


def _allowed_origins() -> list[str]:
    raw = os.getenv("ASHES_ALLOWED_ORIGINS", "http://localhost:5173")
    values = [value.strip().rstrip("/") for value in raw.split(",") if value.strip()]
    return values or ["http://localhost:5173"]


# mongo_main keeps permissive CORS for local development. Production adds a
# final restrictive middleware layer configured by ASHES_ALLOWED_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/production-health", include_in_schema=False)
def production_health() -> dict:
    return {
        "ok": True,
        "service": "ashes-api",
        "database": "mongodb",
        "mode": "production",
        "allowed_origins": _allowed_origins(),
    }
