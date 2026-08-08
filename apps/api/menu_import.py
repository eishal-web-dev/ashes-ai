from __future__ import annotations

import base64
import json
import mimetypes
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
    confidence = item.get("confidence", 1.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except Exception:
        confidence = 0.5
    needs_review = bool(item.get("needs_review", False)) or price <= 0 or confidence < 0.85
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
        "confidence": confidence,
        "needs_review": needs_review,
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


def _openai_extract(image_path: Path) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI menu importer requires the 'openai' Python package") from exc

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = os.getenv("ASHES_MENU_VISION_MODEL", "gpt-5.5").strip() or "gpt-5.5"
    mime = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")

    prompt = """
You are extracting a restaurant/cafe menu into structured data for Ashes AI.
Read only information visible in the supplied menu image. Do not invent missing values.
Return JSON only, matching this shape:
{
  "business": {
    "name": "",
    "phone": "",
    "instagram": "",
    "website": "",
    "city": ""
  },
  "categories": [
    {
      "name": "Burgers",
      "items": [
        {
          "name": "Classic Burger",
          "price": 850,
          "description": "",
          "calories": "",
          "protein": "",
          "carbs": "",
          "fat": "",
          "tags": [],
          "confidence": 0.98,
          "needs_review": false
        }
      ]
    }
  ]
}
Rules:
- Preserve item names and prices as printed.
- Use numeric prices without currency symbols.
- If a price or name is unclear, lower confidence and set needs_review=true.
- Never guess nutrition, ingredients, allergens, phone numbers, URLs, or social handles.
- If something is absent, use an empty string/list.
- Keep categories meaningful but faithful to the menu.
""".strip()

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"},
                ],
            }
        ],
    )
    return normalize_menu_payload(_extract_json_block(response.output_text))


def extract_menu(image_path: Path) -> dict[str, Any]:
    """Extract structured menu data from a menu-card image.

    Provider order:
    1. sibling <image>.json sidecar for deterministic development
    2. ASHES_MENU_IMPORT_PROVIDER=openai using OPENAI_API_KEY
    3. ASHES_MENU_IMPORT_COMMAND command provider (Ashes appends image path)
    """
    sidecar = image_path.with_suffix(image_path.suffix + ".json")
    if sidecar.exists():
        return normalize_menu_payload(json.loads(sidecar.read_text(encoding="utf-8")))

    provider = os.getenv("ASHES_MENU_IMPORT_PROVIDER", "").strip().lower()
    if provider == "openai":
        return _openai_extract(image_path)

    command = os.getenv("ASHES_MENU_IMPORT_COMMAND", "").strip()
    if not command:
        raise RuntimeError(
            "Menu AI extractor is not configured. Set ASHES_MENU_IMPORT_PROVIDER=openai with OPENAI_API_KEY, or ASHES_MENU_IMPORT_COMMAND."
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


def _item_key(name: str, category: str) -> tuple[str, str]:
    clean = lambda value: re.sub(r"\s+", " ", value.strip().lower())
    return clean(name), clean(category or "Main")


def import_products(conn, business_id: str, items: list[dict[str, Any]], public_base_url: str, qr_dir: Path) -> dict[str, Any]:
    existing_rows = conn.execute("SELECT name, category FROM products WHERE business_id=?", (business_id,)).fetchall()
    existing = {_item_key(row["name"], row["category"] or "Main") for row in existing_rows}
    created_ids: list[str] = []
    skipped_duplicates: list[str] = []
    needs_review: list[dict[str, Any]] = []

    for item in items:
        key = _item_key(item["name"], item.get("category") or "Main")
        if key in existing:
            skipped_duplicates.append(item["name"])
            continue

        product_id = str(uuid.uuid4())
        public_url = f"{public_base_url}/?product={product_id}"
        qr_path = qr_dir / f"{product_id}.png"
        import qrcode
        qrcode.make(public_url).save(qr_path)

        review_message = "Imported from menu card. Add a product photo to generate its 3D model."
        if item.get("needs_review"):
            review_message = "Imported from menu card and flagged for review. Verify name/price, then add a product photo for 3D."
            needs_review.append({
                "name": item["name"],
                "category": item.get("category") or "Main",
                "confidence": item.get("confidence", 0.5),
            })

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
                review_message,
                str(qr_path),
            ),
        )
        created_ids.append(product_id)
        existing.add(key)

    return {
        "created_ids": created_ids,
        "created_count": len(created_ids),
        "skipped_duplicates": skipped_duplicates,
        "review_items": needs_review,
    }
