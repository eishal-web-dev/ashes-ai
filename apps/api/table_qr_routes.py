from __future__ import annotations

import uuid
from pathlib import Path

import qrcode
from fastapi import Depends, HTTPException

from apps.api.media_storage import media_url, store_media
from apps.api.mongo_db import create_table_qr, get_product, list_table_qrs
from apps.api.mongo_main import API_BASE_URL, PUBLIC_BASE_URL, QR_DIR, TableQrPayload, app, auth_user, owned_business


def _table_qr_out(row: dict) -> dict:
    data = dict(row)
    data["qr_url"] = media_url(API_BASE_URL, row.get("qr_path")) if row.get("qr_path") else None
    data.pop("qr_path", None)
    return data


@app.get("/api/businesses/{business_slug}/table-qrs")
def get_table_qrs(business_slug: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    return [_table_qr_out(row) for row in list_table_qrs(business["id"])]


@app.post("/api/businesses/{business_slug}/table-qrs")
def make_table_qr(business_slug: str, payload: TableQrPayload, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    table_code = payload.table_code.strip()
    if not table_code:
        raise HTTPException(400, "Table code is required")

    product_id = payload.product_id
    if product_id:
        product = get_product(product_id)
        if not product or product.get("business_id") != business["id"]:
            raise HTTPException(400, "Selected product does not belong to this business")

    # A table QR may open a specific product or the business storefront.
    if product_id:
        public_url = f"{PUBLIC_BASE_URL}/?product={product_id}&table={table_code}"
    else:
        public_url = f"{PUBLIC_BASE_URL}/?business={business_slug}&table={table_code}"

    qr_id = str(uuid.uuid4())
    tmp_path = QR_DIR / f"table-{qr_id}.png"
    qrcode.make(public_url).save(tmp_path)
    try:
        storage_key = store_media(
            API_BASE_URL,
            tmp_path,
            f"table-qr/{business['id']}/table-{qr_id}.png",
            "image/png",
        )
    finally:
        try:
            # Local storage uses the same path, so keep it there. Remote storage can remove temp.
            if str(tmp_path) != str(locals().get("storage_key", "")) and not str(locals().get("storage_key", "")).startswith(str(QR_DIR)):
                tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    row = create_table_qr({
        "business_id": business["id"],
        "table_code": table_code,
        "product_id": product_id,
        "public_url": public_url,
        "qr_path": storage_key,
    })
    return _table_qr_out(row)
