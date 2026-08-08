from __future__ import annotations

import os
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from apps.api.analytics_patch import business_metrics, ensure_analytics_table, product_metrics, record_event
from apps.api.auth import decode_token, hash_password, issue_token, verify_password
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

app = FastAPI(title="Ashes AI API", version="0.4.0")
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


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or f"business-{uuid.uuid4().hex[:6]}"


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              email TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              name TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS businesses (
              id TEXT PRIMARY KEY,
              owner_user_id TEXT,
              name TEXT NOT NULL,
              slug TEXT UNIQUE NOT NULL,
              kind TEXT NOT NULL DEFAULT 'restaurant',
              city TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(owner_user_id) REFERENCES users(id)
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
        ensure_analytics_table(conn)

        business_columns = {row[1] for row in conn.execute("PRAGMA table_info(businesses)").fetchall()}
        if "owner_user_id" not in business_columns:
            conn.execute("ALTER TABLE businesses ADD COLUMN owner_user_id TEXT")

        product_columns = {row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
        if "error_message" not in product_columns:
            conn.execute("ALTER TABLE products ADD COLUMN error_message TEXT")

        demo = conn.execute("SELECT id FROM businesses WHERE slug = ?", ("neon-bites",)).fetchone()
        if not demo:
            conn.execute(
                "INSERT INTO businesses (id, name, slug, kind, city) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "Neon Bites", "neon-bites", "restaurant", "Peshawar"),
            )


init_db()


class SignupPayload(BaseModel):
    owner_name: str
    email: str
    password: str
    business_name: str
    kind: str = "restaurant"
    city: Optional[str] = None


class LoginPayload(BaseModel):
    email: str
    password: str


class BusinessCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    kind: str = "restaurant"
    city: Optional[str] = None


class AnalyticsEventPayload(BaseModel):
    event_type: str


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
    scans: int = 0
    views_3d: int = 0
    ar_launches: int = 0


def product_from_row(row: sqlite3.Row) -> ProductOut:
    public_url = f"{PUBLIC_BASE_URL}/?product={row['id']}"
    with db() as conn:
        metrics = product_metrics(conn, row["id"])
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
        **metrics,
    )


def auth_user(authorization: Optional[str] = Header(None)) -> sqlite3.Row:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    user_id = decode_token(authorization.split(" ", 1)[1].strip())
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def owned_business(user_id: str, business_slug: str) -> sqlite3.Row:
    with db() as conn:
        business = conn.execute(
            "SELECT * FROM businesses WHERE slug = ? AND owner_user_id = ?",
            (business_slug, user_id),
        ).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found for this account")
    return business


def unique_slug(conn: sqlite3.Connection, name: str) -> str:
    base = slugify(name)
    candidate = base
    n = 2
    while conn.execute("SELECT 1 FROM businesses WHERE slug = ?", (candidate,)).fetchone():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def run_generation_job(product_id: str, image_path: Path) -> None:
    with db() as conn:
        conn.execute("UPDATE products SET status = ?, error_message = NULL WHERE id = ?", ("processing", product_id))
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
                    ("awaiting-generator", "No 3D generator configured. Set ASHES_3D_COMMAND or drop a matching GLB for development.", product_id),
                )
    except Exception as exc:
        with db() as conn:
            conn.execute("UPDATE products SET status = ?, error_message = ? WHERE id = ?", ("failed", str(exc)[:600], product_id))


def queue_3d_generation(product_id: str, image_path: Path) -> None:
    threading.Thread(target=run_generation_job, args=(product_id, image_path), daemon=True, name=f"ashes-3d-{product_id[:8]}").start()


@app.get("/health")
def health():
    return {"ok": True, "service": "ashes-api", "version": "0.4.0"}


@app.post("/api/auth/signup")
def signup(payload: SignupPayload):
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user_id = str(uuid.uuid4())
    business_id = str(uuid.uuid4())
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="Account already exists")
        slug = unique_slug(conn, payload.business_name)
        conn.execute(
            "INSERT INTO users (id, email, password_hash, name) VALUES (?, ?, ?, ?)",
            (user_id, email, hash_password(payload.password), payload.owner_name.strip()),
        )
        conn.execute(
            "INSERT INTO businesses (id, owner_user_id, name, slug, kind, city) VALUES (?, ?, ?, ?, ?, ?)",
            (business_id, user_id, payload.business_name.strip(), slug, payload.kind, payload.city),
        )
        business = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()

    return {"token": issue_token(user_id), "user": {"id": user_id, "email": email, "name": payload.owner_name}, "business": dict(business)}


