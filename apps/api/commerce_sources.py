from __future__ import annotations

import ipaddress
import json
import re
import socket
import uuid
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from fastapi import Depends, HTTPException
from pydantic import BaseModel

from apps.api.mongo_main import app, auth_user, owned_business
from apps.api.mongo_db import collection, create_product as mongo_create_product, get_business_by_slug, get_product, now_iso, update_product

UA = "AshesCatalogBot/1.0 (+authorized merchant catalog import)"


class CommerceSourcePayload(BaseModel):
    source_type: str = "ashes"  # ashes | website | shopify | woocommerce | custom
    website_url: Optional[str] = None
    checkout_url: Optional[str] = None
    sync_enabled: bool = False
    external_checkout: bool = False
    store_label: Optional[str] = None


class ImportPayload(BaseModel):
    url: str
    max_pages: int = 12


class ProductLinkPayload(BaseModel):
    source_url: Optional[str] = None
    checkout_url: Optional[str] = None
    external_product_id: Optional[str] = None


class HandoffItem(BaseModel):
    product_id: str
    quantity: int = 1


class HandoffPayload(BaseModel):
    items: list[HandoffItem]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    table_code: Optional[str] = None


class CatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.model_urls: list[str] = []
        self._jsonld = False
        self._script_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        data = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "title": self._in_title = True
        if tag.lower() == "meta":
            key = (data.get("property") or data.get("name") or "").lower()
            value = data.get("content", "").strip()
            if key and value: self.meta[key] = value
        if tag.lower() == "a" and data.get("href"): self.links.append(data["href"])
        if tag.lower() in {"model-viewer", "a-entity", "source"}:
            for key in ("src", "data-src", "gltf-model"):
                candidate = data.get(key, "").strip()
                if candidate and _looks_like_glb(candidate): self.model_urls.append(candidate)
        if tag.lower() == "script" and "ld+json" in data.get("type", "").lower():
            self._jsonld = True; self._script_buf = []

    def handle_endtag(self, tag):
        if tag.lower() == "title": self._in_title = False
        if tag.lower() == "script" and self._jsonld:
            self.scripts.append("".join(self._script_buf)); self._jsonld = False; self._script_buf = []

    def handle_data(self, data):
        if self._in_title: self.title += data
        if self._jsonld: self._script_buf.append(data)


def _safe_public_url(raw: str) -> str:
    value = (raw or "").strip()
    if not re.match(r"^https?://", value, re.I): value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(400, "Use a valid public http/https website URL")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise HTTPException(400, "Local/private websites cannot be imported")
    try:
        for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(400, "Private-network websites cannot be imported")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "Website hostname could not be resolved") from exc
    return value


