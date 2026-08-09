from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from apps.api.mongo_main import app, auth_user, owned_business
from apps.api.mongo_db import get_product, update_product

RETAIL_CATEGORIES = {
    "solar equipment", "electronics", "mobile accessories", "ups and batteries",
    "water filters", "furniture", "mattresses", "home appliances", "led lights",
    "retail", "fashion", "appliances", "lighting", "battery", "batteries",
}


class RetailMetadataPayload(BaseModel):
    product_type: Optional[str] = None
    category: Optional[str] = None
    model_number: Optional[str] = None
    warranty_period: Optional[str] = None
    warranty_details: Optional[str] = None
    support_contact: Optional[str] = None


def _metadata(product: dict) -> dict:
    category = str(product.get("category") or "").strip()
    explicit_type = str(product.get("product_type") or "").strip().lower()
    inferred_retail = category.lower() in RETAIL_CATEGORIES or explicit_type == "retail"
    return {
        "product_id": product["id"],
        "product_type": "retail" if inferred_retail else (explicit_type or "food"),
        "category": category,
        "model_number": product.get("model_number") or "",
        "warranty_period": product.get("warranty_period") or "",
        "warranty_details": product.get("warranty_details") or "",
        "support_contact": product.get("support_contact") or "",
        "is_retail": inferred_retail,
    }


@app.get("/api/products/{product_id}/retail-metadata")
def public_retail_metadata(product_id: str):
    product = get_product(product_id)
    if not product or not product.get("is_published"):
        raise HTTPException(status_code=404, detail="Product not found")
    return _metadata(product)


@app.get("/api/businesses/{business_slug}/products/{product_id}/retail-metadata")
def owner_retail_metadata(business_slug: str, product_id: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    product = get_product(product_id)
    if not product or product.get("business_id") != business["id"]:
        raise HTTPException(status_code=404, detail="Product not found")
    return _metadata(product)


@app.patch("/api/businesses/{business_slug}/products/{product_id}/retail-metadata")
def update_retail_metadata(
    business_slug: str,
    product_id: str,
    payload: RetailMetadataPayload,
    user: dict = Depends(auth_user),
):
    business = owned_business(user["id"], business_slug)
    product = get_product(product_id)
    if not product or product.get("business_id") != business["id"]:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = {k: (v.strip() if isinstance(v, str) else v) for k, v in payload.model_dump().items() if v is not None}
    if updates.get("product_type") not in {None, "food", "retail"}:
        raise HTTPException(status_code=400, detail="product_type must be food or retail")
    updated = update_product(product_id, business["id"], updates)
    return _metadata(updated)
