from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "ashes_ai")

_client: MongoClient = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
_db: Database = _client[MONGODB_DB]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def database() -> Database:
    return _db


def collection(name: str) -> Collection:
    return _db[name]


def init_mongo() -> None:
    _client.admin.command("ping")
    collection("users").create_index("email", unique=True)
    collection("businesses").create_index("slug", unique=True)
    collection("businesses").create_index("owner_user_id")
    collection("products").create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    collection("products").create_index([("business_id", ASCENDING), ("name_key", ASCENDING), ("category_key", ASCENDING)])
    collection("analytics_events").create_index([("product_id", ASCENDING), ("event_type", ASCENDING)])
    collection("analytics_events").create_index("business_id")
    collection("orders").create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    collection("table_qrs").create_index([("business_id", ASCENDING), ("table_code", ASCENDING)], unique=True)
    collection("menu_imports").create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    collection("usage_monthly").create_index([("business_id", ASCENDING), ("month", ASCENDING)], unique=True)
    collection("billing_checkout_intents").create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    collection("billing_checkout_intents").create_index("id", unique=True)
    collection("billing_events").create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])
    collection("billing_events").create_index("provider_event_id", unique=True, sparse=True)
    collection("billing_settings").create_index("key", unique=True)
    collection("manual_payment_settings").create_index("key", unique=True)
    collection("manual_payment_proofs").create_index("id", unique=True)
    collection("manual_payment_proofs").create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    collection("manual_payment_proofs").create_index([("business_id", ASCENDING), ("created_at", DESCENDING)])


