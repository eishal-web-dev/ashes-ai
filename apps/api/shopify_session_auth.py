from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.mongo_main import app
from apps.api.shopify_request_context import (
    normalize_shop,
    reset_id_token,
    reset_shop,
    set_id_token,
    set_shop,
)


# App Home itself must stay public so Shopify can render the shell. All data and
# merchant actions are authenticated with the App Bridge ID token.
_PROTECTED_PREFIXES = (
    "/api/shopify/products",
    "/api/shopify/products-multiview",
    "/api/shopify/plans",
    "/api/shopify/billing-url",
    "/api/shopify/app-pricing/cancel",
    "/api/shopify/generate-3d",
    "/api/shopify/generate-3d-multiview",
    "/api/shopify/generation",
    "/api/shopify/publish-3d",
    "/api/shopify/assets",
)


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def verify_shopify_session_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid Shopify session token")

    header_b64, payload_b64, signature_b64 = parts
    secret = (os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("ASHES_SHOPIFY_CLIENT_SECRET") or "").strip()
    client_id = (os.getenv("SHOPIFY_CLIENT_ID") or os.getenv("ASHES_SHOPIFY_CLIENT_ID") or "").strip()
    if not secret or not client_id:
        raise HTTPException(status_code=500, detail="Shopify session-token verification is not configured")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64url_decode(signature_b64)
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Shopify session token") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(status_code=401, detail="Invalid Shopify session token signature")

    now = int(time.time())
    if int(payload.get("exp") or 0) <= now:
        raise HTTPException(status_code=401, detail="Shopify session token expired")
    if int(payload.get("nbf") or 0) > now + 5:
        raise HTTPException(status_code=401, detail="Shopify session token is not active yet")

    aud = payload.get("aud")
    valid_aud = client_id in aud if isinstance(aud, list) else str(aud or "") == client_id
    if not valid_aud:
        raise HTTPException(status_code=401, detail="Shopify session token audience mismatch")

    dest = str(payload.get("dest") or "")
    issuer = str(payload.get("iss") or "")
    dest_shop = normalize_shop(urlparse(dest).hostname)
    issuer_shop = normalize_shop(urlparse(issuer).hostname)
    if not dest_shop or issuer_shop != dest_shop:
        raise HTTPException(status_code=401, detail="Shopify session token shop mismatch")

    payload["ashes_shop"] = dest_shop
    return payload


class ShopifySessionTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing Shopify session token")

        raw_token = auth.split(" ", 1)[1].strip()
        payload = verify_shopify_session_token(raw_token)
        shop = payload["ashes_shop"]
        request.state.shopify_session = payload
        request.state.shopify_shop = shop

        shop_ctx = set_shop(shop)
        token_ctx = set_id_token(raw_token)
        try:
            return await call_next(request)
        finally:
            reset_id_token(token_ctx)
            reset_shop(shop_ctx)


app.add_middleware(ShopifySessionTokenMiddleware)
