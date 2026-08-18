from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

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
    return {
        "connected": True,
        "shop": _shop(),
        "store_name": (shop_data.get("shop") or {}).get("name"),
        "token_expires_in": token_payload.get("expires_in"),
        "scopes": token_payload.get("scope"),
        "products": ((shop_data.get("products") or {}).get("nodes") or []),
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
    :root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#0a0a0a;color:#f7f7f7;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1180px;margin:0 auto;padding:28px}}.top{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}}.brand{{font-weight:900;letter-spacing:.04em;font-size:24px}}.brand span{{color:#ff6b35}}.pill{{border:1px solid #2b2b2b;background:#121212;border-radius:999px;padding:8px 12px;color:#bdbdbd;font-size:13px}}h1{{font-size:36px;margin:8px 0 6px}}.sub{{color:#a7a7a7;margin:0 0 26px}}.status{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:24px}}.stat,.card{{background:#111;border:1px solid #252525;border-radius:18px}}.stat{{padding:18px}}.stat b{{display:block;font-size:22px;margin-top:6px}}.label{{color:#8f8f8f;font-size:12px;text-transform:uppercase;letter-spacing:.08em}}.toolbar{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:18px 0}}.toolbar h2{{margin:0;font-size:22px}}button{{border:0;border-radius:12px;padding:11px 14px;font-weight:800;cursor:pointer}}.primary{{background:#ff6b35;color:#0a0a0a}}.secondary{{background:#1b1b1b;color:#fff;border:1px solid #303030}}.primary:disabled{{opacity:.5;cursor:not-allowed}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.card{{padding:14px;display:grid;grid-template-columns:112px 1fr;gap:14px;min-height:140px}}.img{{width:112px;height:112px;border-radius:14px;background:#181818;display:flex;align-items:center;justify-content:center;overflow:hidden}}.img img{{width:100%;height:100%;object-fit:cover}}.img span{{color:#555;font-size:12px}}.meta h3{{margin:4px 0 6px;font-size:18px}}.meta p{{margin:0 0 12px;color:#999;font-size:13px}}.actions{{display:flex;gap:8px;flex-wrap:wrap}}.state{{font-size:12px;color:#a8a8a8;margin-top:10px;min-height:18px}}.ok{{color:#75e6a4}}.err{{color:#ff8f8f}}.empty{{padding:40px;text-align:center;color:#888;background:#111;border:1px dashed #333;border-radius:18px}}.empty strong{{display:block;color:#fff;margin-bottom:8px}}@media(max-width:820px){{.status{{grid-template-columns:1fr}}.grid{{grid-template-columns:1fr}}.top{{align-items:flex-start;flex-direction:column}}}}
  </style>
</head>
<body>
<main>
  <div class="top"><div class="brand">ASHES <span>AI</span></div><div class="pill">Shopify store: {shop}</div></div>
  <div class="label">Ashes × Shopify</div><h1>Turn your Shopify products into 3D.</h1><p class="sub">Choose a product, generate a web-ready GLB with Ashes, then publish it back to Shopify.</p>
  <section class="status"><div class="stat"><span class="label">Connection</span><b id="conn">Checking…</b></div><div class="stat"><span class="label">Products loaded</span><b id="count">—</b></div><div class="stat"><span class="label">3D engine</span><b id="engine">Ready to test</b></div></section>
  <div class="toolbar"><h2>Your products</h2><button class="secondary" id="refresh">Refresh</button></div><div id="products" class="grid"></div>
</main>
<script>
const productsEl=document.getElementById('products'),connEl=document.getElementById('conn'),countEl=document.getElementById('count'),engineEl=document.getElementById('engine'),refreshBtn=document.getElementById('refresh');
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}}[c]));
const imageOf=p=>p?.featuredMedia?.preview?.image?.url||'';
const readable=v=>v==null?'':typeof v==='string'?v:Array.isArray(v)?v.map(readable).filter(Boolean).join(' '):typeof v==='object'?(v.message||v.error_description||v.error||JSON.stringify(v)):String(v);
async function loadProducts(){{productsEl.innerHTML='<div class="empty">Loading Shopify products…</div>';connEl.textContent='Checking…';countEl.textContent='—';try{{const r=await fetch('/api/shopify/products',{{cache:'no-store'}}),data=await r.json();if(!r.ok||!data.connected)throw new Error(readable(data.detail)||readable(data.error)||'Could not connect to Shopify');connEl.textContent='Connected';connEl.className='ok';countEl.textContent=String(data.products?.length||0);render(data.products||[]);}}catch(e){{connEl.textContent='Needs attention';connEl.className='err';productsEl.innerHTML='<div class="empty err"><strong>'+esc(e.message)+'</strong></div>';}}}}
function render(products){{if(!products.length){{productsEl.innerHTML='<div class="empty">No products found.</div>';return;}}productsEl.innerHTML=products.map((p,i)=>{{const image=imageOf(p);return '<article class="card"><div class="img">'+(image?'<img src="'+esc(image)+'" alt="">':'<span>No image</span>')+'</div><div class="meta"><div class="label">'+esc(p.status||'')+'</div><h3>'+esc(p.title)+'</h3><p>'+esc(p.handle||'')+'</p><div class="actions"><button class="primary" data-generate="'+i+'" '+(!image?'disabled':'')+'>Generate 3D</button><button class="secondary" disabled>Publish to Shopify</button></div><div class="state" id="state-'+i+'">'+(!image?'Add a product image first.':'Ready to generate.')+'</div></div></article>';}}).join('');document.querySelectorAll('[data-generate]').forEach(btn=>btn.addEventListener('click',()=>startGeneration(products[Number(btn.dataset.generate)],Number(btn.dataset.generate),btn)));}}
async function startGeneration(product,index,btn){{const state=document.getElementById('state-'+index),image=imageOf(product);if(!image)return;btn.disabled=true;state.className='state';state.textContent='Sending product image to Ashes…';engineEl.textContent='Generating…';try{{const r=await fetch('/api/prototype/generate-3d',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_name:product.title,image_url:image}})}}),data=await r.json();if(!r.ok)throw new Error(readable(data.detail)||readable(data.error)||'Generation could not start');state.textContent='Generation queued: '+data.task_id;await poll(data.task_id,state,btn);}}catch(e){{state.textContent=e.message;state.className='state err';engineEl.textContent='Needs attention';btn.disabled=false;}}}}
async function poll(id,state,btn){{for(let n=0;n<120;n++){{await new Promise(r=>setTimeout(r,2500));const r=await fetch('/api/prototype/generate-3d?id='+encodeURIComponent(id),{{cache:'no-store'}}),data=await r.json();if(!r.ok)throw new Error(readable(data.detail)||'Could not read generation status');const pct=Math.round(Number(data.progress||0)*100);state.textContent=(data.stage||data.status||'PROCESSING')+(pct?' · '+pct+'%':'');if(data.status==='SUCCEEDED'||data.status==='COMPLETED'){{state.innerHTML='3D ready ✓'+(data.model_url?' · <a style="color:#ff8a5b" target="_blank" href="'+esc(data.model_url)+'">Open GLB</a>':'');state.className='state ok';engineEl.textContent='GLB ready';return;}}if(data.status==='FAILED')throw new Error(data.error||'3D generation failed');}}throw new Error('Generation is taking longer than expected.');}}
refreshBtn.addEventListener('click',loadProducts);loadProducts();
</script></body></html>'''
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "frame-ancestors https://admin.shopify.com https://*.myshopify.com",
        },
    )
