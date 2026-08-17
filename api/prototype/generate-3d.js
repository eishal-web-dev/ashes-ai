const MAX_ID_LENGTH=160;
const MAX_INLINE_IMAGE_BYTES=3_200_000;

function send(response,status,body){
  response.setHeader('Cache-Control','no-store, max-age=0');
  return response.status(status).json(body);
}

function validPublicUrl(value){
  try{const url=new URL(String(value||''));return url.protocol==='https:'?url.toString():null;}catch{return null;}
}

function decodeInlineImage(value){
  const raw=String(value||'');
  if(!raw)return null;
  const match=raw.match(/^data:(image\/(?:png|jpeg|webp));base64,([a-z0-9+/=\r\n]+)$/i);
  if(!match)return {error:'Upload a PNG, JPEG, or WebP image.'};
  let bytes;
  try{bytes=Buffer.from(match[2].replace(/\s+/g,''),'base64');}catch{return {error:'The uploaded image could not be decoded.'};}
  if(!bytes.length)return {error:'The uploaded image is empty.'};
  if(bytes.length>MAX_INLINE_IMAGE_BYTES)return {error:'The image is too large for direct upload. Keep it under 3 MB or use a public HTTPS image URL.',status:413};
  return {bytes,mime:match[1].toLowerCase()};
}

function workerConfig(){
  const base=validPublicUrl(process.env.ASHES_TRELLIS_WORKER_URL);
  return base?{base:base.replace(/\/$/,''),token:String(process.env.ASHES_TRELLIS_WORKER_TOKEN||'').trim()}:null;
}

function upstreamDetail(data,fallback){
  const detail=data?.detail??data?.message??data?.error;
  if(typeof detail==='string'&&detail.trim())return detail;
  if(Array.isArray(detail)){
    const parts=detail.map(item=>{
      if(typeof item==='string')return item;
      if(item&&typeof item==='object'){
        const where=Array.isArray(item.loc)?item.loc.filter(x=>x!=='body').join('.'):'request';
        const msg=item.msg||item.message||item.type;
        return [where,msg].filter(Boolean).join(': ');
      }
      return '';
    }).filter(Boolean);
    if(parts.length)return parts.join(' · ');
  }
  if(detail&&typeof detail==='object'){
    try{return JSON.stringify(detail);}catch{}
  }
  return fallback;
}

async function workerRequest(config,path,init={}){
  const headers={Accept:'application/json',...(init.headers||{})};
  if(config.token)headers.Authorization=`Bearer ${config.token}`;
  return fetch(`${config.base}${path}`,{...init,headers,signal:AbortSignal.timeout(25000)});
}

export default async function handler(request,response){
  const worker=workerConfig();
  if(!worker)return send(response,503,{detail:'The Ashes TRELLIS GPU worker is offline. Configure ASHES_TRELLIS_WORKER_URL before generating real product geometry.',code:'TRELLIS_WORKER_NOT_CONFIGURED'});
  try{
    if(request.method==='POST'){
      const productName=String(request.body?.product_name||'Product').slice(0,180);
      const inline=decodeInlineImage(request.body?.image_data_url);
      if(inline?.error)return send(response,inline.status||400,{detail:inline.error});

      let upstream;
      let viewsExpected=1;
      if(inline){
        upstream=await workerRequest(worker,'/v1/product-to-3d-file',{
          method:'POST',
          headers:{'Content-Type':inline.mime,'X-Product-Name':productName},
          body:inline.bytes,
        });
      }else{
        const imageUrl=validPublicUrl(request.body?.image_url);
        if(!imageUrl)return send(response,400,{detail:'Upload a product image or provide a public HTTPS product image URL.'});

        // Keep the Vercel -> Modal handoff deliberately minimal. The Modal worker
        // owns reconstruction settings and decides single-image vs real multi-view.
        const payload={image_url:imageUrl,product_name:productName};
        if(Array.isArray(request.body?.view_urls)){
          const viewUrls=request.body.view_urls.map(validPublicUrl).filter(Boolean).slice(0,4);
          if(viewUrls.length){payload.view_urls=viewUrls;viewsExpected=viewUrls.length;}
        }
        upstream=await workerRequest(worker,'/v1/product-to-3d',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify(payload),
        });
      }

      const data=await upstream.json().catch(()=>({}));
      if(!upstream.ok)return send(response,upstream.status,{detail:upstreamDetail(data,'The TRELLIS worker could not start this generation.'),worker_status:upstream.status});
      const taskId=String(data.task_id||data.id||'');
      if(!taskId)return send(response,502,{detail:'The TRELLIS worker did not return a task ID.'});
      return send(response,202,{task_id:taskId,status:data.status||'QUEUED',stage:data.stage||'QUEUED',views_expected:viewsExpected});
    }
    if(request.method==='GET'){
      const id=String(request.query?.id||'');
      if(!id||id.length>MAX_ID_LENGTH||!/^[a-zA-Z0-9_.:-]+$/.test(id))return send(response,400,{detail:'Invalid generation task.'});
      const upstream=await workerRequest(worker,`/v1/product-to-3d/${encodeURIComponent(id)}`);
      const data=await upstream.json().catch(()=>({}));
      if(!upstream.ok)return send(response,upstream.status,{detail:upstreamDetail(data,'The TRELLIS worker could not retrieve this generation.'),worker_status:upstream.status});
      return send(response,200,{task_id:id,status:String(data.status||'PROCESSING').toUpperCase(),stage:data.stage||null,progress:Number(data.progress||0),views:Array.isArray(data.views)?data.views.slice(0,4):[],model_url:validPublicUrl(data.model_url||data.output?.glb_url),thumbnail_url:validPublicUrl(data.thumbnail_url||data.output?.thumbnail_url),error:data.error||null});
    }
    return send(response,405,{detail:'Method not allowed.'});
  }catch(error){return send(response,500,{detail:error.name==='TimeoutError'?'The TRELLIS worker timed out. Please retry.':(error.message||'3D generation failed.')});}
}