def clean_doc(doc: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not doc:
        return None
    value = dict(doc)
    value.pop("_id", None)
    return value


def clean_docs(docs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [clean_doc(x) for x in docs if x]


def new_id() -> str:
    return str(uuid.uuid4())


def create_user(email: str, password_hash: str, name: str) -> dict[str, Any]:
    doc = {"id": new_id(), "email": email, "password_hash": password_hash, "name": name, "created_at": now_iso()}
    collection("users").insert_one(doc)
    return clean_doc(doc)


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    return clean_doc(collection("users").find_one({"email": email}))


def get_user(user_id: str) -> Optional[dict[str, Any]]:
    return clean_doc(collection("users").find_one({"id": user_id}))


def create_business(owner_user_id: Optional[str], name: str, slug: str, kind: str, city: Optional[str]) -> dict[str, Any]:
    doc = {
        "id": new_id(), "owner_user_id": owner_user_id, "name": name, "slug": slug, "kind": kind or "restaurant",
        "city": city, "phone": None, "instagram": None, "website": None, "accent_color": "#ff2f9f", "logo_path": None,
        "created_at": now_iso(),
    }
    collection("businesses").insert_one(doc)
    return clean_doc(doc)


def get_business_by_slug(slug: str) -> Optional[dict[str, Any]]:
    return clean_doc(collection("businesses").find_one({"slug": slug}))


def get_business_by_id(business_id: str) -> Optional[dict[str, Any]]:
    return clean_doc(collection("businesses").find_one({"id": business_id}))


def list_user_businesses(user_id: str) -> list[dict[str, Any]]:
    return clean_docs(collection("businesses").find({"owner_user_id": user_id}).sort("created_at", ASCENDING))


def update_business(business_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    if updates:
        collection("businesses").update_one({"id": business_id}, {"$set": updates})
    return get_business_by_id(business_id)


def create_product(doc: dict[str, Any]) -> dict[str, Any]:
    value = {
        "id": doc.get("id") or new_id(), "business_id": doc["business_id"], "name": doc["name"],
        "name_key": str(doc["name"]).strip().lower(), "category": doc.get("category") or "Main",
        "category_key": str(doc.get("category") or "Main").strip().lower(), "price": float(doc.get("price") or 0),
        "calories": doc.get("calories") or "", "protein": doc.get("protein") or "", "carbs": doc.get("carbs") or "",
        "fat": doc.get("fat") or "", "tags": doc.get("tags") or "", "image_path": doc.get("image_path"),
        "model_path": doc.get("model_path"), "status": doc.get("status") or "queued", "error_message": doc.get("error_message"),
        "qr_code": doc.get("qr_code"), "is_published": bool(doc.get("is_published", False)), "created_at": doc.get("created_at") or now_iso(),
    }
    collection("products").insert_one(value)
    return clean_doc(value)


def get_product(product_id: str) -> Optional[dict[str, Any]]:
    return clean_doc(collection("products").find_one({"id": product_id}))


def list_products(business_id: str, include_unpublished: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"business_id": business_id}
    if not include_unpublished:
        query["is_published"] = True
    return clean_docs(collection("products").find(query).sort("created_at", DESCENDING))


def update_product(product_id: str, business_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    value = dict(updates)
    if "name" in value: value["name_key"] = str(value["name"]).strip().lower()
    if "category" in value: value["category_key"] = str(value["category"]).strip().lower()
    if value:
        collection("products").update_one({"id": product_id, "business_id": business_id}, {"$set": value})
    return clean_doc(collection("products").find_one({"id": product_id, "business_id": business_id}))


def delete_product(product_id: str, business_id: str) -> Optional[dict[str, Any]]:
    doc = clean_doc(collection("products").find_one({"id": product_id, "business_id": business_id}))
    if doc:
        collection("analytics_events").delete_many({"product_id": product_id})
        collection("products").delete_one({"id": product_id, "business_id": business_id})
    return doc


def find_duplicate_product(business_id: str, name: str, category: str) -> Optional[dict[str, Any]]:
    return clean_doc(collection("products").find_one({
        "business_id": business_id,
        "name_key": name.strip().lower(),
        "category_key": (category or "Main").strip().lower(),
    }))


def record_analytics(product_id: str, business_id: str, event_type: str) -> None:
    collection("analytics_events").insert_one({
        "id": new_id(), "product_id": product_id, "business_id": business_id, "event_type": event_type, "created_at": now_iso()
    })


def product_metrics(product_id: str) -> dict[str, int]:
    pipeline = [{"$match": {"product_id": product_id}}, {"$group": {"_id": "$event_type", "total": {"$sum": 1}}}]
    data = {x["_id"]: x["total"] for x in collection("analytics_events").aggregate(pipeline)}
    return {"scans": int(data.get("scan", 0)), "views_3d": int(data.get("view_3d", 0)), "ar_launches": int(data.get("ar_launch", 0))}


def business_metrics(business_id: str) -> dict[str, int]:
    pipeline = [{"$match": {"business_id": business_id}}, {"$group": {"_id": "$event_type", "total": {"$sum": 1}}}]
    data = {x["_id"]: x["total"] for x in collection("analytics_events").aggregate(pipeline)}
    return {"scans": int(data.get("scan", 0)), "views_3d": int(data.get("view_3d", 0)), "ar_launches": int(data.get("ar_launch", 0))}


def create_order(business_id: str, items: Iterable[dict[str, Any]], table_code: Optional[str], customer_name: Optional[str], notes: Optional[str]) -> dict[str, Any]:
    normalized = []
    total = 0.0
    for item in items:
        product_id = str(item.get("product_id", "")).strip()
        quantity = min(99, max(1, int(item.get("quantity", 1))))
        product = get_product(product_id)
        if not product or product["business_id"] != business_id or not product.get("is_published"):
            raise ValueError("Invalid or unavailable product in order")
        line_total = float(product["price"]) * quantity
        total += line_total
        normalized.append({"product_id": product_id, "product_name": product["name"], "unit_price": float(product["price"]), "quantity": quantity, "line_total": line_total})
    if not normalized:
        raise ValueError("Order must contain at least one item")
    stamp = now_iso()
    doc = {
        "id": new_id(), "business_id": business_id, "table_code": table_code, "customer_name": customer_name, "notes": notes,
        "status": "new", "total": total, "items": normalized, "history": [{"status": "new", "created_at": stamp}],
        "notified_business": False, "created_at": stamp, "updated_at": stamp,
    }
    collection("orders").insert_one(doc)
    return clean_doc(doc)


def get_order(order_id: str) -> Optional[dict[str, Any]]:
    return clean_doc(collection("orders").find_one({"id": order_id}))


def list_business_orders(business_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return clean_docs(collection("orders").find({"business_id": business_id}).sort("created_at", DESCENDING).limit(limit))


def set_order_status(order_id: str, business_id: str, status: str) -> Optional[dict[str, Any]]:
    order = get_order(order_id)
    if not order or order["business_id"] != business_id:
        return None
    if order.get("status") != status:
        stamp = now_iso()
        collection("orders").update_one({"id": order_id, "business_id": business_id}, {
            "$set": {"status": status, "updated_at": stamp}, "$push": {"history": {"status": status, "created_at": stamp}}
        })
    return get_order(order_id)


def list_unnotified_orders(business_id: str) -> list[dict[str, Any]]:
    return clean_docs(collection("orders").find({"business_id": business_id, "notified_business": False}).sort("created_at", ASCENDING))


def mark_orders_notified(order_ids: list[str]) -> None:
    if order_ids:
        collection("orders").update_many({"id": {"$in": order_ids}}, {"$set": {"notified_business": True}})


def create_table_qr(doc: dict[str, Any]) -> dict[str, Any]:
    value = {"id": new_id(), "business_id": doc["business_id"], "table_code": doc["table_code"], "product_id": doc.get("product_id"), "public_url": doc["public_url"], "qr_path": doc["qr_path"], "created_at": now_iso()}
    collection("table_qrs").insert_one(value)
    return clean_doc(value)


def list_table_qrs(business_id: str) -> list[dict[str, Any]]:
    return clean_docs(collection("table_qrs").find({"business_id": business_id}).sort("created_at", DESCENDING))


def create_menu_import(business_id: str, image_path: str) -> dict[str, Any]:
    doc = {"id": new_id(), "business_id": business_id, "image_path": image_path, "status": "processing", "items_found": 0, "error_message": None, "created_at": now_iso()}
    collection("menu_imports").insert_one(doc)
    return clean_doc(doc)


def update_menu_import(import_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    collection("menu_imports").update_one({"id": import_id}, {"$set": updates})
    return clean_doc(collection("menu_imports").find_one({"id": import_id}))


def list_menu_imports(business_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return clean_docs(collection("menu_imports").find({"business_id": business_id}).sort("created_at", DESCENDING).limit(limit))
