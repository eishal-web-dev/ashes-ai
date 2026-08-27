from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_main import app


class ShopifyForceMultiViewMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path != "/api/shopify/app" or response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode("utf-8", errors="replace")

        # Force the base Shopify app loader onto the multiview endpoint. This is
        # intentionally unconditional so stale/legacy UI code cannot bypass the
        # product-specific recovery route.
        text = text.replace("fetch('/api/shopify/products',{cache:'no-store'})", "fetch('/api/shopify/products-multiview',{cache:'no-store'})")
        text = text.replace('fetch("/api/shopify/products",{cache:"no-store"})', 'fetch("/api/shopify/products-multiview",{cache:"no-store"})')

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        headers["X-Ashes-Force-Multiview"] = "1"
        return Response(content=text, status_code=response.status_code, headers=headers, media_type="text/html")


app.add_middleware(ShopifyForceMultiViewMiddleware)
