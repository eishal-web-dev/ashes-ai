from __future__ import annotations

import os
from pathlib import Path

import modal

APP_NAME = "ashes-trellis-recovery"
MODEL_ROOT = "/models"

app = modal.App(APP_NAME)
model_volume = modal.Volume.from_name("ashes-trellis-models", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.10").pip_install("fastapi[standard]")

_deploy_worker_token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
web_secrets = (
    [modal.Secret.from_dict({"ASHES_TRELLIS_WORKER_TOKEN": _deploy_worker_token})]
    if _deploy_worker_token
    else []
)


@app.function(
    image=image,
    volumes={MODEL_ROOT: model_volume},
    secrets=web_secrets,
    timeout=120,
    min_containers=0,
    max_containers=1,
)
@modal.asgi_app()
def web():
    import fastapi
    from fastapi import Header, HTTPException
    from fastapi.responses import FileResponse

    api = fastapi.FastAPI(title="Ashes TRELLIS Recovery Index")

    def authorize(authorization: str | None) -> None:
        token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
        if token and authorization != f"Bearer {token}":
            raise HTTPException(401, "Invalid worker token")

    @api.get("/health")
    def health():
        return {"status": "ok", "service": "ashes-trellis-recovery"}

    @api.get("/v1/recovery/models")
    def models(authorization: str | None = Header(default=None)):
        authorize(authorization)
        try:
            model_volume.reload()
        except Exception:
            pass
        rows = []
        for path in Path(MODEL_ROOT).glob("*.glb"):
            try:
                stat = path.stat()
            except OSError:
                continue
            rows.append({
                "model_id": path.stem,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "model_path": f"/v1/files/{path.stem}/model.glb",
            })
        rows.sort(key=lambda row: row["modified_at"], reverse=True)
        return {"count": len(rows), "models": rows[:10]}

    @api.get("/v1/files/{model_id}/model.glb")
    def model_file(model_id: str, authorization: str | None = Header(default=None)):
        authorize(authorization)
        if not model_id or any(ch not in "0123456789abcdef" for ch in model_id.lower()):
            raise HTTPException(400, "Invalid model id")
        try:
            model_volume.reload()
        except Exception:
            pass
        path = Path(MODEL_ROOT) / f"{model_id}.glb"
        if not path.exists():
            raise HTTPException(404, "Model not found")
        return FileResponse(path, media_type="model/gltf-binary", filename="model.glb")

    return api
