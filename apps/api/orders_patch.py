from __future__ import annotations

import sqlite3
import uuid
from typing import Iterable


def ensure_order_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS orders (
          id TEXT PRIMARY KEY,
          business_id TEXT NOT NULL,
          table_code TEXT,
          customer_name TEXT,
          notes TEXT,
          status TEXT NOT NULL DEFAULT 'new',
          total REAL NOT NULL DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
          id TEXT PRIMARY KEY,
          order_id TEXT NOT NULL,
          product_id TEXT NOT NULL,
          product_name TEXT NOT NULL,
          unit_price REAL NOT NULL,
          quantity INTEGER NOT NULL DEFAULT 1,
          line_total REAL NOT NULL,
          FOREIGN KEY(order_id) REFERENCES orders(id),
          FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """
    )


def create_order(conn: sqlite3.Connection, business_id: str, items: Iterable[dict], table_code: str | None, customer_name: str | None, notes: str | None) -> dict:
    normalized = []
    total = 0.0
    for item in items:
        product_id = str(item.get("product_id", "")).strip()
        quantity = max(1, int(item.get("quantity", 1)))
        row = conn.execute(
            "SELECT id, business_id, name, price FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if not row or row["business_id"] != business_id:
            raise ValueError("Invalid product in order")
        line_total = float(row["price"]) * quantity
        total += line_total
        normalized.append({
            "product_id": row["id"],
            "product_name": row["name"],
            "unit_price": float(row["price"]),
            "quantity": quantity,
            "line_total": line_total,
        })

    if not normalized:
        raise ValueError("Order must contain at least one item")

    order_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO orders (id, business_id, table_code, customer_name, notes, status, total) VALUES (?, ?, ?, ?, ?, 'new', ?)",
        (order_id, business_id, table_code, customer_name, notes, total),
    )
    for item in normalized:
        conn.execute(
            "INSERT INTO order_items (id, order_id, product_id, product_name, unit_price, quantity, line_total) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), order_id, item["product_id"], item["product_name"], item["unit_price"], item["quantity"], item["line_total"]),
        )
    return get_order(conn, order_id)


def get_order(conn: sqlite3.Connection, order_id: str) -> dict | None:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return None
    items = conn.execute(
        "SELECT product_id, product_name, unit_price, quantity, line_total FROM order_items WHERE order_id = ? ORDER BY rowid",
        (order_id,),
    ).fetchall()
    return {**dict(order), "items": [dict(x) for x in items]}


def list_business_orders(conn: sqlite3.Connection, business_id: str) -> list[dict]:
    orders = conn.execute(
        "SELECT id FROM orders WHERE business_id = ? ORDER BY created_at DESC LIMIT 100",
        (business_id,),
    ).fetchall()
    return [get_order(conn, row["id"]) for row in orders]
