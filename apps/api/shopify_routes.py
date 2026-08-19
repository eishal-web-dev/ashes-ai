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

    url = f"https://{_shop()}/admin/oauth/access_token"
    try:
        response = requests.post(
            url,
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
    return {
        "ok": True,
        "shop": (data.get("data") or {}).get("shop"),
        "scopes": token_payload.get("scope"),
    }


@app.get("/api/shopify/app", response_class=HTMLResponse)
def shopify_app() -> HTMLResponse:
    shop = _shop()
    html = f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Ashes AI for Shopify</title>
  <style>
    :root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#0a0a0a;color:#f7f7f7;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1180px;margin:0 auto;padding:28px}}.top{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}}.brand{{font-weight:900;letter-spacing:.04em;font-size:24px}}.brand span{{color:#ff6b35}}.pill{{border:1px solid #2b2b2b;background:#121212;border-radius:999px;padding:8px 12px;color:#bdbdbd;font-size:13px}}h1{{font-size:36px;margin:8px 0 6px}}.sub{{color:#a7a7a7;margin:0 0 26px}}.status{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:24px}}.stat,.card,.plan{{background:#111;border:1px solid #252525;border-radius:18px}}.stat{{padding:18px}}.stat b{{display:block;font-size:21px;margin-top:6px}}.label{{color:#8f8f8f;font-size:12px;text-transform:uppercase;letter-spacing:.08em}}.toolbar{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:26px 0 16px}}.toolbar h2{{margin:0;font-size:22px}}button{{border:0;border-radius:12px;padding:11px 14px;font-weight:800;cursor:pointer}}.primary{{background:#ff6b35;color:#0a0a0a}}.secondary{{background:#1b1b1b;color:#fff;border:1px solid #303030}}.primary:disabled,.secondary:disabled{{opacity:.45;cursor:not-allowed}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.card{{padding:14px;display:grid;grid-template-columns:112px 1fr;gap:14px;min-height:140px}}.img{{width:112px;height:112px;border-radius:14px;background:#181818;display:flex;align-items:center;justify-content:center;overflow:hidden}}.img img{{width:100%;height:100%;object-fit:cover}}.img span{{color:#555;font-size:12px}}.meta h3{{margin:4px 0 6px;font-size:18px}}.meta p{{margin:0 0 12px;color:#999;font-size:13px}}.actions{{display:flex;gap:8px;flex-wrap:wrap}}.state{{font-size:12px;color:#a8a8a8;margin-top:10px;min-height:18px}}.ok{{color:#75e6a4}}.err{{color:#ff8f8f}}.warn{{color:#ffd166}}.empty{{padding:40px;text-align:center;color:#888;background:#111;border:1px dashed #333;border-radius:18px}}.empty strong{{display:block;color:#fff;margin-bottom:8px}}.plans{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}}.plan{{padding:16px;position:relative}}.plan.current{{border-color:#ff6b35;box-shadow:0 0 0 1px rgba(255,107,53,.2)}}.plan h3{{margin:8px 0 4px;font-size:18px}}.price{{font-size:20px;font-weight:900;margin-bottom:10px}}.plan ul{{padding-left:18px;margin:10px 0 0;color:#aaa;font-size:12px;line-height:1.5}}.plan .tag{{display:inline-block;border:1px solid #333;border-radius:999px;padding:5px 8px;font-size:10px;color:#aaa}}.notice{{margin:14px 0 0;padding:13px 15px;border-radius:14px;background:#15120d;border:1px solid #3a2f1c;color:#d8c08e;font-size:13px}}.hidden{{display:none!important}}.viewer{{position:fixed;inset:0;z-index:999;background:rgba(0,0,0,.82);display:flex;align-items:center;justify-content:center;padding:24px}}.viewerbox{{width:min(980px,96vw);height:min(720px,88vh);background:#0b0b0b;border:1px solid #333;border-radius:18px;overflow:hidden;display:grid;grid-template-rows:auto 1fr}}.viewerhead{{padding:12px 14px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #262626}}.viewer iframe{{border:0;width:100%;height:100%}}@media(max-width:1000px){{.plans{{grid-template-columns:repeat(2,minmax(0,1fr))}}.status{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:820px){{.status,.plans{{grid-template-columns:1fr}}.grid{{grid-template-columns:1fr}}.top{{align-items:flex-start;flex-direction:column}}}}
  </style>
</head>
<body>
<main>
  <div class="top"><div class="brand">ASHES <span>AI</span></div><div class="pill">Shopify store: {shop}</div></div>
  <div class="label">Ashes × Shopify</div><h1>Turn your Shopify products into 3D.</h1><p class="sub">Generate once, store permanently, and reuse the same product twin across supported commerce channels.</p>
  <section class="status"><div class="stat"><span class="label">Connection</span><b id="conn">Checking…</b></div><div class="stat"><span class="label">Products loaded</span><b id="count">—</b></div><div class="stat"><span class="label">3D engine</span><b id="engine">Checking…</b></div><div class="stat"><span class="label">Generation allowance</span><b id="allowance">—</b></div></section>
  <section id="serviceArea">
    <div class="toolbar"><h2>Packages</h2><span class="pill" id="currentPlan">Loading…</span></div>
    <div id="plans" class="plans"></div>
    <div class="notice">Ashes generates only <b>one product at a time per store</b>. Free Trial includes exactly <b>2 total 3D generations</b>. Completed product twins are stored once and reused without another GPU call.</div>
    <div class="toolbar"><h2>Your products</h2><button class="secondary" id="refresh">Refresh</button></div><div id="products" class="grid"></div>
  </section>
  <div id="disconnected" class="empty hidden"><strong>Ashes 3D services are disconnected.</strong>Reconnect/install Ashes to restore product generation. 3D delivery is disabled while the app is disconnected.</div>
</main>
<div id="viewer" class="viewer hidden"><div class="viewerbox"><div class="viewerhead"><b id="viewerTitle">Ashes 3D</b><button class="secondary" id="closeViewer">Close</button></div><iframe id="viewerFrame" title="Ashes 3D viewer"></iframe></div></div>
<script>
const productsEl=document.getElementById('products'),connEl=document.getElementById('conn'),countEl=document.getElementById('count'),engineEl=document.getElementById('engine'),allowanceEl=document.getElementById('allowance'),refreshBtn=document.getElementById('refresh'),plansEl=document.getElementById('plans'),currentPlanEl=document.getElementById('currentPlan'),serviceArea=document.getElementById('serviceArea'),disconnected=document.getElementById('disconnected'),viewer=document.getElementById('viewer'),viewerFrame=document.getElementById('viewerFrame'),viewerTitle=document.getElementById('viewerTitle');
let productsCache=[],planData=null,activeTask=null;
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}}[c]));
const imageOf=p=>p?.featuredMedia?.preview?.image?.url||'';
const readable=v=>v==null?'':typeof v==='string'?v:Array.isArray(v)?v.map(readable).filter(Boolean).join(' '):typeof v==='object'?(v.message||v.error_description||v.error||JSON.stringify(v)):String(v);
const pctOf=v=>{{const n=Number(v||0);if(!Number.isFinite(n)||n<=0)return 0;return Math.max(0,Math.min(100,Math.round(n<=1?n*100:n)));}};
function setConnected(ok){{serviceArea.classList.toggle('hidden',!ok);disconnected.classList.toggle('hidden',ok);if(!ok){{engineEl.textContent='Unavailable';allowanceEl.textContent='—';}}}}
function openViewer(url,title){{viewerTitle.textContent=title||'Ashes 3D';viewerFrame.src=url;viewer.classList.remove('hidden');}}
function closeViewer(){{viewerFrame.src='about:blank';viewer.classList.add('hidden');}}
document.getElementById('closeViewer').addEventListener('click',closeViewer);viewer.addEventListener('click',e=>{{if(e.target===viewer)closeViewer();}});
function renderPlans(){{if(!planData)return;const current=planData.current_plan||{{}};currentPlanEl.textContent='Current: '+(current.name||'Free Trial');const remaining=planData.remaining;allowanceEl.textContent=remaining==null?'Custom':String(remaining)+' left';plansEl.innerHTML=(planData.plans||[]).map(p=>'<article class="plan '+(p.key===current.key?'current':'')+'"><span class="tag">'+esc(p.key===current.key?'Current plan':p.generation_period==='total'?'Trial':'Package')+'</span><h3>'+esc(p.name)+'</h3><div class="price">'+esc(p.price)+'</div><div class="state">'+(p.generation_allowance==null?'Custom generation allowance':esc(p.generation_allowance)+' '+esc(p.generation_period==='total'?'total generations':'generations / month'))+'</div><ul>'+(p.features||[]).map(f=>'<li>'+esc(f)+'</li>').join('')+'</ul></article>').join('');}}
async function loadPlans(){{const r=await fetch('/api/shopify/plans',{{cache:'no-store'}}),data=await r.json();if(!r.ok)throw new Error(readable(data.detail)||'Could not load Ashes packages');planData=data;activeTask=data.active_generation||null;renderPlans();engineEl.textContent=activeTask?'Generating…':'Ready';}}
async function loadProducts(){{productsEl.innerHTML='<div class="empty">Loading Shopify products…</div>';connEl.textContent='Checking…';countEl.textContent='—';try{{const r=await fetch('/api/shopify/products',{{cache:'no-store'}}),data=await r.json();if(!r.ok||!data.connected)throw new Error(readable(data.detail)||readable(data.error)||'Could not connect to Shopify');connEl.textContent='Connected';connEl.className='ok';countEl.textContent=String(data.products?.length||0);setConnected(true);productsCache=data.products||[];await loadPlans();render(productsCache);}}catch(e){{connEl.textContent='Disconnected';connEl.className='err';setConnected(false);disconnected.innerHTML='<strong>Ashes 3D services are disconnected.</strong>'+esc(e.message);}}}}
function render(products){{if(!products.length){{productsEl.innerHTML='<div class="empty">No products found.</div>';return;}}const locked=!!activeTask;productsEl.innerHTML=products.map((p,i)=>{{const image=imageOf(p),ready=!!p?.ashes_3d?.ready,viewerUrl=p?.ashes_3d?.viewer_url||'';const primary=ready?'<button class="primary" data-view="'+i+'">View 3D</button>':'<button class="primary" data-generate="'+i+'" '+(!image||locked?'disabled':'')+'>Generate 3D</button>';const status=!image&&!ready?'Add a product image first.':ready?'3D ready · Stored in Ashes':locked?'Another product is generating.':'Ready to generate.';return '<article class="card"><div class="img">'+(image?'<img src="'+esc(image)+'" alt="">':'<span>No image</span>')+'</div><div class="meta"><div class="label">'+esc(p.status||'')+'</div><h3>'+esc(p.title)+'</h3><p>'+esc(p.handle||'')+'</p><div class="actions">'+primary+'<button class="secondary" '+(ready?'':'disabled')+'>Publish to Shopify</button></div><div class="state '+(ready?'ok':'')+'" id="state-'+i+'">'+status+'</div></div></article>';}}).join('');document.querySelectorAll('[data-generate]').forEach(btn=>btn.addEventListener('click',()=>startGeneration(products[Number(btn.dataset.generate)],Number(btn.dataset.generate),btn)));document.querySelectorAll('[data-view]').forEach(btn=>btn.addEventListener('click',()=>{{const p=products[Number(btn.dataset.view)];openViewer(p.ashes_3d.viewer_url,p.title);}}));}}
function lockAll(taskId){{activeTask=taskId||'starting';document.querySelectorAll('[data-generate]').forEach(b=>b.disabled=true);engineEl.textContent='Generating…';}}
async function startGeneration(product,index,btn){{const state=document.getElementById('state-'+index),image=imageOf(product);if(!image||activeTask)return;lockAll('starting');state.className='state';state.textContent='Sending product image to Ashes…';try{{const r=await fetch('/api/shopify/generate-3d',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:product.id,product_name:product.title,image_url:image}})}}),data=await r.json();if(!r.ok)throw new Error(readable(data.detail)||readable(data.error)||'Generation could not start');if(data.reused&&data.status==='COMPLETED'){{activeTask=null;await loadProducts();openViewer(data.viewer_url,product.title);return;}}activeTask=data.task_id;state.textContent='Generation queued';await poll(data.task_id,state);}}catch(e){{state.textContent=e.message;state.className='state err';engineEl.textContent='Needs attention';activeTask=null;await loadPlans().catch(()=>{{}});render(productsCache);}}}}
async function poll(id,state){{for(let n=0;n<240;n++){{await new Promise(r=>setTimeout(r,2500));const r=await fetch('/api/shopify/generate-3d?id='+encodeURIComponent(id),{{cache:'no-store'}}),data=await r.json();if(!r.ok)throw new Error(readable(data.detail)||'Could not read generation status');const pct=pctOf(data.progress);state.textContent=(data.stage||data.status||'PROCESSING')+(pct?' · '+pct+'%':'');if(data.plan_usage){{allowanceEl.textContent=data.plan_usage.remaining==null?'Custom':String(data.plan_usage.remaining)+' left';}}if(data.status==='COMPLETED'){{state.textContent='3D ready · Stored in Ashes';state.className='state ok';engineEl.textContent='3D ready';activeTask=null;await loadProducts();return;}}if(['FAILED','CANCELLED','STORAGE_FAILED'].includes(data.status))throw new Error(data.error||'3D generation failed');}}throw new Error('Generation is taking longer than expected.');}}
refreshBtn.addEventListener('click',loadProducts);loadProducts();
</script></body></html>'''
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "frame-ancestors https://admin.shopify.com https://*.myshopify.com",
        },
    )
