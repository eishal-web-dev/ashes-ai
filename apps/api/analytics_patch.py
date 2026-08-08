from __future__ import annotations

# Analytics helpers are kept separate so the main API can remain compact.
# This module is imported by apps/api/main.py.

import sqlite3
from typing import Dict

VALID_EVENTS = {"scan", "view_3d", "ar_launch"}


def ensure_analytics_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS analytics_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE INDEX IF NOT EXISTS idx_analytics_product ON analytics_events(product_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics_events(event_type);
        """
    )


def record_event(conn: sqlite3.Connection, product_id: str, event_type: str) -> None:
    if event_type not in VALID_EVENTS:
        raise ValueError("Unsupported analytics event")
    conn.execute(
        "INSERT INTO analytics_events (product_id, event_type) VALUES (?, ?)",
        (product_id, event_type),
    )


def product_metrics(conn: sqlite3.Connection, product_id: str) -> Dict[str, int]:
    rows = conn.execute(
        """
        SELECT event_type, COUNT(*) AS total
        FROM analytics_events
        WHERE product_id = ?
        GROUP BY event_type
        """,
        (product_id,),
    ).fetchall()
    data = {row["event_type"]: row["total"] for row in rows}
    return {
        "scans": int(data.get("scan", 0)),
        "views_3d": int(data.get("view_3d", 0)),
        "ar_launches": int(data.get("ar_launch", 0)),
    }


def business_metrics(conn: sqlite3.Connection, business_id: str) -> Dict[str, int]:
    rows = conn.execute(
        """
        SELECT ae.event_type, COUNT(*) AS total
        FROM analytics_events ae
        JOIN products p ON p.id = ae.product_id
        WHERE p.business_id = ?
        GROUP BY ae.event_type
        """,
        (business_id,),
    ).fetchall()
    data = {row["event_type"]: row["total"] for row in rows}
    return {
        "scans": int(data.get("scan", 0)),
        "views_3d": int(data.get("view_3d", 0)),
        "ar_launches": int(data.get("ar_launch", 0)),
    }