def _fetch(url: str) -> tuple[str, str]:
    safe = _safe_public_url(url)
    try:
        response = requests.get(safe, timeout=12, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(400, f"Could not read website: {str(exc)[:180]}") from exc
    final = _safe_public_url(response.url)
    ctype = response.headers.get("content-type", "")
    if "html" not in ctype.lower(): raise HTTPException(400, "Website URL did not return an HTML page")
    return final, response.text[:2_000_000]


def _money(value: Any) -> Optional[float]:
    if value is None: return None
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    if not match: return None
    try: return float(match.group(0).replace(",", ""))
    except ValueError: return None


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values(): yield from _walk_json(v)
    elif isinstance(value, list):
        for v in value: yield from _walk_json(v)


def _looks_like_glb(value: str) -> bool:
    lowered = value.lower()
    return ".glb" in lowered or "glb_draco" in lowered


def _extract_model_urls(url: str, html: str, parser: CatalogParser) -> list[str]:
    """Find GLB assets exposed in markup, JSON state, or model-viewer elements."""
    candidates = list(parser.model_urls)
    # Commerce sites commonly serialize model URLs as JSON with escaped slashes.
    normalized = html.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
    candidates.extend(re.findall(r"https?://[^\"'<>\\s]+?(?:\.glb(?:\?[^\"'<>\\s]*)?|glb_draco[^\"'<>\\s]*)", normalized, re.I))

    resolved: list[str] = []
    for candidate in candidates:
        model_url = urljoin(url, candidate).replace("&amp;", "&")
        parsed = urlparse(model_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc and _looks_like_glb(model_url):
            resolved.append(model_url)
    return list(dict.fromkeys(resolved))


def _extract_product(url: str, html: str) -> tuple[Optional[dict], list[str]]:
    parser = CatalogParser(); parser.feed(html)
    model_urls = _extract_model_urls(url, html, parser)
    candidates: list[dict] = []
    for script in parser.scripts:
        try: obj = json.loads(script)
        except Exception: continue
        for node in _walk_json(obj):
            typ = node.get("@type")
            types = typ if isinstance(typ, list) else [typ]
            if "Product" not in types: continue
            offers = node.get("offers") or {}
            if isinstance(offers, list): offers = offers[0] if offers else {}
            image = node.get("image")
            if isinstance(image, list): image = image[0] if image else None
            if isinstance(image, dict): image = image.get("url")
            candidates.append({
                "name": node.get("name"), "description": node.get("description"), "image_url": image,
                "price": _money(offers.get("price") if isinstance(offers, dict) else None),
                "currency": offers.get("priceCurrency") if isinstance(offers, dict) else None,
                "external_product_id": node.get("sku") or node.get("productID") or node.get("mpn"),
                "source_url": url,
                "model_url": model_urls[0] if model_urls else None,
            })
    if candidates:
        product = next((x for x in candidates if x.get("name")), candidates[0])
    else:
        name = parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title.strip()
        price = _money(parser.meta.get("product:price:amount") or parser.meta.get("og:price:amount"))
        image = parser.meta.get("og:image") or parser.meta.get("twitter:image")
        product = {"name": name, "price": price, "image_url": image, "description": parser.meta.get("og:description"), "source_url": url, "model_url": model_urls[0] if model_urls else None} if price is not None else None
    links = [urljoin(url, href) for href in parser.links]
    return product, links


def _productish(url: str) -> bool:
    path = urlparse(url).path.lower()
    return bool(re.search(r"/(product|products|shop|item|menu|catalog|collections?)/", path)) or any(x in path for x in ["/product-", "/p/"])


def _crawl(start_url: str, max_pages: int) -> list[dict]:
    first_url, first_html = _fetch(start_url)
    root = urlparse(first_url)
    first_product, links = _extract_product(first_url, first_html)
    products: list[dict] = []
    if first_product: products.append(first_product)
    queue = []
    for link in links:
        p = urlparse(link)
        if p.hostname == root.hostname and _productish(link): queue.append(link.split("#")[0])
    seen = {first_url}
    for link in list(dict.fromkeys(queue))[: max(1, min(max_pages, 20))]:
        if link in seen: continue
        seen.add(link)
        try:
            final, html = _fetch(link)
            if urlparse(final).hostname != root.hostname: continue
            product, _ = _extract_product(final, html)
            if product and product.get("name") and product.get("price") is not None: products.append(product)
        except HTTPException:
            continue
    dedup: dict[str, dict] = {}
    for p in products:
        key = (p.get("external_product_id") or p.get("source_url") or p.get("name") or str(uuid.uuid4())).lower()
        dedup[key] = p
    return list(dedup.values())


def _source_doc(business_id: str) -> dict:
    row = collection("commerce_sources").find_one({"business_id": business_id})
    if not row:
        return {"business_id": business_id, "source_type": "ashes", "website_url": None, "checkout_url": None, "sync_enabled": False, "external_checkout": False, "store_label": "Ashes Full Store"}
    row.pop("_id", None); return row


@app.get("/api/businesses/{slug}/commerce-source")
def get_commerce_source(slug: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], slug); return _source_doc(business["id"])


@app.get("/api/public/businesses/{slug}/commerce-source")
def get_public_commerce_source(slug: str):
    business = get_business_by_slug(slug)
    if not business: raise HTTPException(404, "Business not found")
    row = _source_doc(business["id"])
    return {k: row.get(k) for k in ["source_type", "website_url", "checkout_url", "external_checkout", "store_label"]}


@app.patch("/api/businesses/{slug}/commerce-source")
def save_commerce_source(slug: str, payload: CommerceSourcePayload, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], slug)
    source_type = payload.source_type.strip().lower()
    if source_type not in {"ashes", "website", "shopify", "woocommerce", "custom"}: raise HTTPException(400, "Unsupported commerce source")
    website = _safe_public_url(payload.website_url) if payload.website_url else None
    checkout = _safe_public_url(payload.checkout_url) if payload.checkout_url else None
    doc = {"business_id": business["id"], "source_type": source_type, "website_url": website, "checkout_url": checkout, "sync_enabled": bool(payload.sync_enabled), "external_checkout": bool(payload.external_checkout and source_type != "ashes"), "store_label": payload.store_label or ("Ashes Full Store" if source_type == "ashes" else "Merchant Store"), "updated_at": now_iso()}
    collection("commerce_sources").update_one({"business_id": business["id"]}, {"$set": doc, "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    return _source_doc(business["id"])


@app.post("/api/businesses/{slug}/commerce-source/import")
def import_website_catalog(slug: str, payload: ImportPayload, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], slug)
    products = _crawl(payload.url, payload.max_pages)
    created = []
    for item in products:
        source_url = item.get("source_url")
        existing = collection("products").find_one({"business_id": business["id"], "source_url": source_url}) if source_url else None
        if existing: continue
        row = mongo_create_product({"business_id": business["id"], "name": (item.get("name") or "Imported product")[:180], "category": "Imported", "price": float(item.get("price") or 0), "status": "awaiting-image", "is_published": False})
        update_product(row["id"], business["id"], {"source_url": source_url, "checkout_url": source_url, "external_image_url": item.get("image_url"), "external_model_url": item.get("model_url"), "external_product_id": item.get("external_product_id"), "source_currency": item.get("currency"), "source_description": item.get("description"), "commerce_source_type": "website"})
        created.append({"id": row["id"], **item})
    collection("commerce_imports").insert_one({"id": str(uuid.uuid4()), "business_id": business["id"], "url": payload.url, "found": len(products), "created": len(created), "created_at": now_iso()})
    return {"found": len(products), "created": len(created), "products": created, "message": "Imported products are Ashes drafts. Review them and add/confirm photos before publishing."}


@app.get("/api/products/{product_id}/commerce")
def get_product_commerce(product_id: str):
    product = get_product(product_id)
    if not product: raise HTTPException(404, "Product not found")
    source = _source_doc(product["business_id"])
    return {"source_type": source.get("source_type", "ashes"), "external_checkout": bool(source.get("external_checkout")), "website_url": source.get("website_url"), "business_checkout_url": source.get("checkout_url"), "source_url": product.get("source_url"), "checkout_url": product.get("checkout_url"), "external_product_id": product.get("external_product_id")}


@app.patch("/api/businesses/{slug}/products/{product_id}/commerce")
def save_product_commerce(slug: str, product_id: str, payload: ProductLinkPayload, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], slug); product = get_product(product_id)
    if not product or product["business_id"] != business["id"]: raise HTTPException(404, "Product not found")
    updates = {"source_url": _safe_public_url(payload.source_url) if payload.source_url else None, "checkout_url": _safe_public_url(payload.checkout_url) if payload.checkout_url else None, "external_product_id": payload.external_product_id}
    return update_product(product_id, business["id"], updates)


