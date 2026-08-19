from __future__ import annotations

import hashlib
import hmac
import os
import re

import requests
from fastapi import HTTPException, Query
from fastapi.responses import StreamingResponse

from apps.api.mongo_main import app


def _expected(model_id: str) -> str:
    secret = os.getenv("JWT_SECRET", "ashes-internal-media")
    return hashlib.sha256(f"{secret}:modal-recovery:{model_id}".encode("utf-8")).hexdigest()


def _headers() -> dict[str, str]:
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _recovery_url() -> str:
    return os.getenv(
        "ASHES_TRELLIS_RECOVERY_URL",
        "https://ashes-ai-26--ashes-trellis-recovery-web.modal.run",
    ).strip().rstrip("/")


@app.get("/api/internal/modal-recovery/{model_id}", include_in_schema=False)
def modal_recovery_model(model_id: str, key: str = Query(...)) -> StreamingResponse:
    if not re.fullmatch(r"[0-9a-fA-F]{16,64}", model_id):
        raise HTTPException(status_code=400, detail="Invalid model id")
    if not hmac.compare_digest(key, _expected(model_id)):
        raise HTTPException(status_code=403, detail="Invalid media token")

    try:
        upstream = requests.get(
            f"{_recovery_url()}/v1/files/{model_id}/model.glb",
            headers=_headers(),
            timeout=60,
            stream=True,
        )
        upstream.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Stored Modal model is unavailable") from exc

    def body():
        try:
            for chunk in upstream.iter_content(1024 * 256):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return StreamingResponse(
        body(),
        media_type="model/gltf-binary",
        headers={"Cache-Control": "private, max-age=300", "Content-Disposition": "inline"},
    )
