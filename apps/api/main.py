from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from apps.api.services.three_d import MODEL_DIR, generate_3d

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
QR_DIR = DATA_DIR / "qr"
DB_PATH = DATA_DIR / "ashes.db"
PUBLIC_BASE_URL = os.getenv("ASHES_PUBLIC_BASE_URL", "http://localhost:5173")
API_BASE_URL = os.getenv("ASHES_API_BASE_URL", "http://localhost:8000")

for directory in (DATA_DIR, UPLOAD_DIR, QR_DIR, MODEL_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Ashes AI API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS businesses (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              slug TEXT UNIQUE NOT NULL,
              kind TEXT NOT NULL DEFAULT 'restaurant',
              city TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
              id TEXT PRIMARY KEY,
              business_id TEXT NOT NULL,
              name TEXT NOT NULL,
              category TEXT,
              price REAL NOT NULL,
              calories TEXT,
              protein TEXT,
              carbs TEXT,
              fat TEXT,
              tags TEXT,
              image_path TEXT,
              model_path TEXT,
              status TEXT NOT NULL DEFAULT 'queued',
              error_message TEXT,
              qr_code TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(business_id) REFERENCES businesses(id)
            );
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
        if "error_message" not in columns:
            conn.execute("ALTER TABLE products ADD COLUMN error_message TEXT")

        demo = conn.execute("SELECT id FROM businesses WHERE slug = ?", ("neon-bites",)).fetchone()
        if not demo:
            conn.execute(
                "INSERT INTO businesses (id, name, slug, kind, city) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "Neon Bites", "neon-bites", "restaurant", "Peshawar"),
            )


init_db()


class BusinessCreate(BaseModel):
    name: str
    slug: str
    kind: str = "restaurant"
    city: Optional[str] = None


class ProductOut(BaseModel):
    id: str
    business_id: str
    name: str
    category: Optional[str] = None
    price: float
    calories: Optional[str] = None
    protein: Optional[str] = None
    carbs: Optional[str] = None
    fat: Optional[str] = None
    tags: list[str] = []
    image_url: Optional[str] = None
    model_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    qr_url: Optional[str] = None
    public_url: str


def product_from_row(row: sqlite3.Row) -> ProductOut:
    public_url = f"{PUBLIC_BASE_URL}/?product={row['id']}"
    return ProductOut(
        id=row["id"],
        business_id=row["business_id"],
        name=row["name"],
        category=row["category"],
        price=row["price"],
        calories=row["calories"],
        protein=row["protein"],
        carbs=row["carbs"],
        fat=row["fat"],
        tags=[x.strip() for x in (row["tags"] or "").split(",") if x.strip()],
        image_url=f"{API_BASE_URL}/media/uploads/{Path(row['image_path']).name}" if row["image_path"] else None,
        model_url=f"{API_BASE_URL}/media/models/{Path(row['model_path']).name}" if row["model_path"] else None,
        status=row["status"],
        error_message=row["error_message"],
        qr_url=f"{API_BASE_URL}/media/qr/{Path(row['qr_code']).name}" if row["qr_code"] else None,
        public_url=public_url,
    )


def run_generation_job(product_id: str, image_path: Path) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE products SET status = ?, error_message = NULL WHERE id = ?",
            ("processing", product_id),
        )

    try:
        model_path = generate_3d(product_id, image_path)
        if model_path:
            with db() as conn:
                conn.execute(
                    "UPDATE products SET model_path = ?, status = ?, error_message = NULL WHERE id = ?",
                    (str(model_path), "ready", product_id),
                )
        else:
            with db() as conn:
                conn.execute(
                    "UPDATE products SET status = ?, error_message = ? WHERE id = ?",
                    (
                        "awaiting-generator",
                        "No 3D generator configured. Set ASHES_3D_COMMAND or drop a matching GLB for development.",
                        product_id,
                    ),
                )
    except Exception as exc:
        with db() as conn:
            conn.execute(
                "UPDATE products SET status = ?, error_message = ? WHERE id = ?",
                ("failed", str(exc)[:600], product_id),
            )


def queue_3d_generation(product_id: str, image_path: Path) -> None:
    threading.Thread(
        target=run_generation_job,
        args=(product_id, image_path),
        daemon=True,
        name=f"ashes-3d-{product_id[:8]}",
    ).start()


@app.get("/health")
def health():
    return {"ok": True, "service": "ashes-api", "version": "0.2.0"}


@app.get("/api/businesses")
def list_businesses():
    with db() as conn:
        rows = conn.execute("SELECT * FROM businesses ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/businesses")
def create_business(payload: BusinessCreate):
    business_id = str(uuid.uuid4())
    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO businesses (id, name, slug, kind, city) VALUES (?, ?, ?, ?, ?)",
                (business_id, payload.name, payload.slug, payload.kind, payload.city),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Business slug already exists") from exc
    return {"id": business_id, **payload.model_dump()}


@app.get("/api/businesses/{business_slug}/products", response_model=list[ProductOut])
def list_products(business_slug: str):
    with db() as conn:
        business = conn.execute("SELECT id FROM businesses WHERE slug = ?", (business_slug,)).fetchone()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        rows = conn.execute(
            "SELECT * FROM products WHERE business_id = ? ORDER BY created_at DESC",
            (business["id"],),
        ).fetchall()
    return [product_from_row(row) for row in rows]


@app.post("/api/businesses/{business_slug}/products", response_model=ProductOut)
async def create_product(
    business_slug: str,
    name: str = Form(...),
    price: float = Form(...),
    category: str = Form("Main"),
    calories: str = Form(""),
    protein: str = Form(""),
    carbs: str = Form(""),
    fat: str = Form(""),
    tags: str = Form(""),
    image: UploadFile = File(...),
):
    with db() as conn:
        business = conn.execute("SELECT id FROM businesses WHERE slug = ?", (business_slug,)).fetchone()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image")

    product_id = str(uuid.uuid4())
    extension = Path(image.filename or "product.jpg").suffix.lower() or ".jpg"
    image_path = UPLOAD_DIR / f"{product_id}{extension}"
    image_path.write_bytes(await image.read())

    public_url = f"{PUBLIC_BASE_URL}/?product={product_id}"
    qr_path = QR_DIR / f"{product_id}.png"
    qrcode.make(public_url).save(qr_path)

    with db() as conn:
        conn.execute(
            """
            INSERT INTO products (
              id, business_id, name, category, price, calories, protein, carbs, fat,
              tags, image_path, status, qr_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                business["id"],
                name,
                category,
                price,
                calories,
                protein,
                carbs,
                fat,
                tags,
                str(image_path),
                "queued",
                str(qr_path),
            ),
        )
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    queue_3d_generation(product_id, image_path)
    return product_from_row(row)


@app.post("/api/products/{product_id}/retry-3d", response_model=ProductOut)
def retry_product_3d(product_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    if not row["image_path"]:
        raise HTTPException(status_code=400, detail="Product has no source image")

    queue_3d_generation(product_id, Path(row["image_path"]))
    return product_from_row(row)


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_from_row(row)


@app.get("/media/uploads/{filename}")
def media_upload(filename: str):
    path = UPLOAD_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


@app.get("/media/models/{filename}")
def media_model(filename: str):
    path = MODEL_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Model not found")
    return FileResponse(path, media_type="model/gltf-binary")


@app.get("/media/qr/{filename}")
def media_qr(filename: str):
    path = QR_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="QR not found")
    return FileResponse(path, media_type="image/png")