@app.post("/api/auth/login")
def login(payload: LoginPayload):
    email = payload.email.strip().lower()
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        business = conn.execute("SELECT * FROM businesses WHERE owner_user_id = ? ORDER BY created_at LIMIT 1", (user["id"],)).fetchone()
    return {"token": issue_token(user["id"]), "user": {"id": user["id"], "email": user["email"], "name": user["name"]}, "business": dict(business) if business else None}


@app.get("/api/auth/me")
def me(user: sqlite3.Row = Depends(auth_user)):
    with db() as conn:
        businesses = conn.execute("SELECT * FROM businesses WHERE owner_user_id = ? ORDER BY created_at", (user["id"],)).fetchall()
    return {"user": {"id": user["id"], "email": user["email"], "name": user["name"]}, "businesses": [dict(x) for x in businesses]}


@app.get("/api/businesses")
def list_businesses():
    with db() as conn:
        rows = conn.execute("SELECT id, name, slug, kind, city, created_at FROM businesses ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/businesses")
def create_business(payload: BusinessCreate, user: sqlite3.Row = Depends(auth_user)):
    business_id = str(uuid.uuid4())
    with db() as conn:
        slug = slugify(payload.slug or payload.name)
        if conn.execute("SELECT 1 FROM businesses WHERE slug = ?", (slug,)).fetchone():
            slug = unique_slug(conn, payload.name)
        conn.execute(
            "INSERT INTO businesses (id, owner_user_id, name, slug, kind, city) VALUES (?, ?, ?, ?, ?, ?)",
            (business_id, user["id"], payload.name, slug, payload.kind, payload.city),
        )
        row = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    return dict(row)


@app.get("/api/businesses/{business_slug}/products", response_model=list[ProductOut])
def list_products(business_slug: str):
    with db() as conn:
        business = conn.execute("SELECT id FROM businesses WHERE slug = ?", (business_slug,)).fetchone()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        rows = conn.execute("SELECT * FROM products WHERE business_id = ? ORDER BY created_at DESC", (business["id"],)).fetchall()
    return [product_from_row(row) for row in rows]


@app.get("/api/businesses/{business_slug}/analytics")
def get_business_analytics(business_slug: str, user: sqlite3.Row = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    with db() as conn:
        totals = business_metrics(conn, business["id"])
        rows = conn.execute(
            """
            SELECT p.*, 
              SUM(CASE WHEN ae.event_type='scan' THEN 1 ELSE 0 END) AS scans,
              SUM(CASE WHEN ae.event_type='view_3d' THEN 1 ELSE 0 END) AS views_3d,
              SUM(CASE WHEN ae.event_type='ar_launch' THEN 1 ELSE 0 END) AS ar_launches
            FROM products p
            LEFT JOIN analytics_events ae ON ae.product_id=p.id
            WHERE p.business_id=?
            GROUP BY p.id
            ORDER BY p.created_at DESC
            """,
            (business["id"],),
        ).fetchall()
    return {
        "business_id": business["id"],
        **totals,
        "products": [
            {
                "id": row["id"],
                "name": row["name"],
                "scans": int(row["scans"] or 0),
                "views_3d": int(row["views_3d"] or 0),
                "ar_launches": int(row["ar_launches"] or 0),
            }
            for row in rows
        ],
    }


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
    user: sqlite3.Row = Depends(auth_user),
):
    business = owned_business(user["id"], business_slug)
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
            (product_id, business["id"], name, category, price, calories, protein, carbs, fat, tags, str(image_path), "queued", str(qr_path)),
        )
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    queue_3d_generation(product_id, image_path)
    return product_from_row(row)


@app.post("/api/products/{product_id}/analytics")
def add_product_analytics(product_id: str, payload: AnalyticsEventPayload):
    with db() as conn:
        product = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        try:
            record_event(conn, product_id, payload.event_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metrics = product_metrics(conn, product_id)
    return {"ok": True, "product_id": product_id, **metrics}


@app.post("/api/products/{product_id}/retry-3d", response_model=ProductOut)
def retry_product_3d(product_id: str, user: sqlite3.Row = Depends(auth_user)):
    with db() as conn:
        row = conn.execute(
            "SELECT p.* FROM products p JOIN businesses b ON b.id=p.business_id WHERE p.id = ? AND b.owner_user_id = ?",
            (product_id, user["id"]),
        ).fetchone()
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
