from __future__ import annotations

import os
from urllib.parse import quote

import requests
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from apps.api.media_storage import media_url
from apps.api.mongo_db import collection
from apps.api.mongo_main import API_BASE_URL, app


def _shop() -> str:
    return (os.getenv("SHOPIFY_SHOP") or "ashes-stack.myshopify.com").strip().lower()


def _require_connected() -> None:
    account = collection("shopify_accounts").find_one({"shop": _shop()}) or {}
    if account and not bool(account.get("connected", True)):
        raise HTTPException(status_code=403, detail="Ashes is disconnected from this Shopify store.")


def _asset(product_id: str):
    return collection("shopify_3d_assets").find_one(
        {
            "shop": _shop(),
            "product_id": product_id,
            "model_path": {"$exists": True, "$ne": None},
        }
    )


def _modal_headers() -> dict[str, str]:
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _modal_recovery_url() -> str:
    return os.getenv(
        "ASHES_TRELLIS_RECOVERY_URL",
        "https://ashes-ai-26--ashes-trellis-recovery-web.modal.run",
    ).strip().rstrip("/")


@app.get("/api/shopify/viewer/{product_id:path}", response_class=HTMLResponse)
def shopify_3d_viewer_path(product_id: str) -> HTMLResponse:
    _require_connected()
    asset = _asset(product_id)
    if not asset or not bool(asset.get("storefront_enabled", True)):
        raise HTTPException(status_code=404, detail="This Ashes 3D product is not available.")

    title = str(asset.get("product_name") or "Product").replace("<", "&lt;").replace(">", "&gt;")
    encoded_product_id = quote(product_id, safe="")
    model_src = f"/api/shopify/model/{encoded_product_id}"
    html = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Ashes 3D</title><script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.1.0/model-viewer.min.js"></script><style>html,body{{margin:0;width:100%;height:100%;background:#090909;color:#fff;font-family:Inter,system-ui,sans-serif}}main{{height:100%;display:grid;grid-template-rows:auto 1fr}}header{{padding:14px 18px;border-bottom:1px solid #252525;background:#111;display:flex;justify-content:space-between;align-items:center}}b{{letter-spacing:.04em}}span{{font-size:12px;color:#999}}model-viewer{{width:100%;height:100%;background:radial-gradient(circle at 50% 45%,#202020,#090909 65%);--poster-color:transparent}}</style></head><body><main><header><b>{title}</b><span>ASHES 3D · drag to rotate · scroll to zoom</span></header><model-viewer src="{model_src}" camera-controls auto-rotate shadow-intensity="1" environment-image="neutral" interaction-prompt="auto"></model-viewer></main></body></html>'''
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "frame-ancestors https://admin.shopify.com https://*.myshopify.com; default-src 'self' https://ajax.googleapis.com; script-src 'self' https://ajax.googleapis.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self';",
        },
    )


@app.get("/api/shopify/model/{product_id:path}")
def shopify_3d_model_path(product_id: str) -> StreamingResponse:
    _require_connected()
    asset = _asset(product_id)
    if not asset or not bool(asset.get("storefront_enabled", True)):
        raise HTTPException(status_code=404, detail="This Ashes 3D product is not available.")

    model_path = str(asset.get("model_path") or "")
    headers: dict[str, str] = {}
    if model_path.startswith("modal-recovery://"):
        model_id = model_path.split("modal-recovery://", 1)[1].strip()
        if not model_id:
            raise HTTPException(status_code=404, detail="Recovered 3D model is unavailable.")
        source = f"{_modal_recovery_url()}/v1/files/{model_id}/model.glb"
        headers = _modal_headers()
    else:
        source = media_url(API_BASE_URL, model_path)

    if not source:
        raise HTTPException(status_code=404, detail="Stored model is unavailable.")

    try:
        upstream = requests.get(source, headers=headers, timeout=60, stream=True)
        upstream.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Ashes could not load this stored 3D asset: {str(exc)[:180]}") from exc

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
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )
