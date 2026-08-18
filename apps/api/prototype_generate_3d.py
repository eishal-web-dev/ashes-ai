from __future__ import annotations

import os
import re
from typing import Any

import requests
from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.mongo_main import app

MAX_ID_LENGTH = 160


class Generate3DPayload(BaseModel):
    product_name: str = Field(default="Product", max_length=180)
    image_url: str | None = None
    view_urls: list[str] | None = None


def _worker_url() -> str:
    value = os.getenv("ASHES_TRELLIS_WORKER_URL", "").strip().rstrip("/")
    if not value:
        raise HTTPException(
            status_code=503,
            detail="The Ashes TRELLIS GPU worker is offline. Configure ASHES_TRELLIS_WORKER_URL before generating real product geometry.",
        )
    return value


def _headers(content_type: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _request_timeout() -> int:
    try:
        return min(60, max(10, int(os.getenv("ASHES_3D_HTTP_TIMEOUT", "30"))))
    except ValueError:
        return 30


def _json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else {"detail": payload}
    except ValueError:
        return {"detail": response.text[:500]}


def _detail(payload: dict[str, Any], fallback: str) -> str:
    value = payload.get("detail") or payload.get("message") or payload.get("error")
    if isinstance(value, str) and value.strip():
        return value
    if value is not None:
        return str(value)[:500]
    return fallback


@app.get("/api/prototype/generate-3d")
def generation_status(id: str = Query(..., min_length=1, max_length=MAX_ID_LENGTH)) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", id):
        raise HTTPException(status_code=400, detail="Invalid generation task.")

    try:
        response = requests.get(
            f"{_worker_url()}/v1/product-to-3d/{id}",
            headers=_headers(),
            timeout=_request_timeout(),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"TRELLIS worker request failed: {str(exc)[:180]}") from exc

    data = _json(response)
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=_detail(data, "The TRELLIS worker could not retrieve this generation."))

    return {
        "task_id": id,
        "status": str(data.get("status") or "PROCESSING").upper(),
        "stage": data.get("stage"),
        "progress": float(data.get("progress") or 0),
        "views": (data.get("views") or [])[:4] if isinstance(data.get("views"), list) else [],
        "model_url": data.get("model_url") or (data.get("output") or {}).get("glb_url"),
        "thumbnail_url": data.get("thumbnail_url") or (data.get("output") or {}).get("thumbnail_url"),
        "error": data.get("error"),
    }


@app.post("/api/prototype/generate-3d", status_code=202)
def start_generation(payload: Generate3DPayload) -> dict[str, Any]:
    image_url = (payload.image_url or "").strip()
    if not image_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Provide a public HTTPS product image URL.")

    view_urls = []
    for value in payload.view_urls or []:
        value = str(value).strip()
        if value.startswith("https://") and value not in view_urls:
            view_urls.append(value)
    view_urls = view_urls[:4]

    body: dict[str, Any] = {
        "image_url": image_url,
        "product_name": payload.product_name or "Product",
    }
    if view_urls:
        body["view_urls"] = view_urls

    try:
        response = requests.post(
            f"{_worker_url()}/v1/product-to-3d",
            json=body,
            headers=_headers("application/json"),
            timeout=_request_timeout(),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"TRELLIS worker request failed: {str(exc)[:180]}") from exc

    data = _json(response)
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=_detail(data, "The TRELLIS worker could not start this generation."))

    task_id = str(data.get("task_id") or data.get("id") or "").strip()
    if not task_id:
        raise HTTPException(status_code=502, detail="The TRELLIS worker did not return a task ID.")

    return {
        "task_id": task_id,
        "status": data.get("status") or "QUEUED",
        "stage": data.get("stage") or "QUEUED",
        "views_expected": len(view_urls) or 1,
    }
