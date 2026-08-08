from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import qrcode


def ensure_table_qr_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS table_qr_codes (
          id TEXT PRIMARY KEY,
          business_id TEXT NOT NULL,
          table_code TEXT NOT NULL,
          qr_path TEXT NOT NULL,
          public_url TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(business_id, table_code)
        )
        """
    )


def create_table_qr(
    conn: sqlite3.Connection,
    business_id: str,
    table_code: str,
    qr_dir: Path,
    public_base_url: str,
    product_id: str | None = None,
) -> dict:
    clean_code = table_code.strip().upper()
    if not clean_code:
        raise ValueError("Table code is required")

    existing = conn.execute(
        "SELECT * FROM table_qr_codes WHERE business_id=? AND table_code=?",
        (business_id, clean_code),
    ).fetchone()
    if existing:
        return dict(existing)

    qr_id = str(uuid.uuid4())
    query = f"table={clean_code}"
    if product_id:
        query = f"product={product_id}&{query}"
    public_url = f"{public_base_url}/?{query}"
    qr_path = qr_dir / f"table-{qr_id}.png"
    qrcode.make(public_url).save(qr_path)

    conn.execute(
        "INSERT INTO table_qr_codes (id,business_id,table_code,qr_path,public_url) VALUES (?,?,?,?,?)",
        (qr_id, business_id, clean_code, str(qr_path), public_url),
    )
    row = conn.execute("SELECT * FROM table_qr_codes WHERE id=?", (qr_id,)).fetchone()
    return dict(row)


def list_table_qrs(conn: sqlite3.Connection, business_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM table_qr_codes WHERE business_id=? ORDER BY created_at DESC",
        (business_id,),
    ).fetchall()
    return [dict(row) for row in rows]
