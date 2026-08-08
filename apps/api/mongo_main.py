from __future__ import annotations

import os
import re
import threading
import uuid
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from apps.api.auth import decode_token, hash_password, issue_token, verify_password
from apps.api.menu_import import extract_menu
from apps.api.mongo_db import (
    business_metrics, collection, create_business as mongo_create_business, create_menu_import,
    create_order as mongo_create_order, create_product as mongo_create_product,
    create_table_qr as mongo_create_table_qr, create_user, delete_product as mongo_delete_product,
    find_duplicate_product, get_business_by_id, get_business_by_slug, get_order as mongo_get_order,
    get_product as mongo_get_product, get_user, get_user_by_email, init_mongo, list_business_orders,
    list_menu_imports, list_products as mongo_list_products, list_table_qrs as mongo_list_table_qrs,
    list_unnotified_orders, list_user_businesses, mark_orders_notified, product_metrics,
    record_analytics, set_order_status as mongo_set_order_status, update_business, update_menu_import,
    update_product as mongo_update_product,
)
from apps.api.services.three_d import MODEL_DIR, generate_3d

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
QR_DIR = DATA_DIR / "qr"
LOGO_DIR = DATA_DIR / "logos"
MENU_IMPORT_DIR = DATA_DIR / "menu-imports"
PUBLIC_BASE_URL = os.getenv("ASHES_PUBLIC_BASE_URL", "http://localhost:5173")
API_BASE_URL = os.getenv("ASHES_API_BASE_URL", "http://localhost:8000")
for directory in (DATA_DIR, UPLOAD_DIR, QR_DIR, MODEL_DIR, LOGO_DIR, MENU_IMPORT_DIR): directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Ashes AI API", version="1.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
init_mongo()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or f"business-{uuid.uuid4().hex[:6]}"


def unique_slug(name: str) -> str:
    base = slugify(name); candidate = base; n = 2
    while get_business_by_slug(candidate): candidate = f"{base}-{n}"; n += 1
    return candidate


class SignupPayload(BaseModel): owner_name:str; email:str; password:str; business_name:str; kind:str="restaurant"; city:Optional[str]=None
class LoginPayload(BaseModel): email:str; password:str
class BusinessUpdatePayload(BaseModel): name:Optional[str]=None; kind:Optional[str]=None; city:Optional[str]=None; phone:Optional[str]=None; instagram:Optional[str]=None; website:Optional[str]=None; accent_color:Optional[str]=None
class AnalyticsEventPayload(BaseModel): event_type:str
class OrderItemPayload(BaseModel): product_id:str; quantity:int=1
class OrderCreatePayload(BaseModel): items:list[OrderItemPayload]; table_code:Optional[str]=None; customer_name:Optional[str]=None; notes:Optional[str]=None
class OrderStatusPayload(BaseModel): status:str
class TableQrPayload(BaseModel): table_code:str; product_id:Optional[str]=None
class ProductUpdatePayload(BaseModel): name:Optional[str]=None; category:Optional[str]=None; price:Optional[float]=None; calories:Optional[str]=None; protein:Optional[str]=None; carbs:Optional[str]=None; fat:Optional[str]=None; tags:Optional[str]=None; is_published:Optional[bool]=None


def auth_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "): raise HTTPException(401, "Authentication required")
    user_id = decode_token(authorization.split(" ",1)[1].strip())
    user = get_user(user_id) if user_id else None
    if not user: raise HTTPException(401, "Invalid or expired token")
    return user


def owned_business(user_id: str, slug: str) -> dict:
    business = get_business_by_slug(slug)
    if not business or business.get("owner_user_id") != user_id: raise HTTPException(404, "Business not found for this account")
    return business


def business_out(row: dict) -> dict:
    data = dict(row)
    data["logo_url"] = f"{API_BASE_URL}/media/logos/{Path(row['logo_path']).name}" if row.get("logo_path") else None
    data.pop("logo_path", None)
    return data


def product_out(row: dict) -> dict:
    return {
        "id": row["id"], "business_id": row["business_id"], "name": row["name"], "category": row.get("category"),
        "price": float(row.get("price") or 0), "calories": row.get("calories"), "protein": row.get("protein"),
        "carbs": row.get("carbs"), "fat": row.get("fat"),
        "tags": [x.strip() for x in str(row.get("tags") or "").split(",") if x.strip()],
        "image_url": f"{API_BASE_URL}/media/uploads/{Path(row['image_path']).name}" if row.get("image_path") else None,
        "model_url": f"{API_BASE_URL}/media/models/{Path(row['model_path']).name}" if row.get("model_path") else None,
        "status": row.get("status") or "queued", "error_message": row.get("error_message"),
        "qr_url": f"{API_BASE_URL}/media/qr/{Path(row['qr_code']).name}" if row.get("qr_code") else None,
        "public_url": f"{PUBLIC_BASE_URL}/?product={row['id']}", "is_published": bool(row.get("is_published")),
        **product_metrics(row["id"]),
    }