@app.post("/api/businesses/{slug}/commerce-handoff")
def create_commerce_handoff(slug: str, payload: HandoffPayload):
    business = get_business_by_slug(slug)
    if not business: raise HTTPException(404, "Business not found")
    source = _source_doc(business["id"])
    if not source.get("external_checkout"): return {"mode": "ashes", "redirect_url": None}
    resolved = []
    for item in payload.items:
        product = get_product(item.product_id)
        if product and product.get("business_id") == business["id"]:
            resolved.append({"product_id": product["id"], "name": product.get("name"), "quantity": max(1, min(99, item.quantity)), "source_url": product.get("source_url"), "checkout_url": product.get("checkout_url")})
    if not resolved: raise HTTPException(400, "No valid products for checkout handoff")
    if len(resolved) == 1:
        redirect = resolved[0].get("checkout_url") or resolved[0].get("source_url") or source.get("checkout_url") or source.get("website_url")
    else:
        redirect = source.get("checkout_url") or source.get("website_url") or resolved[0].get("checkout_url") or resolved[0].get("source_url")
    if not redirect: raise HTTPException(400, "Merchant has not configured an external checkout URL")
    handoff_id = str(uuid.uuid4())
    collection("commerce_handoffs").insert_one({"id": handoff_id, "business_id": business["id"], "items": resolved, "customer_name": payload.customer_name, "customer_phone": payload.customer_phone, "table_code": payload.table_code, "redirect_url": redirect, "created_at": now_iso()})
    return {"mode": "external", "handoff_id": handoff_id, "redirect_url": redirect, "source_type": source.get("source_type")}
