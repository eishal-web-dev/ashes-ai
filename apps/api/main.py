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
from apps.api.menu_import import extract_menu, import_products
from apps.api.orders_patch import create_order as create_order_record, ensure_order_tables, get_order as get_order_record, list_business_orders, list_unnotified_orders, mark_orders_notified, set_order_status
from apps.api.services.three_d import MODEL_DIR, generate_3d
from apps.api.table_qr_patch import create_table_qr, ensure_table_qr_table, list_table_qrs

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
QR_DIR = DATA_DIR / "qr"
LOGO_DIR = DATA_DIR / "logos"
MENU_IMPORT_DIR = DATA_DIR / "menu-imports"
DB_PATH = DATA_DIR / "ashes.db"
PUBLIC_BASE_URL = os.getenv("ASHES_PUBLIC_BASE_URL", "http://localhost:5173")
API_BASE_URL = os.getenv("ASHES_API_BASE_URL", "http://localhost:8000")

for directory in (DATA_DIR, UPLOAD_DIR, QR_DIR, MODEL_DIR, LOGO_DIR, MENU_IMPORT_DIR): directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Ashes AI API", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or f"business-{uuid.uuid4().hex[:6]}"

def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS businesses (id TEXT PRIMARY KEY,owner_user_id TEXT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL,kind TEXT NOT NULL DEFAULT 'restaurant',city TEXT,phone TEXT,instagram TEXT,website TEXT,accent_color TEXT DEFAULT '#ff2f9f',logo_path TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(owner_user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY,business_id TEXT NOT NULL,name TEXT NOT NULL,category TEXT,price REAL NOT NULL,calories TEXT,protein TEXT,carbs TEXT,fat TEXT,tags TEXT,image_path TEXT,model_path TEXT,status TEXT NOT NULL DEFAULT 'queued',error_message TEXT,qr_code TEXT,is_published INTEGER NOT NULL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(business_id) REFERENCES businesses(id));
        CREATE TABLE IF NOT EXISTS menu_imports (id TEXT PRIMARY KEY,business_id TEXT NOT NULL,image_path TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'processing',items_found INTEGER NOT NULL DEFAULT 0,error_message TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(business_id) REFERENCES businesses(id));
        """)
        ensure_analytics_table(conn); ensure_order_tables(conn); ensure_table_qr_table(conn)
        business_columns={row[1] for row in conn.execute("PRAGMA table_info(businesses)").fetchall()}
        for name, definition in {"owner_user_id":"TEXT", "phone":"TEXT", "instagram":"TEXT", "website":"TEXT", "accent_color":"TEXT DEFAULT '#ff2f9f'", "logo_path":"TEXT"}.items():
            if name not in business_columns: conn.execute(f"ALTER TABLE businesses ADD COLUMN {name} {definition}")
        product_columns={row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
        if "error_message" not in product_columns: conn.execute("ALTER TABLE products ADD COLUMN error_message TEXT")
        if "is_published" not in product_columns: conn.execute("ALTER TABLE products ADD COLUMN is_published INTEGER NOT NULL DEFAULT 0")
        demo=conn.execute("SELECT id FROM businesses WHERE slug=?",("neon-bites",)).fetchone()
        if not demo: conn.execute("INSERT INTO businesses (id,name,slug,kind,city) VALUES (?,?,?,?,?)",(str(uuid.uuid4()),"Neon Bites","neon-bites","restaurant","Peshawar"))

init_db()

class SignupPayload(BaseModel): owner_name:str; email:str; password:str; business_name:str; kind:str="restaurant"; city:Optional[str]=None
class LoginPayload(BaseModel): email:str; password:str
class BusinessCreate(BaseModel): name:str; slug:Optional[str]=None; kind:str="restaurant"; city:Optional[str]=None
class BusinessUpdatePayload(BaseModel): name:Optional[str]=None; kind:Optional[str]=None; city:Optional[str]=None; phone:Optional[str]=None; instagram:Optional[str]=None; website:Optional[str]=None; accent_color:Optional[str]=None
class AnalyticsEventPayload(BaseModel): event_type:str
class OrderItemPayload(BaseModel): product_id:str; quantity:int=1
class OrderCreatePayload(BaseModel): items:list[OrderItemPayload]; table_code:Optional[str]=None; customer_name:Optional[str]=None; notes:Optional[str]=None
class OrderStatusPayload(BaseModel): status:str
class TableQrPayload(BaseModel): table_code:str; product_id:Optional[str]=None
class ProductUpdatePayload(BaseModel): name:Optional[str]=None; category:Optional[str]=None; price:Optional[float]=None; calories:Optional[str]=None; protein:Optional[str]=None; carbs:Optional[str]=None; fat:Optional[str]=None; tags:Optional[str]=None; is_published:Optional[bool]=None
class ProductOut(BaseModel): id:str; business_id:str; name:str; category:Optional[str]=None; price:float; calories:Optional[str]=None; protein:Optional[str]=None; carbs:Optional[str]=None; fat:Optional[str]=None; tags:list[str]=[]; image_url:Optional[str]=None; model_url:Optional[str]=None; status:str; error_message:Optional[str]=None; qr_url:Optional[str]=None; public_url:str; scans:int=0; views_3d:int=0; ar_launches:int=0; is_published:bool=False

def business_from_row(row: sqlite3.Row) -> dict:
    data=dict(row); data["logo_url"]=f"{API_BASE_URL}/media/logos/{Path(row['logo_path']).name}" if row["logo_path"] else None; data.pop("logo_path",None); return data

def product_from_row(row: sqlite3.Row) -> ProductOut:
    public_url=f"{PUBLIC_BASE_URL}/?product={row['id']}"
    with db() as conn: metrics=product_metrics(conn,row["id"])
    return ProductOut(id=row["id"],business_id=row["business_id"],name=row["name"],category=row["category"],price=row["price"],calories=row["calories"],protein=row["protein"],carbs=row["carbs"],fat=row["fat"],tags=[x.strip() for x in (row["tags"] or "").split(",") if x.strip()],image_url=f"{API_BASE_URL}/media/uploads/{Path(row['image_path']).name}" if row["image_path"] else None,model_url=f"{API_BASE_URL}/media/models/{Path(row['model_path']).name}" if row["model_path"] else None,status=row["status"],error_message=row["error_message"],qr_url=f"{API_BASE_URL}/media/qr/{Path(row['qr_code']).name}" if row["qr_code"] else None,public_url=public_url,is_published=bool(row["is_published"]),**metrics)

def auth_user(authorization:Optional[str]=Header(None))->sqlite3.Row:
    if not authorization or not authorization.lower().startswith("bearer "): raise HTTPException(status_code=401,detail="Authentication required")
    user_id=decode_token(authorization.split(" ",1)[1].strip())
    if not user_id: raise HTTPException(status_code=401,detail="Invalid or expired token")
    with db() as conn: user=conn.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone()
    if not user: raise HTTPException(status_code=401,detail="User not found")
    return user

def owned_business(user_id:str,business_slug:str)->sqlite3.Row:
    with db() as conn: business=conn.execute("SELECT * FROM businesses WHERE slug=? AND owner_user_id=?",(business_slug,user_id)).fetchone()
    if not business: raise HTTPException(status_code=404,detail="Business not found for this account")
    return business

def unique_slug(conn:sqlite3.Connection,name:str)->str:
    base=slugify(name); candidate=base; n=2
    while conn.execute("SELECT 1 FROM businesses WHERE slug=?",(candidate,)).fetchone(): candidate=f"{base}-{n}"; n+=1
    return candidate

def run_generation_job(product_id:str,image_path:Path)->None:
    with db() as conn: conn.execute("UPDATE products SET status=?,error_message=NULL WHERE id=?",("processing",product_id))
    try:
        model_path=generate_3d(product_id,image_path)
        if model_path:
            with db() as conn: conn.execute("UPDATE products SET model_path=?,status=?,error_message=NULL WHERE id=?",(str(model_path),"ready",product_id))
        else:
            with db() as conn: conn.execute("UPDATE products SET status=?,error_message=? WHERE id=?",("awaiting-generator","No 3D generator configured. Set ASHES_3D_COMMAND or drop a matching GLB for development.",product_id))
    except Exception as exc:
        with db() as conn: conn.execute("UPDATE products SET status=?,error_message=? WHERE id=?",("failed",str(exc)[:600],product_id))

def queue_3d_generation(product_id:str,image_path:Path)->None:
    threading.Thread(target=run_generation_job,args=(product_id,image_path),daemon=True,name=f"ashes-3d-{product_id[:8]}").start()

@app.get("/health")
def health(): return {"ok":True,"service":"ashes-api","version":"1.2.0"}

@app.post("/api/auth/signup")
def signup(payload:SignupPayload):
    email=payload.email.strip().lower()
    if "@" not in email: raise HTTPException(status_code=400,detail="Enter a valid email")
    if len(payload.password)<8: raise HTTPException(status_code=400,detail="Password must be at least 8 characters")
    user_id=str(uuid.uuid4()); business_id=str(uuid.uuid4())
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone(): raise HTTPException(status_code=409,detail="Account already exists")
        slug=unique_slug(conn,payload.business_name)
        conn.execute("INSERT INTO users (id,email,password_hash,name) VALUES (?,?,?,?)",(user_id,email,hash_password(payload.password),payload.owner_name.strip()))
        conn.execute("INSERT INTO businesses (id,owner_user_id,name,slug,kind,city) VALUES (?,?,?,?,?,?)",(business_id,user_id,payload.business_name.strip(),slug,payload.kind,payload.city))
        business=conn.execute("SELECT * FROM businesses WHERE id=?",(business_id,)).fetchone()
    return {"token":issue_token(user_id),"user":{"id":user_id,"email":email,"name":payload.owner_name},"business":business_from_row(business)}

@app.post("/api/auth/login")
def login(payload:LoginPayload):
    email=payload.email.strip().lower()
    with db() as conn:
        user=conn.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if not user or not verify_password(payload.password,user["password_hash"]): raise HTTPException(status_code=401,detail="Invalid email or password")
        business=conn.execute("SELECT * FROM businesses WHERE owner_user_id=? ORDER BY created_at LIMIT 1",(user["id"],)).fetchone()
    return {"token":issue_token(user["id"]),"user":{"id":user["id"],"email":user["email"],"name":user["name"]},"business":business_from_row(business) if business else None}

@app.get("/api/auth/me")
def me(user:sqlite3.Row=Depends(auth_user)):
    with db() as conn: businesses=conn.execute("SELECT * FROM businesses WHERE owner_user_id=? ORDER BY created_at",(user["id"],)).fetchall()
    return {"user":{"id":user["id"],"email":user["email"],"name":user["name"]},"businesses":[business_from_row(x) for x in businesses]}

@app.get("/api/businesses")
def list_businesses():
    with db() as conn: rows=conn.execute("SELECT * FROM businesses ORDER BY created_at DESC").fetchall()
    return [business_from_row(row) for row in rows]

@app.get("/api/businesses/{business_slug}")
def get_business_profile(business_slug:str):
    with db() as conn: row=conn.execute("SELECT * FROM businesses WHERE slug=?",(business_slug,)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Business not found")
    return business_from_row(row)

@app.post("/api/businesses")
def create_business(payload:BusinessCreate,user:sqlite3.Row=Depends(auth_user)):
    business_id=str(uuid.uuid4())
    with db() as conn:
        slug=slugify(payload.slug or payload.name)
        if conn.execute("SELECT 1 FROM businesses WHERE slug=?",(slug,)).fetchone(): slug=unique_slug(conn,payload.name)
        conn.execute("INSERT INTO businesses (id,owner_user_id,name,slug,kind,city) VALUES (?,?,?,?,?,?)",(business_id,user["id"],payload.name,slug,payload.kind,payload.city))
        row=conn.execute("SELECT * FROM businesses WHERE id=?",(business_id,)).fetchone()
    return business_from_row(row)

@app.patch("/api/businesses/{business_slug}")
def update_business_profile(business_slug:str,payload:BusinessUpdatePayload,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); updates=[]; values=[]
    for field in ("name","kind","city","phone","instagram","website","accent_color"):
        value=getattr(payload,field)
        if value is not None:
            if field=="accent_color" and not re.fullmatch(r"#[0-9a-fA-F]{6}",value): raise HTTPException(status_code=400,detail="Accent color must be a hex color")
            updates.append(f"{field}=?"); values.append(value.strip() if isinstance(value,str) else value)
    if updates:
        values.append(business["id"])
        with db() as conn:
            conn.execute(f"UPDATE businesses SET {', '.join(updates)} WHERE id=?",values); row=conn.execute("SELECT * FROM businesses WHERE id=?",(business["id"],)).fetchone()
    else: row=business
    return business_from_row(row)

@app.post("/api/businesses/{business_slug}/logo")
async def upload_business_logo(business_slug:str,logo:UploadFile=File(...),user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    if not logo.content_type or not logo.content_type.startswith("image/"): raise HTTPException(status_code=400,detail="Logo must be an image")
    extension=Path(logo.filename or "logo.png").suffix.lower() or ".png"; path=LOGO_DIR/f"{business['id']}{extension}"; path.write_bytes(await logo.read())
    with db() as conn:
        conn.execute("UPDATE businesses SET logo_path=? WHERE id=?",(str(path),business["id"])); row=conn.execute("SELECT * FROM businesses WHERE id=?",(business["id"],)).fetchone()
    return business_from_row(row)

@app.post("/api/businesses/{business_slug}/import-menu-card")
async def import_menu_card(business_slug:str,image:UploadFile=File(...),user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400,detail="Menu card must be an image")
    import_id=str(uuid.uuid4()); extension=Path(image.filename or "menu.jpg").suffix.lower() or ".jpg"; image_path=MENU_IMPORT_DIR/f"{import_id}{extension}"; image_path.write_bytes(await image.read())
    with db() as conn:
        conn.execute("INSERT INTO menu_imports (id,business_id,image_path,status) VALUES (?,?,?,'processing')",(import_id,business["id"],str(image_path)))
    try:
        extracted=extract_menu(image_path)
        items=extracted.get("items") or []
        if not items: raise ValueError("No menu items were detected")
        with db() as conn:
            import_result=import_products(conn,business["id"],items,PUBLIC_BASE_URL,QR_DIR)
            created_ids=import_result.get("created_ids",[])
            skipped_duplicates=import_result.get("skipped_duplicates",[])
            review_items=import_result.get("review_items",[])
            detected_business=extracted.get("business") or {}
            updates=[]; values=[]
            for field in ("phone","instagram","website","city"):
                value=(detected_business.get(field) or "").strip()
                if value and not business[field]: updates.append(f"{field}=?"); values.append(value)
            detected_name=(detected_business.get("name") or "").strip()
            if detected_name and (not business["name"] or business["name"].lower() in {"my business","your business"}): updates.append("name=?"); values.append(detected_name)
            if updates:
                values.append(business["id"]); conn.execute(f"UPDATE businesses SET {', '.join(updates)} WHERE id=?",values)
            conn.execute("UPDATE menu_imports SET status='completed',items_found=?,error_message=NULL WHERE id=?",(len(created_ids),import_id))
            profile=conn.execute("SELECT * FROM businesses WHERE id=?",(business["id"],)).fetchone()
            if created_ids:
                placeholders=','.join(['?']*len(created_ids)); rows=conn.execute(f"SELECT * FROM products WHERE id IN ({placeholders}) ORDER BY created_at DESC",created_ids).fetchall()
            else: rows=[]
        return {"import_id":import_id,"status":"completed","items_found":len(created_ids),"detected_items":len(items),"duplicates_skipped":len(skipped_duplicates),"duplicate_names":skipped_duplicates,"review_items":review_items,"business":business_from_row(profile),"products":[product_from_row(row) for row in rows],"review_required":True}
    except Exception as exc:
        with db() as conn: conn.execute("UPDATE menu_imports SET status='failed',error_message=? WHERE id=?",(str(exc)[:800],import_id))
        raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.get("/api/businesses/{business_slug}/menu-imports")
def get_menu_imports(business_slug:str,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn: rows=conn.execute("SELECT id,status,items_found,error_message,created_at FROM menu_imports WHERE business_id=? ORDER BY created_at DESC LIMIT 20",(business["id"],)).fetchall()
    return [dict(row) for row in rows]

@app.get("/api/businesses/{business_slug}/products",response_model=list[ProductOut])
def list_products(business_slug:str,include_unpublished:bool=False,authorization:Optional[str]=Header(None)):
    with db() as conn:
        business=conn.execute("SELECT * FROM businesses WHERE slug=?",(business_slug,)).fetchone()
        if not business: raise HTTPException(status_code=404,detail="Business not found")
        allow_all=False
        if include_unpublished and authorization and authorization.lower().startswith("bearer "):
            user_id=decode_token(authorization.split(" ",1)[1].strip()); allow_all=bool(user_id and business["owner_user_id"]==user_id)
        sql="SELECT * FROM products WHERE business_id=?" + ("" if allow_all else " AND is_published=1") + " ORDER BY created_at DESC"; rows=conn.execute(sql,(business["id"],)).fetchall()
    return [product_from_row(row) for row in rows]

@app.get("/api/businesses/{business_slug}/analytics")
def get_business_analytics(business_slug:str,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn:
        totals=business_metrics(conn,business["id"])
        rows=conn.execute("SELECT p.*, SUM(CASE WHEN ae.event_type='scan' THEN 1 ELSE 0 END) AS scans, SUM(CASE WHEN ae.event_type='view_3d' THEN 1 ELSE 0 END) AS views_3d, SUM(CASE WHEN ae.event_type='ar_launch' THEN 1 ELSE 0 END) AS ar_launches FROM products p LEFT JOIN analytics_events ae ON ae.product_id=p.id WHERE p.business_id=? GROUP BY p.id ORDER BY p.created_at DESC",(business["id"],)).fetchall()
    return {"business_id":business["id"],**totals,"products":[{"id":row["id"],"name":row["name"],"scans":int(row["scans"] or 0),"views_3d":int(row["views_3d"] or 0),"ar_launches":int(row["ar_launches"] or 0)} for row in rows]}

@app.get("/api/businesses/{business_slug}/orders")
def get_orders(business_slug:str,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn: return list_business_orders(conn,business["id"])

@app.get("/api/businesses/{business_slug}/order-notifications")
def get_order_notifications(business_slug:str,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn:
        orders=list_unnotified_orders(conn,business["id"]); mark_orders_notified(conn,[o["id"] for o in orders])
    return orders

@app.patch("/api/businesses/{business_slug}/orders/{order_id}")
def update_order_status(business_slug:str,order_id:str,payload:OrderStatusPayload,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); allowed={"new","accepted","preparing","ready","served","cancelled"}
    if payload.status not in allowed: raise HTTPException(status_code=400,detail="Invalid status")
    with db() as conn:
        row=conn.execute("SELECT id FROM orders WHERE id=? AND business_id=?",(order_id,business["id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="Order not found")
        return set_order_status(conn,order_id,payload.status)

@app.get("/api/businesses/{business_slug}/table-qrs")
def get_table_qrs(business_slug:str,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn: rows=list_table_qrs(conn,business["id"])
    return [{**row,"qr_url":f"{API_BASE_URL}/media/qr/{Path(row['qr_path']).name}"} for row in rows]

@app.post("/api/businesses/{business_slug}/table-qrs")
def add_table_qr(business_slug:str,payload:TableQrPayload,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn:
        if payload.product_id:
            product=conn.execute("SELECT id FROM products WHERE id=? AND business_id=? AND is_published=1",(payload.product_id,business["id"])).fetchone()
            if not product: raise HTTPException(status_code=404,detail="Published product not found for this business")
        try: row=create_table_qr(conn,business["id"],payload.table_code,QR_DIR,PUBLIC_BASE_URL,payload.product_id,business["slug"])
        except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc
    return {**row,"qr_url":f"{API_BASE_URL}/media/qr/{Path(row['qr_path']).name}"}

@app.post("/api/businesses/{business_slug}/products",response_model=ProductOut)
async def create_product(business_slug:str,name:str=Form(...),price:float=Form(...),category:str=Form("Main"),calories:str=Form(""),protein:str=Form(""),carbs:str=Form(""),fat:str=Form(""),tags:str=Form(""),image:UploadFile=File(...),user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    if not image.content_type or not image.content_type.startswith("image/"): raise HTTPException(status_code=400,detail="Upload must be an image")
    product_id=str(uuid.uuid4()); extension=Path(image.filename or "product.jpg").suffix.lower() or ".jpg"; image_path=UPLOAD_DIR/f"{product_id}{extension}"; image_path.write_bytes(await image.read())
    public_url=f"{PUBLIC_BASE_URL}/?product={product_id}"; qr_path=QR_DIR/f"{product_id}.png"; qrcode.make(public_url).save(qr_path)
    with db() as conn:
        conn.execute("INSERT INTO products (id,business_id,name,category,price,calories,protein,carbs,fat,tags,image_path,status,qr_code,is_published) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)",(product_id,business["id"],name,category,price,calories,protein,carbs,fat,tags,str(image_path),"queued",str(qr_path)))
        row=conn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone()
    queue_3d_generation(product_id,image_path); return product_from_row(row)

@app.post("/api/businesses/{business_slug}/products/{product_id}/photo",response_model=ProductOut)
async def attach_product_photo(business_slug:str,product_id:str,image:UploadFile=File(...),user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400,detail="Product photo must be an image")
    with db() as conn:
        row=conn.execute("SELECT * FROM products WHERE id=? AND business_id=?",(product_id,business["id"])).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Product not found")
    extension=Path(image.filename or "product.jpg").suffix.lower() or ".jpg"
    image_path=UPLOAD_DIR/f"{product_id}{extension}"
    image_path.write_bytes(await image.read())
    old_image=row["image_path"]; old_model=row["model_path"]
    if old_image and Path(old_image)!=image_path:
        try: Path(old_image).unlink(missing_ok=True)
        except OSError: pass
    if old_model:
        try: Path(old_model).unlink(missing_ok=True)
        except OSError: pass
    with db() as conn:
        conn.execute("UPDATE products SET image_path=?,model_path=NULL,status='queued',error_message=NULL WHERE id=? AND business_id=?",(str(image_path),product_id,business["id"]))
        updated=conn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone()
    queue_3d_generation(product_id,image_path)
    return product_from_row(updated)

@app.patch("/api/businesses/{business_slug}/products/{product_id}",response_model=ProductOut)
def update_product(business_slug:str,product_id:str,payload:ProductUpdatePayload,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); updates=[]; values=[]
    for field in ("name","category","price","calories","protein","carbs","fat"):
        value=getattr(payload,field)
        if value is not None: updates.append(f"{field}=?"); values.append(value)
    if payload.tags is not None: updates.append("tags=?"); values.append(payload.tags)
    if payload.is_published is not None: updates.append("is_published=?"); values.append(1 if payload.is_published else 0)
    if not updates:
        with db() as conn: row=conn.execute("SELECT * FROM products WHERE id=? AND business_id=?",(product_id,business["id"])).fetchone()
    else:
        values.extend([product_id,business["id"]])
        with db() as conn:
            conn.execute(f"UPDATE products SET {', '.join(updates)} WHERE id=? AND business_id=?",values); row=conn.execute("SELECT * FROM products WHERE id=? AND business_id=?",(product_id,business["id"])).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Product not found")
    return product_from_row(row)

@app.delete("/api/businesses/{business_slug}/products/{product_id}")
def delete_product(business_slug:str,product_id:str,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn:
        row=conn.execute("SELECT * FROM products WHERE id=? AND business_id=?",(product_id,business["id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="Product not found")
        conn.execute("DELETE FROM analytics_events WHERE product_id=?",(product_id,)); conn.execute("DELETE FROM products WHERE id=?",(product_id,))
    for key in ("image_path","model_path","qr_code"):
        path=row[key]
        if path:
            try: Path(path).unlink(missing_ok=True)
            except OSError: pass
    return {"ok":True}

@app.get("/api/businesses/{business_slug}/products/{product_id}",response_model=ProductOut)
def get_owned_product(business_slug:str,product_id:str,user:sqlite3.Row=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    with db() as conn: row=conn.execute("SELECT * FROM products WHERE id=? AND business_id=?",(product_id,business["id"])).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Product not found")
    return product_from_row(row)

@app.post("/api/products/{product_id}/analytics")
def track_analytics(product_id:str,payload:AnalyticsEventPayload):
    if payload.event_type not in {"scan","view_3d","ar_launch"}: raise HTTPException(status_code=400,detail="Unsupported analytics event")
    with db() as conn:
        row=conn.execute("SELECT business_id,is_published FROM products WHERE id=?",(product_id,)).fetchone()
        if not row or not row["is_published"]: raise HTTPException(status_code=404,detail="Product not found")
        record_event(conn,product_id,row["business_id"],payload.event_type)
    return {"ok":True}

@app.post("/api/orders")
def create_order(payload:OrderCreatePayload):
    if not payload.items: raise HTTPException(status_code=400,detail="Order needs at least one item")
    with db() as conn:
        first=conn.execute("SELECT business_id,is_published FROM products WHERE id=?",(payload.items[0].product_id,)).fetchone()
        if not first or not first["is_published"]: raise HTTPException(status_code=400,detail="Product is unavailable")
        try: return create_order_record(conn,first["business_id"],[item.model_dump() for item in payload.items],payload.table_code,payload.customer_name,payload.notes)
        except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.get("/api/orders/{order_id}")
def get_order(order_id:str):
    with db() as conn: order=get_order_record(conn,order_id)
    if not order: raise HTTPException(status_code=404,detail="Order not found")
    return order

@app.post("/api/products/{product_id}/retry-3d",response_model=ProductOut)
def retry_product_3d(product_id:str,user:sqlite3.Row=Depends(auth_user)):
    with db() as conn: row=conn.execute("SELECT p.* FROM products p JOIN businesses b ON b.id=p.business_id WHERE p.id=? AND b.owner_user_id=?",(product_id,user["id"])).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Product not found")
    if not row["image_path"]: raise HTTPException(status_code=400,detail="Product has no source image")
    queue_3d_generation(product_id,Path(row["image_path"])); return product_from_row(row)

@app.get("/api/products/{product_id}/business")
def get_product_business(product_id:str):
    with db() as conn:
        row=conn.execute("SELECT b.* FROM businesses b JOIN products p ON p.business_id=b.id WHERE p.id=? AND p.is_published=1",(product_id,)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Business not found")
    return business_from_row(row)

@app.get("/api/products/{product_id}",response_model=ProductOut)
def get_product(product_id:str):
    with db() as conn: row=conn.execute("SELECT * FROM products WHERE id=? AND is_published=1",(product_id,)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Product not found")
    return product_from_row(row)

@app.get("/media/uploads/{filename}")
def media_upload(filename:str):
    path=UPLOAD_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(status_code=404,detail="File not found")
    return FileResponse(path)

@app.get("/media/models/{filename}")
def media_model(filename:str):
    path=MODEL_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(status_code=404,detail="Model not found")
    return FileResponse(path,media_type="model/gltf-binary")

@app.get("/media/qr/{filename}")
def media_qr(filename:str):
    path=QR_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(status_code=404,detail="QR not found")
    return FileResponse(path,media_type="image/png")

@app.get("/media/logos/{filename}")
def media_logo(filename:str):
    path=LOGO_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(status_code=404,detail="Logo not found")
    return FileResponse(path)