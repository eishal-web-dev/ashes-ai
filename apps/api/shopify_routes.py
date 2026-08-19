from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from apps.api.mongo_db import collection
from apps.api.mongo_main import app

SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-07")


def _shop() -> str:
    return (os.getenv("SHOPIFY_SHOP") or "ashes-stack.myshopify.com").strip()


def _client_id() -> str:
    return (os.getenv("SHOPIFY_CLIENT_ID") or os.getenv("ASHES_SHOPIFY_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return (os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("ASHES_SHOPIFY_CLIENT_SECRET") or "").strip()


def _access_token() -> tuple[str, dict[str, Any]]:
    client_id = _client_id()
    client_secret = _client_secret()
    if not client_id:
        raise HTTPException(status_code=500, detail="SHOPIFY_CLIENT_ID is not configured")
    if not client_secret:
        raise HTTPException(status_code=500, detail="SHOPIFY_CLIENT_SECRET is not configured")
    try:
        response = requests.post(
            f"https://{_shop()}/admin/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        payload = response.json() if response.content else {}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Shopify token request failed: {str(exc)[:180]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Shopify token endpoint returned invalid JSON") from exc
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not response.ok or not token:
        detail = payload.get("error_description") or payload.get("error") or payload
        raise HTTPException(status_code=response.status_code or 502, detail=f"Shopify client credentials grant failed: {detail}")
    return str(token), payload


def _graphql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = requests.post(
            f"https://{_shop()}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Shopify-Access-Token": token,
            },
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        payload = response.json() if response.content else {}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Shopify GraphQL request failed: {str(exc)[:180]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Shopify GraphQL returned invalid JSON") from exc
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=payload)
    if payload.get("errors"):
        raise HTTPException(status_code=502, detail=payload["errors"])
    return payload


@app.get("/api/shopify/products")
def shopify_products() -> dict[str, Any]:
    token, token_payload = _access_token()
    data = _graphql(
        token,
        """
        query AshesProducts {
          shop { name }
          products(first: 50) {
            nodes {
              id
              title
              handle
              status
              featuredMedia { preview { image { url } } }
            }
          }
        }
        """,
    )
    shop_data = data.get("data") or {}
    products = ((shop_data.get("products") or {}).get("nodes") or [])
    product_ids = [str(p.get("id")) for p in products if p.get("id")]
    assets = {
        str(row.get("product_id")): row
        for row in collection("shopify_3d_assets").find(
            {"shop": _shop().lower(), "product_id": {"$in": product_ids}, "model_path": {"$exists": True, "$ne": None}}
        )
    }
    for product in products:
        product_id = str(product.get("id") or "")
        asset = assets.get(product_id)
        product["ashes_3d"] = {
            "ready": bool(asset),
            "viewer_url": f"/api/shopify/viewer/{product_id}" if asset else None,
            "updated_at": asset.get("updated_at") if asset else None,
            "published": bool(asset and asset.get("shopify_media_id")),
            "shopify_media_id": asset.get("shopify_media_id") if asset else None,
            "shopify_media_status": asset.get("shopify_media_status") if asset else None,
            "published_at": asset.get("shopify_published_at") if asset else None,
        }
    return {
        "connected": True,
        "shop": _shop(),
        "store_name": (shop_data.get("shop") or {}).get("name"),
        "token_expires_in": token_payload.get("expires_in"),
        "scopes": token_payload.get("scope"),
        "products": products,
    }


@app.get("/api/shopify/health")
def shopify_health() -> dict[str, Any]:
    token, token_payload = _access_token()
    data = _graphql(token, "query AshesShopHealth { shop { name myshopifyDomain } }")
    return {"ok": True, "shop": (data.get("data") or {}).get("shop"), "scopes": token_payload.get("scope")}


@app.get("/api/shopify/app", response_class=HTMLResponse)
def shopify_app() -> HTMLResponse:
    html = '''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ashes AI for Shopify</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0a0a0a;color:#f7f7f7;font-family:Inter,system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:28px}.top{display:flex;justify-content:space-between;gap:16px;margin-bottom:24px}.brand{font-weight:900;font-size:24px}.brand span{color:#ff6b35}.pill{border:1px solid #2b2b2b;background:#121212;border-radius:999px;padding:8px 12px;color:#bbb;font-size:13px}h1{font-size:36px;margin:8px 0 6px}.sub{color:#999;margin:0 0 26px}.label{color:#8f8f8f;font-size:12px;text-transform:uppercase;letter-spacing:.08em}.status{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.stat,.card,.plan{background:#111;border:1px solid #252525;border-radius:18px}.stat{padding:18px}.stat b{display:block;font-size:21px;margin-top:6px}.toolbar{display:flex;justify-content:space-between;align-items:center;margin:26px 0 16px}.toolbar h2{margin:0}.plans{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.plan{padding:16px}.plan.current{border-color:#ff6b35}.plan h3{margin:8px 0}.price{font-size:20px;font-weight:900}.plan ul{padding-left:18px;color:#aaa;font-size:12px;line-height:1.5}.notice{margin-top:14px;padding:13px 15px;border-radius:14px;background:#15120d;border:1px solid #3a2f1c;color:#d8c08e;font-size:13px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}.card{padding:14px;display:grid;grid-template-columns:112px 1fr;gap:14px}.img{width:112px;height:112px;border-radius:14px;background:#181818;overflow:hidden;display:grid;place-items:center}.img img{width:100%;height:100%;object-fit:cover}.meta h3{margin:4px 0 6px}.meta p{margin:0 0 12px;color:#999;font-size:13px}.actions{display:flex;gap:8px;flex-wrap:wrap}button{border:0;border-radius:12px;padding:11px 14px;font-weight:800;cursor:pointer}.primary{background:#ff6b35;color:#080808}.secondary{background:#1b1b1b;color:#fff;border:1px solid #303030}button:disabled{opacity:.45;cursor:not-allowed}.state{font-size:12px;color:#aaa;margin-top:10px;min-height:18px}.ok{color:#75e6a4}.err{color:#ff8f8f}.warn{color:#ffd166}.hidden{display:none!important}.empty{padding:40px;text-align:center;color:#888;background:#111;border:1px dashed #333;border-radius:18px}.viewer{position:fixed;inset:0;z-index:999;background:rgba(0,0,0,.82);display:flex;align-items:center;justify-content:center;padding:24px}.viewerbox{width:min(980px,96vw);height:min(720px,88vh);background:#0b0b0b;border:1px solid #333;border-radius:18px;overflow:hidden;display:grid;grid-template-rows:auto 1fr}.viewerhead{padding:12px 14px;display:flex;justify-content:space-between;border-bottom:1px solid #262626}.viewer iframe{border:0;width:100%;height:100%}@media(max-width:1000px){.plans{grid-template-columns:repeat(2,1fr)}.status{grid-template-columns:repeat(2,1fr)}}@media(max-width:820px){.status,.plans,.grid{grid-template-columns:1fr}.top{flex-direction:column}}
</style></head><body><main>
<div class="top"><div class="brand">ASHES <span>AI</span></div><div class="pill">Shopify store: __SHOP__</div></div>
<div class="label">Ashes × Shopify</div><h1>Turn your Shopify products into 3D.</h1><p class="sub">Generate once, store permanently, reuse the same product twin, then publish it as native Shopify 3D media.</p>
<section class="status"><div class="stat"><span class="label">Connection</span><b id="conn">Checking…</b></div><div class="stat"><span class="label">Products loaded</span><b id="count">—</b></div><div class="stat"><span class="label">3D engine</span><b id="engine">Checking…</b></div><div class="stat"><span class="label">Generation allowance</span><b id="allowance">—</b></div></section>
<section id="serviceArea"><div class="toolbar"><h2>Packages</h2><span class="pill" id="currentPlan">Loading…</span></div><div id="plans" class="plans"></div><div class="notice">Only one new product twin generates at a time. <b>Publishing an existing twin to Shopify costs 0 generation credits.</b></div><div class="toolbar"><h2>Your products</h2><button class="secondary" id="refresh">Refresh</button></div><div id="products" class="grid"></div></section>
<div id="disconnected" class="empty hidden"><strong>Ashes 3D services are disconnected.</strong></div></main>
<div id="viewer" class="viewer hidden"><div class="viewerbox"><div class="viewerhead"><b id="viewerTitle">Ashes 3D</b><button class="secondary" id="closeViewer">Close</button></div><iframe id="viewerFrame"></iframe></div></div>
<script>
const $=id=>document.getElementById(id),productsEl=$('products'),connEl=$('conn'),countEl=$('count'),engineEl=$('engine'),allowanceEl=$('allowance'),plansEl=$('plans'),serviceArea=$('serviceArea'),disconnected=$('disconnected'),viewer=$('viewer'),viewerFrame=$('viewerFrame'),viewerTitle=$('viewerTitle');let productsCache=[],planData=null,activeTask=null;
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[c]));const imageOf=p=>p?.featuredMedia?.preview?.image?.url||'';const readable=v=>v==null?'':typeof v==='string'?v:Array.isArray(v)?v.map(readable).join(' '):typeof v==='object'?(v.message||v.error||JSON.stringify(v)):String(v);const pctOf=v=>{const n=Number(v||0);return Number.isFinite(n)?Math.max(0,Math.min(100,Math.round(n<=1?n*100:n))):0};
function setConnected(ok){serviceArea.classList.toggle('hidden',!ok);disconnected.classList.toggle('hidden',ok)}function openViewer(url,title){viewerTitle.textContent=title||'Ashes 3D';viewerFrame.src=url;viewer.classList.remove('hidden')}function closeViewer(){viewerFrame.src='about:blank';viewer.classList.add('hidden')}$('closeViewer').onclick=closeViewer;viewer.onclick=e=>{if(e.target===viewer)closeViewer()};
function renderPlans(){if(!planData)return;const current=planData.current_plan||{};$('currentPlan').textContent='Current: '+(current.name||'Free Trial');allowanceEl.textContent=planData.remaining==null?'Custom':planData.remaining+' left';plansEl.innerHTML=(planData.plans||[]).map(p=>'<article class="plan '+(p.key===current.key?'current':'')+'"><span class="label">'+(p.key===current.key?'Current plan':'Package')+'</span><h3>'+esc(p.name)+'</h3><div class="price">'+esc(p.price)+'</div><div class="state">'+(p.generation_allowance==null?'Custom':p.generation_allowance+' '+(p.generation_period==='total'?'total generations':'generations / month'))+'</div><ul>'+(p.features||[]).map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul></article>').join('')}
async function loadPlans(){const r=await fetch('/api/shopify/plans',{cache:'no-store'}),d=await r.json();if(!r.ok)throw new Error(readable(d.detail)||'Could not load packages');planData=d;activeTask=d.active_generation||null;renderPlans();engineEl.textContent=activeTask?'Generating…':'Ready'}
async function loadProducts(){productsEl.innerHTML='<div class="empty">Loading Shopify products…</div>';try{const r=await fetch('/api/shopify/products',{cache:'no-store'}),d=await r.json();if(!r.ok||!d.connected)throw new Error(readable(d.detail)||'Could not connect to Shopify');connEl.textContent='Connected';connEl.className='ok';countEl.textContent=String(d.products?.length||0);setConnected(true);productsCache=d.products||[];await loadPlans();render(productsCache)}catch(e){connEl.textContent='Disconnected';connEl.className='err';setConnected(false);disconnected.innerHTML='<strong>Ashes 3D services are disconnected.</strong>'+esc(e.message)}}
function render(products){if(!products.length){productsEl.innerHTML='<div class="empty">No products found.</div>';return}const locked=!!activeTask;productsEl.innerHTML=products.map((p,i)=>{const image=imageOf(p),a=p.ashes_3d||{},ready=!!a.ready,published=!!a.published;const primary=ready?'<button class="primary" data-view="'+i+'">View 3D</button>':'<button class="primary" data-generate="'+i+'" '+(!image||locked?'disabled':'')+'>Generate 3D</button>';const pub=published?'<button class="secondary" disabled>Published ✓</button>':'<button class="secondary" data-publish="'+i+'" '+(ready?'':'disabled')+'>Publish to Shopify</button>';const status=published?'Published to Shopify · '+esc(a.shopify_media_status||'PROCESSING'):ready?'3D ready · Stored in Ashes':!image?'Add a product image first.':locked?'Another product is generating.':'Ready to generate.';return '<article class="card"><div class="img">'+(image?'<img src="'+esc(image)+'">':'<span>No image</span>')+'</div><div class="meta"><div class="label">'+esc(p.status||'')+'</div><h3>'+esc(p.title)+'</h3><p>'+esc(p.handle||'')+'</p><div class="actions">'+primary+pub+'</div><div class="state '+(ready?'ok':'')+'" id="state-'+i+'">'+status+'</div></div></article>'}).join('');document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{const p=products[+b.dataset.view];openViewer(p.ashes_3d.viewer_url,p.title)});document.querySelectorAll('[data-generate]').forEach(b=>b.onclick=()=>startGeneration(products[+b.dataset.generate],+b.dataset.generate));document.querySelectorAll('[data-publish]').forEach(b=>b.onclick=()=>publishProduct(products[+b.dataset.publish],+b.dataset.publish,b))}
async function publishProduct(product,index,btn){const state=$('state-'+index);btn.disabled=true;btn.textContent='Publishing…';state.className='state warn';state.textContent='Uploading existing GLB to Shopify…';try{const r=await fetch('/api/shopify/publish-3d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:product.id,product_name:product.title})}),d=await r.json();if(!r.ok)throw new Error(readable(d.detail)||'Shopify publish failed');state.className='state ok';state.textContent='Published to Shopify · '+(d.status||'PROCESSING');await loadProducts()}catch(e){btn.disabled=false;btn.textContent='Publish to Shopify';state.className='state err';state.textContent=e.message}}
function lockAll(id){activeTask=id||'starting';engineEl.textContent='Generating…';document.querySelectorAll('[data-generate]').forEach(b=>b.disabled=true)}
async function startGeneration(product,index){const state=$('state-'+index),image=imageOf(product);if(!image||activeTask)return;lockAll('starting');state.textContent='Sending product image to Ashes…';try{const r=await fetch('/api/shopify/generate-3d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:product.id,product_name:product.title,image_url:image})}),d=await r.json();if(!r.ok)throw new Error(readable(d.detail)||'Generation could not start');if(d.reused&&d.status==='COMPLETED'){activeTask=null;await loadProducts();openViewer(d.viewer_url,product.title);return}activeTask=d.task_id;await poll(d.task_id,state)}catch(e){state.className='state err';state.textContent=e.message;engineEl.textContent='Needs attention';activeTask=null;await loadPlans().catch(()=>{});render(productsCache)}}
async function poll(id,state){for(let n=0;n<240;n++){await new Promise(r=>setTimeout(r,2500));const r=await fetch('/api/shopify/generate-3d?id='+encodeURIComponent(id),{cache:'no-store'}),d=await r.json();if(!r.ok)throw new Error(readable(d.detail)||'Could not read status');const pct=pctOf(d.progress);state.textContent=(d.stage||d.status||'PROCESSING')+(pct?' · '+pct+'%':'');if(d.plan_usage)allowanceEl.textContent=d.plan_usage.remaining==null?'Custom':d.plan_usage.remaining+' left';if(d.status==='COMPLETED'){activeTask=null;await loadProducts();return}if(['FAILED','CANCELLED','STORAGE_FAILED','QUALITY_FAILED'].includes(d.status))throw new Error(d.error||'3D generation failed')}throw new Error('Generation is taking longer than expected.')}
$('refresh').onclick=loadProducts;loadProducts();
</script></body></html>'''.replace("__SHOP__", _shop())
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "Content-Security-Policy": "frame-ancestors https://admin.shopify.com https://*.myshopify.com"})