def run_generation_job(product_id: str, image_path: Path) -> None:
    product = mongo_get_product(product_id)
    if not product: return
    mongo_update_product(product_id, product["business_id"], {"status":"processing","error_message":None})
    try:
        model_path = generate_3d(product_id, image_path)
        if model_path: mongo_update_product(product_id, product["business_id"], {"model_path":str(model_path),"status":"ready","error_message":None})
        else: mongo_update_product(product_id, product["business_id"], {"status":"awaiting-generator","error_message":"No 3D generator configured."})
    except Exception as exc:
        mongo_update_product(product_id, product["business_id"], {"status":"failed","error_message":str(exc)[:600]})


def queue_3d_generation(product_id: str, image_path: Path) -> None:
    threading.Thread(target=run_generation_job,args=(product_id,image_path),daemon=True).start()


@app.get("/health")
def health(): return {"ok":True,"service":"ashes-api","version":"1.3.0","database":"mongodb"}

@app.post("/api/auth/signup")
def signup(payload: SignupPayload):
    email = payload.email.strip().lower()
    if get_user_by_email(email): raise HTTPException(409,"Account already exists")
    if len(payload.password) < 8: raise HTTPException(400,"Password must be at least 8 characters")
    try:
        user = create_user(email,hash_password(payload.password),payload.owner_name.strip())
        business = mongo_create_business(user["id"],payload.business_name.strip(),unique_slug(payload.business_name),payload.kind,payload.city)
    except DuplicateKeyError as exc: raise HTTPException(409,"Account or business already exists") from exc
    return {"token":issue_token(user["id"]),"user":{"id":user["id"],"email":user["email"],"name":user.get("name")},"business":business_out(business)}

@app.post("/api/auth/login")
def login(payload: LoginPayload):
    user = get_user_by_email(payload.email.strip().lower())
    if not user or not verify_password(payload.password,user["password_hash"]): raise HTTPException(401,"Invalid email or password")
    businesses = list_user_businesses(user["id"])
    return {"token":issue_token(user["id"]),"user":{"id":user["id"],"email":user["email"],"name":user.get("name")},"business":business_out(businesses[0]) if businesses else None}

@app.get("/api/auth/me")
def me(user: dict = Depends(auth_user)):
    return {"user":{"id":user["id"],"email":user["email"],"name":user.get("name")},"businesses":[business_out(x) for x in list_user_businesses(user["id"])]}

@app.get("/api/businesses/{business_slug}")
def business_profile(business_slug: str):
    row = get_business_by_slug(business_slug)
    if not row: raise HTTPException(404,"Business not found")
    return business_out(row)

@app.patch("/api/businesses/{business_slug}")
def update_business_profile(business_slug:str,payload:BusinessUpdatePayload,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); updates={k:v.strip() if isinstance(v,str) else v for k,v in payload.model_dump().items() if v is not None}
    if "accent_color" in updates and not re.fullmatch(r"#[0-9a-fA-F]{6}",updates["accent_color"]): raise HTTPException(400,"Accent color must be a hex color")
    return business_out(update_business(business["id"],updates))

