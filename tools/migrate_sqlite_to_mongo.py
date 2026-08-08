from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = ROOT / "apps" / "api" / "data" / "ashes.db"


def rowdict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def fetch_all(conn: sqlite3.Connection, table: str) -> list[dict]:
    if not table_exists(conn, table):
        return []
    return [rowdict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def migrate(sqlite_path: Path, mongo_uri: str, mongo_db: str, replace: bool = False) -> None:
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    db = client[mongo_db]

    users = fetch_all(source, "users")
    businesses = fetch_all(source, "businesses")
    products = fetch_all(source, "products")
    analytics = fetch_all(source, "analytics_events")
    orders = fetch_all(source, "orders")
    order_items = fetch_all(source, "order_items")
    histories = fetch_all(source, "order_status_history")
    table_qrs = fetch_all(source, "table_qrs")
    menu_imports = fetch_all(source, "menu_imports")

    if replace:
        for name in ("users", "businesses", "products", "analytics_events", "orders", "table_qrs", "menu_imports"):
            db[name].delete_many({})

    for user in users:
        db.users.replace_one({"id": user["id"]}, user, upsert=True)

    for business in businesses:
        db.businesses.replace_one({"id": business["id"]}, business, upsert=True)

    for product in products:
        product["name_key"] = str(product.get("name") or "").strip().lower()
        product["category_key"] = str(product.get("category") or "Main").strip().lower()
        product["is_published"] = bool(product.get("is_published"))
        db.products.replace_one({"id": product["id"]}, product, upsert=True)

    for event in analytics:
        event_id = str(event.get("id"))
        product = next((p for p in products if p["id"] == event.get("product_id")), None)
        doc = {
            "id": event_id,
            "product_id": event.get("product_id"),
            "business_id": product.get("business_id") if product else None,
            "event_type": event.get("event_type"),
            "created_at": event.get("created_at"),
        }
        db.analytics_events.replace_one({"id": event_id}, doc, upsert=True)

    items_by_order: dict[str, list[dict]] = {}
    for item in order_items:
        items_by_order.setdefault(item["order_id"], []).append({
            "product_id": item.get("product_id"),
            "product_name": item.get("product_name"),
            "unit_price": float(item.get("unit_price") or 0),
            "quantity": int(item.get("quantity") or 1),
            "line_total": float(item.get("line_total") or 0),
        })

    history_by_order: dict[str, list[dict]] = {}
    for item in histories:
        history_by_order.setdefault(item["order_id"], []).append({
            "status": item.get("status"),
            "created_at": item.get("created_at"),
        })

    for order in orders:
        order["total"] = float(order.get("total") or 0)
        order["notified_business"] = bool(order.get("notified_business"))
        order["items"] = items_by_order.get(order["id"], [])
        order["history"] = history_by_order.get(order["id"], []) or [{"status": order.get("status", "new"), "created_at": order.get("created_at")}]
        db.orders.replace_one({"id": order["id"]}, order, upsert=True)

    for qr in table_qrs:
        db.table_qrs.replace_one({"id": qr["id"]}, qr, upsert=True)

    for imp in menu_imports:
        db.menu_imports.replace_one({"id": imp["id"]}, imp, upsert=True)

    db.users.create_index("email", unique=True)
    db.businesses.create_index("slug", unique=True)
    db.businesses.create_index("owner_user_id")
    db.products.create_index([("business_id", 1), ("created_at", -1)])
    db.analytics_events.create_index([("product_id", 1), ("event_type", 1)])
    db.orders.create_index([("business_id", 1), ("created_at", -1)])
    db.table_qrs.create_index([("business_id", 1), ("table_code", 1)], unique=True)

    print("Migration complete")
    print(f"users={len(users)} businesses={len(businesses)} products={len(products)} analytics={len(analytics)} orders={len(orders)} table_qrs={len(table_qrs)} menu_imports={len(menu_imports)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Ashes SQLite data to MongoDB")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE), help="Path to ashes.db")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    parser.add_argument("--mongo-db", default=os.getenv("MONGODB_DB", "ashes_ai"))
    parser.add_argument("--replace", action="store_true", help="Clear Ashes Mongo collections before importing")
    args = parser.parse_args()
    migrate(Path(args.sqlite), args.mongo_uri, args.mongo_db, args.replace)
