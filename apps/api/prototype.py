from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException
from pydantic import BaseModel, Field

from apps.api.mongo_main import app
from apps.api.commerce_sources import _crawl, _safe_public_url


class PrototypeScanPayload(BaseModel):
    url: str = Field(min_length=4, max_length=2048)
    max_pages: int = Field(default=8, ge=1, le=8)


@app.post("/api/prototype/scan")
def scan_prototype_catalog(payload: PrototypeScanPayload) -> dict:
    """Read-only catalog preview for the public Ashes prototype.

    The endpoint intentionally does not create businesses, products, imports, or
    other database records. Publishing a catalog remains an authenticated action.
    """
    safe_url = _safe_public_url(payload.url)
    products = _crawl(safe_url, payload.max_pages)
    host = urlparse(safe_url).hostname or "merchant website"

    cleaned = []
    for item in products[:12]:
        name = str(item.get("name") or "Imported product").strip()[:180]
        image = item.get("image_url")
        source = item.get("source_url")
        cleaned.append({
            "name": name,
            "description": str(item.get("description") or "").strip()[:320] or None,
            "image_url": image if isinstance(image, str) else None,
            "price": item.get("price"),
            "currency": item.get("currency") or "USD",
            "source_url": source if isinstance(source, str) else safe_url,
            "external_product_id": item.get("external_product_id"),
            "readiness": "image-ready" if image else "needs-image",
        })

    if not cleaned:
        raise HTTPException(
            422,
            "The website responded, but no structured products were found. It may block automated catalog access.",
        )

    return {
        "mode": "live",
        "website_url": safe_url,
        "merchant": host.removeprefix("www."),
        "found": len(cleaned),
        "products": cleaned,
        "notice": "Read-only preview. Nothing was saved or published.",
    }