@app.post("/api/businesses/{business_slug}/logo")
async def upload_logo(business_slug:str,logo:UploadFile=File(...),user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    if not logo.content_type or not logo.content_type.startswith("image/"): raise HTTPException(400,"Logo must be an image")
    ext=Path(logo.filename or "logo.png").suffix.lower() or ".png"; path=LOGO_DIR/f"{business['id']}{ext}"; path.write_bytes(await logo.read())
    return business_out(update_business(business["id"],{"logo_path":str(path)}))

@app.get("/api/businesses/{business_slug}/products")
def list_products(business_slug:str,include_unpublished:bool=False,authorization:Optional[str]=Header(None)):
    business=get_business_by_slug(business_slug)
    if not business: raise HTTPException(404,"Business not found")
    allow_all=False
    if include_unpublished and authorization and authorization.lower().startswith("bearer "):
        uid=decode_token(authorization.split(" ",1)[1].strip()); allow_all=bool(uid and uid==business.get("owner_user_id"))
    return [product_out(x) for x in mongo_list_products(business["id"],allow_all)]

@app.post("/api/businesses/{business_slug}/products")
async def create_product(business_slug:str,name:str=Form(...),price:float=Form(...),category:str=Form("Main"),calories:str=Form(""),protein:str=Form(""),carbs:str=Form(""),fat:str=Form(""),tags:str=Form(""),image:UploadFile=File(...),user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug)
    if not image.content_type or not image.content_type.startswith("image/"): raise HTTPException(400,"Upload must be an image")
    pid=str(uuid.uuid4()); ext=Path(image.filename or "product.jpg").suffix.lower() or ".jpg"; image_path=UPLOAD_DIR/f"{pid}{ext}"; image_path.write_bytes(await image.read()); qr_path=QR_DIR/f"{pid}.png"; qrcode.make(f"{PUBLIC_BASE_URL}/?product={pid}").save(qr_path)
    row=mongo_create_product({"id":pid,"business_id":business["id"],"name":name,"category":category,"price":price,"calories":calories,"protein":protein,"carbs":carbs,"fat":fat,"tags":tags,"image_path":str(image_path),"status":"queued","qr_code":str(qr_path),"is_published":False}); queue_3d_generation(pid,image_path); return product_out(row)

@app.post("/api/businesses/{business_slug}/products/{product_id}/image")
async def attach_product_image(business_slug:str,product_id:str,image:UploadFile=File(...),user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); product=mongo_get_product(product_id)
    if not product or product["business_id"]!=business["id"]: raise HTTPException(404,"Product not found")
    ext=Path(image.filename or "product.jpg").suffix.lower() or ".jpg"; path=UPLOAD_DIR/f"{product_id}{ext}"; path.write_bytes(await image.read()); row=mongo_update_product(product_id,business["id"],{"image_path":str(path),"model_path":None,"status":"queued","error_message":None}); queue_3d_generation(product_id,path); return product_out(row)

@app.patch("/api/businesses/{business_slug}/products/{product_id}")
def update_product(business_slug:str,product_id:str,payload:ProductUpdatePayload,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); updates={k:v for k,v in payload.model_dump().items() if v is not None}; row=mongo_update_product(product_id,business["id"],updates)
    if not row: raise HTTPException(404,"Product not found")
    return product_out(row)

@app.delete("/api/businesses/{business_slug}/products/{product_id}")
def delete_product(business_slug:str,product_id:str,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); row=mongo_delete_product(product_id,business["id"])
    if not row: raise HTTPException(404,"Product not found")
    return {"ok":True}

@app.get("/api/businesses/{business_slug}/analytics")
def get_analytics(business_slug:str,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); return {"business_id":business["id"],**business_metrics(business["id"]),"products":[{"id":p["id"],"name":p["name"],**product_metrics(p["id"])} for p in mongo_list_products(business["id"],True)]}

@app.post("/api/products/{product_id}/analytics")
def analytics(product_id:str,payload:AnalyticsEventPayload):
    product=mongo_get_product(product_id)
    if not product or not product.get("is_published"): raise HTTPException(404,"Product not found")
    record_analytics(product_id,product["business_id"],payload.event_type); return {"ok":True}

@app.post("/api/orders")
def create_order(payload:OrderCreatePayload):
    if not payload.items: raise HTTPException(400,"Order needs at least one item")
    first=mongo_get_product(payload.items[0].product_id)
    if not first or not first.get("is_published"): raise HTTPException(400,"Product unavailable")
    try: return mongo_create_order(first["business_id"],[x.model_dump() for x in payload.items],payload.table_code,payload.customer_name,payload.notes)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@app.get("/api/orders/{order_id}")
def get_order(order_id:str):
    order=mongo_get_order(order_id)
    if not order: raise HTTPException(404,"Order not found")
    return order

@app.get("/api/businesses/{business_slug}/orders")
def get_orders(business_slug:str,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); return list_business_orders(business["id"])

@app.get("/api/businesses/{business_slug}/order-notifications")
def order_notifications(business_slug:str,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); orders=list_unnotified_orders(business["id"]); mark_orders_notified([x["id"] for x in orders]); return orders

@app.patch("/api/businesses/{business_slug}/orders/{order_id}")
def order_status(business_slug:str,order_id:str,payload:OrderStatusPayload,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); order=mongo_set_order_status(order_id,business["id"],payload.status)
    if not order: raise HTTPException(404,"Order not found")
    return order

@app.get("/api/businesses/{business_slug}/table-qrs")
def table_qrs(business_slug:str,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); return [{**x,"qr_url":f"{API_BASE_URL}/media/qr/{Path(x['qr_path']).name}"} for x in mongo_list_table_qrs(business["id"])]

@app.post("/api/businesses/{business_slug}/table-qrs")
def add_table_qr(business_slug:str,payload:TableQrPayload,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); code=payload.table_code.strip().upper(); public_url=f"{PUBLIC_BASE_URL}/?business={business['slug']}&table={code}"; qr_path=QR_DIR/f"table-{business['id']}-{slugify(code)}.png"; qrcode.make(public_url).save(qr_path)
    try: row=mongo_create_table_qr({"business_id":business["id"],"table_code":code,"product_id":payload.product_id,"public_url":public_url,"qr_path":str(qr_path)})
    except DuplicateKeyError as exc: raise HTTPException(409,"That table QR already exists") from exc
    return {**row,"qr_url":f"{API_BASE_URL}/media/qr/{qr_path.name}"}

@app.post("/api/businesses/{business_slug}/import-menu-card")
async def import_menu_card(business_slug:str,image:UploadFile=File(...),user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); ext=Path(image.filename or "menu.jpg").suffix.lower() or ".jpg"; path=MENU_IMPORT_DIR/f"{uuid.uuid4()}{ext}"; path.write_bytes(await image.read()); imp=create_menu_import(business["id"],str(path))
    try:
        extracted=extract_menu(path); created=[]; skipped=[]; review=[]
        for item in extracted.get("items") or []:
            name=str(item.get("name") or "").strip(); category=str(item.get("category") or "Main").strip() or "Main"
            if not name: continue
            if find_duplicate_product(business["id"],name,category): skipped.append(name); continue
            pid=str(uuid.uuid4()); qr=QR_DIR/f"{pid}.png"; qrcode.make(f"{PUBLIC_BASE_URL}/?product={pid}").save(qr); confidence=float(item.get("confidence") or 0)
            row=mongo_create_product({"id":pid,"business_id":business["id"],"name":name,"category":category,"price":float(item.get("price") or 0),"tags":", ".join(item.get("tags") or []),"status":"awaiting-image","error_message":"Imported from menu card. Add a product photo to generate its 3D model.","qr_code":str(qr),"is_published":False}); created.append(row)
            if confidence < .78 or float(item.get("price") or 0)<=0: review.append({"id":pid,"name":name,"confidence":confidence})
        update_menu_import(imp["id"],{"status":"completed","items_found":len(created),"error_message":None}); return {"import_id":imp["id"],"status":"completed","items_found":len(created),"created_count":len(created),"duplicates_skipped":len(skipped),"needs_review":len(review),"review_items":review,"business":business_out(business),"products":[product_out(x) for x in created],"review_required":True}
    except Exception as exc:
        update_menu_import(imp["id"],{"status":"failed","error_message":str(exc)[:800]}); raise HTTPException(400,str(exc)) from exc

@app.get("/api/businesses/{business_slug}/menu-imports")
def menu_imports(business_slug:str,user:dict=Depends(auth_user)):
    business=owned_business(user["id"],business_slug); return list_menu_imports(business["id"])

@app.get("/api/products/{product_id}/business")
def product_business(product_id:str):
    product=mongo_get_product(product_id)
    if not product or not product.get("is_published"): raise HTTPException(404,"Business not found")
    return business_out(get_business_by_id(product["business_id"]))

@app.get("/api/products/{product_id}")
def public_product(product_id:str):
    product=mongo_get_product(product_id)
    if not product or not product.get("is_published"): raise HTTPException(404,"Product not found")
    return product_out(product)

@app.get("/media/uploads/{filename}")
def media_upload(filename:str):
    path=UPLOAD_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(404,"File not found")
    return FileResponse(path)

@app.get("/media/models/{filename}")
def media_model(filename:str):
    path=MODEL_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(404,"Model not found")
    return FileResponse(path,media_type="model/gltf-binary")

@app.get("/media/qr/{filename}")
def media_qr(filename:str):
    path=QR_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(404,"QR not found")
    return FileResponse(path,media_type="image/png")

@app.get("/media/logos/{filename}")
def media_logo(filename:str):
    path=LOGO_DIR/Path(filename).name
    if not path.exists(): raise HTTPException(404,"Logo not found")
    return FileResponse(path)
