from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any


def _normalize_item(item: dict[str, Any], fallback_category: str = "Main") -> dict[str, Any] | None:
    name = str(item.get("name") or "").strip()
    if not name:
        return None
    raw_price = item.get("price", 0)
    try:
        price = float(str(raw_price).replace(",", "").replace("Rs.", "").replace("Rs", "").strip())
    except Exception:
        price = 0.0
    category = str(item.get("category") or fallback_category or "Main").strip() or "Main"
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [x.strip() for x in tags.split(",") if x.strip()]
    return {
        "name": name,
        "price": max(0.0, price),
        "category": category,
        "calories": str(item.get("calories") or "").strip(),
        "protein": str(item.get("protein") or "").strip(),
        "carbs": str(item.get("carbs") or "").strip(),
        "fat": str(item.get("fat") or "").strip(),
        "tags": tags,
        "description": str(item.get("description") or "").strip(),
    }


def normalize_menu_payload(payload: dict[str, Any]) -> dict[str, Any]:
    business = payload.get("business") or {}
    categories = payload.get("categories") or []
    items: list[dict[str, Any]] = []

    if categories:
        for category in categories:
            category_name = str(category.get("name") or "Main").strip() or "Main"
            for item in category.get("items") or []:
                normalized = _normalize_item(item, category_name)
                if normalized:
                    items.append(normalized)
    else:
        for item in payload.get("items") or []:
            normalized = _normalize_item(item)
            if normalized:
                items.append(normalized)

    return {
        "business": {
            "name": str(business.get("name") or "").strip(),
            "phone": str(business.get("phone") or "").strip(),
            "instagram": str(business.get("instagram") or "").strip(),
            "website": str(business.get("website") or "").strip(),
            "city": str(business.get("city") or "").strip(),
        },
        "items": items,
    }


def _extract_json_block(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("Menu extractor did not return JSON")
        return json.loads(match.group(0))


def extract_menu(image_path: Path) -> dict[str, Any]:
    """Extract structured menu data from a menu-card image.

    Provider seam:
    - ASHES_MENU_IMPORT_COMMAND: executable command. Ashes appends the image path.
      The command must print JSON to stdout.
    - Without a provider, a sibling <image>.json file is accepted for development.
    """
    sidecar = image_path.with_suffix(image_path.suffix + ".json")
    if sidecar.exists():
        return normalize_menu_payload(json.loads(sidecar.read_text(encoding="utf-8")))

    command = os.getenv("ASHES_MENU_IMPORT_COMMAND", "").strip()
    if not command:
        raise RuntimeError(
            "Menu AI extractor is not configured. Set ASHES_MENU_IMPORT_COMMAND to a vision extractor command."
        )

    timeout = int(os.getenv("ASHES_MENU_IMPORT_TIMEOUT", "120"))
    completed = subprocess.run(
        [*command.split(), str(image_path)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "Menu extraction failed")[:1000])

    payload = _extract_json_block(completed.stdout)
    return normalize_menu_payload(payload)


def import_products(conn, business_id: str, items: list[dict[str, Any]], public_base_url: str, qr_dir: Path) -> list[str]:
    created_ids: list[str] = []
    for item in items:
        product_id = str(uuid.uuid4())
        public_url = f"{public_base_url}/?product={product_id}"
        qr_path = qr_dir / f"{product_id}.png"
        import qrcode
        qrcode.make(public_url).save(qr_path)
        conn.execute(
            "INSERT INTO products (id,business_id,name,category,price,calories,protein,carbs,fat,tags,status,error_message,qr_code,is_published) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (
                product_id,
                business_id,
                item["name"],
                item.get("category") or "Main",
                float(item.get("price") or 0),
                item.get("calories") or "",
                item.get("protein") or "",
                item.get("carbs") or "",
                item.get("fat") or "",
                ", ".join(item.get("tags") or []),
                "awaiting-image",
                "Imported from menu card. Add a product photo to generate its 3D model.",
                str(qr_path),
            ),
        )
        created_ids.append(product_id)
    return created_ids
