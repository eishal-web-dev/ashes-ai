const MESHY_API='https://api.meshy.ai/openapi/v1/image-to-3d';

function send(response,status,body){
  response.setHeader('Cache-Control','no-store, max-age=0');
  return response.status(status).json(body);
}

function validImageUrl(value){
  try{
    const url=new URL(String(value||''));
    return url.protocol==='https:'?url.toString():null;
  }catch{return null;}
}

export default async function handler(request,response){
  const key=process.env.MESHY_API_KEY;
  if(!key)return send(response,503,{detail:'Real 3D generation is not configured yet. Add MESHY_API_KEY to the Vercel project.'});
  try{
    if(request.method==='POST'){
      const imageUrl=validImageUrl(request.body?.image_url);
      if(!imageUrl)return send(response,400,{detail:'A public HTTPS product image is required.'});
      const upstream=await fetch(MESHY_API,{
        method:'POST',
        signal:AbortSignal.timeout(20000),
        headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json'},
        body:JSON.stringify({
          image_url:imageUrl,
          model_type:'standard',
          ai_model:'latest',
          should_texture:true,
          enable_pbr:true,
          target_formats:['glb']
        })
      });
      const data=await upstream.json().catch(()=>({}));
      if(!upstream.ok)return send(response,upstream.status,{detail:data.message||data.detail||'The 3D provider could not start this generation.'});
      return send(response,202,{task_id:data.result||data.id,status:'PENDING'});
    }
    if(request.method==='GET'){
      const id=String(request.query?.id||'');
      if(!/^[a-zA-Z0-9-]{8,80}$/.test(id))return send(response,400,{detail:'Invalid generation task.'});
      const upstream=await fetch(`${MESHY_API}/${encodeURIComponent(id)}`,{
        signal:AbortSignal.timeout(15000),
        headers:{Authorization:`Bearer ${key}`}
      });
      const data=await upstream.json().catch(()=>({}));
      if(!upstream.ok)return send(response,upstream.status,{detail:data.message||data.detail||'The 3D provider could not retrieve this generation.'});
      return send(response,200,{
        task_id:data.id,
        status:data.status,
        progress:Number(data.progress||0),
        model_url:data.model_urls?.glb||null,
        thumbnail_url:data.thumbnail_url||null,
        error:data.task_error?.message||null
      });
    }
    return send(response,405,{detail:'Method not allowed.'});
  }catch(error){
    return send(response,500,{detail:error.name==='TimeoutError'?'The 3D provider timed out. Please retry.':(error.message||'3D generation failed.')});
  }
}
