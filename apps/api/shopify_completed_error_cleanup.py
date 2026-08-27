from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.mongo_db import collection
from apps.api.mongo_main import app
from apps.api.shopify_generation import _shop


class ShopifyCompletedErrorCleanupMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method == "GET" and request.url.path in {
            "/api/shopify/products-multiview",
            "/api/shopify/products",
            "/api/shopify/plans",
        }:
            try:
                collection("shopify_generation_jobs").update_many(
                    {
                        "shop": _shop(),
                        "status": "COMPLETED",
                        "error": {"$exists": True},
                    },
                    {"$unset": {"error": ""}},
                )
            except Exception:
                pass
        return response


app.add_middleware(ShopifyCompletedErrorCleanupMiddleware)
