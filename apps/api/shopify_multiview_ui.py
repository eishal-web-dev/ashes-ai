from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.mongo_main import app


_INJECT = r'''
<!-- ASHES_MULTIVIEW_UI_V3 -->
<script>
(function(){
  const imageUrls = p => Array.isArray(p && p.ashes_images) ? p.ashes_images.slice(0,3) : [];
  const firstImage = p => imageUrls(p)[0] || (p?.featuredMedia?.preview?.image?.url || '');

  loadProducts = async function(){
    productsEl.innerHTML='<div class="empty">Loading Shopify products…</div>';
    try{
      const r=await fetch('/api/shopify/products-multiview',{cache:'no-store'}),d=await r.json();
      if(!r.ok||!d.connected)throw new Error(readable(d.detail)||'Could not connect to Shopify');
      connEl.textContent='Connected';connEl.className='ok';countEl.textContent=String(d.products?.length||0);setConnected(true);
      productsCache=d.products||[];await loadPlans();render(productsCache);
    }catch(e){
      connEl.textContent='Disconnected';connEl.className='err';setConnected(false);
      disconnected.innerHTML='<strong>Ashes 3D services are disconnected.</strong>'+esc(e.message);
    }
  };

  render = function(products){
    if(!products.length){productsEl.innerHTML='<div class="empty">No products found.</div>';return}
    const locked=!!activeTask;
    productsEl.innerHTML=products.map((p,i)=>{
      const images=imageUrls(p), image=firstImage(p), imageCount=images.length, a=p.ashes_3d||{}, ready=!!a.ready, published=!!a.published;
      const enough=imageCount>=3;
      const primary=ready
        ? '<button class="primary" data-view="'+i+'">View 3D</button>'
        : '<button class="primary" data-generate="'+i+'" '+(!enough||locked?'disabled':'')+'>Generate 3D</button>';
      const pub=published
        ? '<button class="secondary" disabled>Published ✓</button>'
        : '<button class="secondary" data-publish="'+i+'" '+(ready?'':'disabled')+'>Publish to Shopify</button>';
      let status;
      if(published) status='Published to Shopify · '+esc(a.shopify_media_status||'PROCESSING');
      else if(ready) status='3D ready · Stored in Ashes';
      else if(imageCount===0) status='0/3 images · Add 3 product images first.';
      else if(imageCount<3) status=imageCount+'/3 images · Add '+(3-imageCount)+' more image'+((3-imageCount)===1?'':'s')+'.';
      else if(locked) status='3/3 images ready · Another product is generating.';
      else status='3/3 images ready · Multi-view generation available.';
      const thumbs=images.map((u,n)=>'<img src="'+esc(u)+'" alt="View '+(n+1)+'" style="width:34px;height:34px;object-fit:cover;border-radius:7px;border:1px solid #333">').join('');
      return '<article class="card"><div class="img">'+(image?'<img src="'+esc(image)+'">':'<span>No image</span>')+'</div><div class="meta"><div class="label">'+esc(p.status||'')+'</div><h3>'+esc(p.title)+'</h3><p>'+esc(p.handle||'')+'</p><div style="display:flex;gap:6px;margin:0 0 10px">'+thumbs+'</div><div class="actions">'+primary+pub+'</div><div class="state '+(ready?'ok':enough?'ok':'warn')+'" id="state-'+i+'">'+status+'</div></div></article>';
    }).join('');
    document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{const p=products[+b.dataset.view];openViewer(p.ashes_3d.viewer_url,p.title)});
    document.querySelectorAll('[data-generate]').forEach(b=>b.onclick=()=>startGeneration(products[+b.dataset.generate],+b.dataset.generate));
    document.querySelectorAll('[data-publish]').forEach(b=>b.onclick=()=>publishProduct(products[+b.dataset.publish],+b.dataset.publish,b));
  };

  startGeneration = async function(product,index){
    const state=$('state-'+index), images=imageUrls(product);
    if(images.length<3||activeTask){
      if(state){state.className='state warn';state.textContent='Ashes requires 3 Shopify product images from different angles.'}
      return;
    }
    lockAll('starting');state.className='state warn';state.textContent='Sending 3 product views to Ashes…';
    try{
      const r=await fetch('/api/shopify/generate-3d-multiview',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({product_id:product.id,product_name:product.title,image_urls:images.slice(0,3)})
      }),d=await r.json();
      if(!r.ok)throw new Error(readable(d.detail)||'Multi-view generation could not start');
      if(d.reused&&d.status==='COMPLETED'){activeTask=null;await loadProducts();openViewer(d.viewer_url,product.title);return}
      activeTask=d.task_id;state.textContent='TRELLIS multi-view reconstruction · 3 views';await poll(d.task_id,state);
    }catch(e){
      state.className='state err';
      state.textContent='3D generation failed: '+(e && e.message ? e.message : String(e));
      engineEl.textContent='Needs attention';
      activeTask=null;
      await loadPlans().catch(()=>{});
      document.querySelectorAll('[data-generate]').forEach(btn=>btn.disabled=false);
    }
  };

  const notice=document.querySelector('.notice');
  if(notice) notice.innerHTML='Ashes uses <b>exactly 3 Shopify product images</b> from different angles for each new 3D twin. Only one twin generates at a time. Publishing an existing twin costs 0 generation credits.';
  loadProducts();
})();
</script>
'''


class ShopifyMultiViewUIMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path != '/api/shopify/app' or response.status_code != 200:
            return response
        if 'text/html' not in response.headers.get('content-type',''):
            return response
        body=b''
        async for chunk in response.body_iterator:
            body+=chunk
        text=body.decode('utf-8',errors='replace')
        if 'ASHES_MULTIVIEW_UI_V3' not in text:
            text=text.replace('</body>',_INJECT+'</body>')
        headers=dict(response.headers)
        headers.pop('content-length',None)
        headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
        return Response(content=text,status_code=response.status_code,headers=headers,media_type='text/html')


app.add_middleware(ShopifyMultiViewUIMiddleware)
