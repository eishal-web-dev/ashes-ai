from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_main import app
from apps.api.shopify_request_context import current_id_token, current_shop, normalize_shop, reset_shop, set_shop


def dynamic_shop() -> str:
    """Return the authenticated merchant shop for this request.

    SHOPIFY_SHOP is retained only as a development/background fallback. Merchant
    API requests are always bound to the shop from the verified App Bridge token.
    """
    shop = current_shop()
    if shop:
        return shop
    fallback = normalize_shop(os.getenv("SHOPIFY_SHOP"))
    if fallback:
        return fallback
    raise HTTPException(status_code=401, detail="No authenticated Shopify shop is available")


def merchant_access_token() -> tuple[str, dict[str, Any]]:
    """Exchange the current App Bridge ID token for a merchant Admin API token.

    Client-credentials auth only works for stores in our own Shopify organization,
    which is why it worked on ashes-stack but failed for App Store reviewers.
    """
    id_token = current_id_token()
    shop = current_shop()
    if id_token and shop:
        client_id = (os.getenv("SHOPIFY_CLIENT_ID") or os.getenv("ASHES_SHOPIFY_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("ASHES_SHOPIFY_CLIENT_SECRET") or "").strip()
        if not client_id or not client_secret:
            raise HTTPException(status_code=500, detail="Shopify token exchange is not configured")
        try:
            response = requests.post(
                f"https://{shop}/admin/oauth/access_token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "subject_token": id_token,
                    "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
                    "requested_token_type": "urn:shopify:params:oauth:token-type:online-access-token",
                },
                headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                timeout=20,
            )
            payload = response.json() if response.content else {}
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Shopify token exchange failed: {str(exc)[:180]}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Shopify token exchange returned invalid JSON") from exc
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not response.ok or not token:
            # A stale App Bridge ID token is retryable; Shopify's fetch interceptor
            # will obtain a fresh token when this header is returned by the route.
            status = 401 if response.status_code == 400 else 502
            detail = payload.get("error_description") or payload.get("error") or payload
            raise HTTPException(status_code=status, detail=f"Shopify token exchange failed: {detail}")
        return str(token), payload

    # Development/background compatibility only. Never use this branch for a
    # merchant request because the authenticated request context is set first.
    import apps.api.shopify_routes as routes
    original = getattr(routes, "_ashes_original_access_token", None)
    if original:
        return original()
    raise HTTPException(status_code=401, detail="Missing authenticated Shopify session")


def _patch_shop_bindings() -> None:
    import apps.api.shopify_routes as routes
    import apps.api.shopify_generation as generation
    import apps.api.shopify_multiview as multiview
    import apps.api.shopify_pricing_live as pricing
    import apps.api.shopify_pricing_controls as controls
    import apps.api.shopify_publish as publish
    import apps.api.shopify_publish_s3_fix as publish_s3
    import apps.api.shopify_viewer_paths as viewer

    if not hasattr(routes, "_ashes_original_access_token"):
        routes._ashes_original_access_token = routes._access_token
    routes._shop = dynamic_shop
    routes._access_token = merchant_access_token
    generation._shop = dynamic_shop

    # These modules imported _shop/_access_token by value, so replace their local
    # bindings too. This keeps billing, generation, publishing, and storage scoped
    # to the merchant who is actually using the embedded app.
    for module in (multiview, pricing, controls, publish, publish_s3, viewer):
        if hasattr(module, "_shop"):
            module._shop = dynamic_shop
        if hasattr(module, "_access_token"):
            module._access_token = merchant_access_token


_patch_shop_bindings()


_APP_BRIDGE = r'''
<!-- ASHES_REVIEWER_FRESH_INSTALL_V1 -->
<meta name="shopify-api-key" content="__ASHES_SHOPIFY_API_KEY__">
<script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
<script>
(function(){
  // App Bridge automatically authenticates same-origin fetch calls. Keep a
  // manual fallback so every API request has a fresh ID token during review.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function(input, init){
    init = init || {};
    try {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const sameOrigin = !/^https?:\/\//i.test(url) || url.indexOf(window.location.origin) === 0;
      if (sameOrigin && url.indexOf('/api/shopify/') !== -1 && window.shopify && window.shopify.idToken) {
        const token = await window.shopify.idToken();
        const headers = new Headers(init.headers || (input && input.headers) || {});
        headers.set('Authorization', 'Bearer ' + token);
        init = Object.assign({}, init, {headers: headers});
      }
    } catch (_) {}
    return nativeFetch(input, init);
  };
})();
</script>
'''


class ShopifyReviewerFreshInstallMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Bind App Home rendering to Shopify's shop query param when present. Data
        # requests are rebound by the verified ID-token middleware.
        shop_ctx = None
        if request.url.path == "/api/shopify/app":
            candidate = normalize_shop(request.query_params.get("shop"))
            if candidate:
                shop_ctx = set_shop(candidate)
        try:
            response = await call_next(request)
        finally:
            if shop_ctx is not None:
                reset_shop(shop_ctx)

        if request.url.path != "/api/shopify/app" or response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode("utf-8", errors="replace")
        if "ASHES_REVIEWER_FRESH_INSTALL_V1" not in text:
            client_id = (os.getenv("SHOPIFY_CLIENT_ID") or os.getenv("ASHES_SHOPIFY_CLIENT_ID") or "").strip()
            inject = _APP_BRIDGE.replace("__ASHES_SHOPIFY_API_KEY__", client_id)
            text = text.replace("</head>", inject + "</head>")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return Response(content=text, status_code=response.status_code, headers=headers, media_type="text/html")


app.add_middleware(ShopifyReviewerFreshInstallMiddleware)
