from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import Depends, File, HTTPException, UploadFile

from apps.api.media_storage import store_media
from apps.api.menu_import import extract_menu
from apps.api.mongo_main import API_BASE_URL, app, auth_user, owned_business
from apps.api.mongo_db import (
    create_menu_import,
    create_product,
    find_duplicate_product,
    update_menu_import,
)
from apps.api.subscriptions import assert_capacity, increment_usage


def _tmp_path(suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    path = Path(handle.name)
    handle.close()
    return path


@app.post("/api/storage/businesses/{business_slug}/import-menu-card")
async def storage_import_menu_card(
    business_slug: str,
    image: UploadFile = File(...),
    user: dict = Depends(auth_user),
):
    business = owned_business(user["id"], business_slug)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Menu card must be an image")

    try:
        assert_capacity(business["id"], "menu_imports")
    except ValueError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    ext = Path(image.filename or "menu.jpg").suffix.lower() or ".jpg"
    temp_path = _tmp_path(ext)
    temp_path.write_bytes(await image.read())
    provisional = None

    try:
        provisional = create_menu_import(business["id"], "pending")
        storage_key = store_media(
            API_BASE_URL,
            temp_path,
            f"menu-imports/{business['id']}/{provisional['id']}{ext}",
            image.content_type,
        )
        update_menu_import(provisional["id"], {"image_path": storage_key})

        extracted = extract_menu(temp_path)
        items = extracted.get("items") or []
        if not items:
            raise ValueError("No menu items were detected")

        created = []
        skipped = []
        review = []
        for raw in items:
            name = str(raw.get("name") or "").strip()
            category = str(raw.get("category") or "Main").strip() or "Main"
            price = raw.get("price")
            if not name or price in (None, ""):
                review.append({"name": name or "Unnamed item", "reason": "Missing name or price"})
                continue
            try:
                price_value = float(str(price).replace(",", "").strip())
            except ValueError:
                review.append({"name": name, "reason": "Price needs review"})
                continue

            if find_duplicate_product(business["id"], name, category):
                skipped.append(name)
                continue

            try:
                assert_capacity(business["id"], "products", len(created) + 1)
            except ValueError:
                review.append({"name": name, "reason": "Plan product limit reached"})
                continue

            confidence = float(raw.get("confidence") or 1)
            tags = raw.get("tags") or ""
            if isinstance(tags, list):
                tags = ", ".join(str(x) for x in tags if x)
            product = create_product({
                "business_id": business["id"],
                "name": name,
                "category": category,
                "price": price_value,
                "tags": tags,
                "status": "awaiting-image",
                "is_published": False,
            })
            created.append(product)
            if confidence < 0.75:
                review.append({"name": name, "reason": "Low AI confidence", "confidence": confidence})

        increment_usage(business["id"], "menu_imports")
        update_menu_import(
            provisional["id"],
            {
                "status": "completed",
                "items_found": len(created),
                "error_message": None,
            },
        )
        return {
            "import_id": provisional["id"],
            "status": "completed",
            "items_found": len(created),
            "created_count": len(created),
            "duplicates_skipped": len(skipped),
            "needs_review": len(review),
            "review_items": review,
            "review_required": True,
        }
    except Exception as exc:
        if provisional:
            try:
                update_menu_import(provisional["id"], {"status": "failed", "error_message": str(exc)[:800]})
            except Exception:
                pass
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)
