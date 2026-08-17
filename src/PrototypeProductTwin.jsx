import { useMemo, useState } from 'react';
import { ArrowLeft, Box, Check, Copy, Download, LoaderCircle, QrCode, Rotate3D, Share2, Sparkles } from 'lucide-react';
import QRCode from 'qrcode';
import './prototype-viewer-controls.css';

function TwinGeometry({name}){
 const kind=(name||'').toLowerCase();
 const plate=<mesh position={[0,-1.02,0]}><cylinderGeometry args={[1.65,1.8,.16,64]}/><meshPhysicalMaterial color="#eee7db" roughness={.22} clearcoat={.45}/></mesh>;
 if(/salad|raita|chat|chaat/.test(kind))return <group>{plate}<mesh position={[0,-.72,0]}><sphereGeometry args={[1.28,64,32,0,Math.PI*2,0,Math.PI/2]}/><meshPhysicalMaterial color="#e5ded1" roughness={.26}/></mesh>{Array.from({length:28},(_,i)=>{const angle=i*2.4,r=.2+(i%6)*.14,x=Math.cos(angle)*r,z=Math.sin(angle)*r;const colors=['#58a942','#92c83e','#e54d37','#f2d25b','#d9eee0'];return <mesh key={i} position={[x,-.3+(i%4)*.08,z]} rotation={[i*.4,i*.7,0]}><dodecahedronGeometry args={[.16+(i%3)*.025,0]}/><meshStandardMaterial color={colors[i%colors.length]} roughness={.65}/></mesh>})}</group>;
 if(/fish/.test(kind))return <group>{plate}<mesh position={[0,-.35,0]} rotation={[0,0,-.08]} scale={[1.45,.42,.55]}><sphereGeometry args={[1,64,32]}/><meshPhysicalMaterial color="#c98643" roughness={.42} clearcoat={.18}/></mesh><mesh position={[.96,0,0]} rotation={[0,0,-Math.PI/2]} scale={[.8,.7,.55]}><coneGeometry args={[.65,1,3]}/><meshStandardMaterial color="#b96f34"/></mesh></group>;
 if(/pizza/.test(kind))return <group>{plate}<mesh position={[0,-.68,0]}><cylinderGeometry args={[1.48,1.48,.24,64]}/><meshStandardMaterial color="#d89b45" roughness={.7}/></mesh><mesh position={[0,-.53,0]}><cylinderGeometry args={[1.3,1.3,.08,64]}/><meshStandardMaterial color="#d84b32" roughness={.55}/></mesh>{Array.from({length:14},(_,i)=><mesh key={i} position={[Math.cos(i*2.3)*(.25+(i%4)*.25),-.45,Math.sin(i*2.3)*(.25+(i%4)*.25)]}><cylinderGeometry args={[.14,.14,.04,24]}/><meshStandardMaterial color={i%3?'#f2d37b':'#8a2e25'}/></mesh>)}</group>;
 if(/tea|lassi|drink|margarita|cola|water/.test(kind))return <group><mesh position={[0,-.15,0]}><cylinderGeometry args={[.78,.65,2.2,64]}/><meshPhysicalMaterial color="#d8c49b" transparent opacity={.76} roughness={.12} transmission={.18}/></mesh><mesh position={[0,.98,0]}><torusGeometry args={[.72,.08,20,64]}/><meshStandardMaterial color="#ece8df"/></mesh><mesh position={[.28,.9,0]} rotation={[0,0,-.16]}><cylinderGeometry args={[.045,.045,1.55,18]}/><meshStandardMaterial color="#b9ff67" metalness={.25}/></mesh></group>;
 if(/halwa|dessert|kheer|jamun|sweet/.test(kind))return <group>{plate}<mesh position={[0,-.6,0]}><cylinderGeometry args={[1.15,1.3,.55,64]}/><meshPhysicalMaterial color="#d8792d" roughness={.5}/></mesh>{Array.from({length:9},(_,i)=><mesh key={i} position={[Math.cos(i*2.1)*(.2+(i%3)*.22),-.22,Math.sin(i*2.1)*(.2+(i%3)*.22)]}><sphereGeometry args={[.13,24,16]}/><meshStandardMaterial color={i%2?'#ead48e':'#8b522d'}/></mesh>)}</group>;
 if(/chicken|mutton|kabab|kebab|tikka|handi|karahi|boti|chops|tak/.test(kind))return <group>{plate}{Array.from({length:8},(_,i)=><mesh key={i} position={[Math.cos(i*.9)*(.45+(i%3)*.25),-.5+(i%2)*.12,Math.sin(i*.9)*(.45+(i%3)*.22)]} rotation={[.15,i*.8,.12]} scale={[.72,.34,.42]}><sphereGeometry args={[.62,32,20]}/><meshPhysicalMaterial color={i%2?'#a84928':'#c26832'} roughness={.62} clearcoat={.08}/></mesh>)}</group>;
 if(/chair|sofa|seat|stool/.test(kind))return <group rotation={[0,-.35,0]}><mesh position={[0,-.55,0]}><boxGeometry args={[2.1,.32,1.8]}/><meshStandardMaterial color="#c9b79f" roughness={.48}/></mesh><mesh position={[0,.45,.72]} rotation={[-.12,0,0]}><boxGeometry args={[2.1,1.75,.3]}/><meshStandardMaterial color="#d7c6ae" roughness={.5}/></mesh>{[-.82,.82].map(x=><mesh key={x} position={[x,-1.1,0]}><cylinderGeometry args={[.09,.13,1.1,20]}/><meshStandardMaterial color="#1b1b1c" metalness={.7}/></mesh>)}</group>;
 if(/lamp|light|pendant/.test(kind))return <group><mesh position={[0,.15,0]}><coneGeometry args={[1.45,1.7,64,1,true]}/><meshPhysicalMaterial color="#d8d0bd" roughness={.32} side={2}/></mesh><mesh position={[0,1.6,0]}><cylinderGeometry args={[.06,.06,1.7,20]}/><meshStandardMaterial color="#262628" metalness={.8}/></mesh><pointLight position={[0,-.3,0]} intensity={18} color="#ffd99b"/></group>;
 if(/cup|mug|ceramic|bowl|plate|set/.test(kind))return <group>{[-.7,.7].map((x,i)=><mesh key={x} position={[x,-.25,i*.18]}><cylinderGeometry args={[.62,.48,1.35,64]}/><meshPhysicalMaterial color={i?'#b7a48e':'#e4ddd0'} roughness={.25} clearcoat={.35}/></mesh>)}<mesh position={[0,-1.02,0]}><cylinderGeometry args={[1.45,1.45,.12,64]}/><meshStandardMaterial color="#d5caba"/></mesh></group>;
 return <group rotation={[.08,-.35,0]}><mesh><boxGeometry args={[2.4,2.4,.75]}/><meshPhysicalMaterial color="#c2b59f" roughness={.28} metalness={.1}/></mesh><mesh position={[0,0,.4]}><boxGeometry args={[1.6,1.6,.04]}/><meshStandardMaterial color="#161618" emissive="#b9ff67" emissiveIntensity={.08}/></mesh></group>;
}

export default function PrototypeProductTwin({product,onClose}){
 const[copied,setCopied]=useState(false),[qrUrl,setQrUrl]=useState(''),[qrBusy,setQrBusy]=useState(false),[qrError,setQrError]=useState('');
 const[generatedModel,setGeneratedModel]=useState(''),[generationState,setGenerationState]=useState('idle'),[generationProgress,setGenerationProgress]=useState(0),[generationStage,setGenerationStage]=useState(''),[generatedViews,setGeneratedViews]=useState([]),[generationError,setGenerationError]=useState('');
 const[viewerScale,setViewerScale]=useState(1),[viewerX,setViewerX]=useState(0),[viewerY,setViewerY]=useState(0),[viewerZ,setViewerZ]=useState(0),[viewerLight,setViewerLight]=useState(1),[viewerGrid,setViewerGrid]=useState(true);
 const assetModel=product.model_url||generatedModel;
 const shareUrl=useMemo(()=>{const u=new URL('/prototype',window.location.origin);u.searchParams.set('preview','1');u.searchParams.set('name',product.name||'Ashes product');if(product.image_url)u.searchParams.set('image',product.image_url);if(assetModel)u.searchParams.set('model',assetModel);if(product.price!=null)u.searchParams.set('price',String(product.price));u.searchParams.set('currency',product.currency||'USD');return u.toString()},[product,assetModel]);
 const resetViewer=()=>{setViewerScale(1);setViewerX(0);setViewerY(0);setViewerZ(0);setViewerLight(1);setViewerGrid(true)};
 const generate3d=async()=>{
  if(!product.image_url||generationState==='working')return;
  setGenerationState('working');setGenerationProgress(1);setGenerationError('');
  try{
   const started=await fetch('/api/prototype/generate-3d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image_url:product.image_url,product_name:product.name})});
   const startBody=await started.json().catch(()=>({}));
   if(!started.ok)throw new Error(startBody.detail||'Could not start real 3D generation.');
   for(let attempt=0;attempt<240;attempt+=1){
    await new Promise(resolve=>setTimeout(resolve,5000));
    const check=await fetch(`/api/prototype/generate-3d?id=${encodeURIComponent(startBody.task_id)}`,{cache:'no-store'});
    const task=await check.json().catch(()=>({}));
    if(!check.ok)throw new Error(task.detail||'Could not check the 3D generation.');
    setGenerationProgress(Math.max(1,Math.min(99,Number(task.progress||attempt+2))));setGenerationStage(task.stage||'RECONSTRUCTING_3D');if(Array.isArray(task.views))setGeneratedViews(task.views.slice(0,4));
    if(['SUCCEEDED','COMPLETED'].includes(task.status)&&task.model_url){setGeneratedModel(task.model_url);setGenerationProgress(100);setGenerationState('done');return;}
    if(['FAILED','CANCELED','EXPIRED'].includes(task.status))throw new Error(task.error||`3D generation ${task.status.toLowerCase()}.`);
   }
   throw new Error('3D generation is still running after 20 minutes. Check the 3D worker before retrying.');
  }catch(error){setGenerationState('error');setGenerationError(error.message||'3D generation failed.');}
 };
 const makeQr=async()=>{if(qrUrl)return;setQrBusy(true);setQrError('');try{const svg=await QRCode.toString(shareUrl,{type:'svg',errorCorrectionLevel:'M',margin:2,width:320,color:{dark:'#09090b',light:'#ffffff'}});setQrUrl(URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'})))}catch(e){setQrError(e.message||'QR generation failed.')}finally{setQrBusy(false)}};
 const copy=async()=>{await navigator.clipboard.writeText(shareUrl);setCopied(true);setTimeout(()=>setCopied(false),1800)};
 const download=()=>{if(!qrUrl)return;const a=document.createElement('a');a.href=qrUrl;a.download=`${(product.name||'ashes-product').toLowerCase().replace(/[^a-z0-9]+/g,'-')}-qr.svg`;a.click()};
 return <section className="twin-overlay" role="dialog" aria-modal="true" aria-label={`3D preview for ${product.name}`}>
  <div className="twin-shell">
   <header><button onClick={onClose}><ArrowLeft size={16}/> Catalog</button><span><i/> INTERACTIVE TWIN · LIVE</span></header>
   <div className="twin-layout">
    <div className="twin-canvas twin-canvas-compact">
     <div className="twin-hud"><span><Sparkles size={13}/> {assetModel?'REAL PRODUCT 3D · GLB':generationState==='working'?'BUILDING PRODUCT GEOMETRY':'SOURCE PHOTO · NOT 3D'}</span>{assetModel&&<span><Rotate3D size={13}/> DRAG TO ROTATE</span>}</div>
     {assetModel?<div className={`twin-viewer-stage${viewerGrid?' grid-on':''}`}><model-viewer src={assetModel} alt={`Interactive 3D model of ${product.name}`} camera-controls auto-rotate shadow-intensity={String(Math.min(2.4,viewerLight))} exposure={String(viewerLight)} scale={`${viewerScale} ${viewerScale} ${viewerScale}`} camera-target={`${viewerX}m ${viewerY}m ${viewerZ}m`} interaction-prompt="auto" style={{width:'100%',height:'100%',background:'transparent'}}/></div>:product.image_url?<div className="twin-honest-source"><img src={product.image_url} alt={`Source photograph of ${product.name}`}/><span>{generationState==='working'?`${generationStage.replaceAll('_',' ').toLowerCase()} · ${generationProgress}%`:'SOURCE IMAGE — GENERATE 3D TO ROTATE THE PRODUCT'}</span></div>:<div className="image-empty"><Box/><span>No real 3D model or product photo available</span></div>}
     <div className="twin-badge"><Box size={15}/><span><b>{assetModel?'Real 3D asset':'No fake 3D preview'}</b>{assetModel?(product.model_url?'Loaded from the merchant product page':'Reconstructed by Ashes TRELLIS into a GLB'):'The source remains a flat photo until the GPU pipeline returns actual geometry'}</span></div>
    </div>
    <aside className="twin-panel">
     <span className="prototype-kicker">PRODUCT EXPERIENCE 03</span><h2>{product.name}</h2><p>{product.description||'An interactive Ashes product twin prepared from the imported catalog.'}</p>
     {product.image_url&&<div className="twin-source"><img src={product.image_url} alt="Product reference"/><span><b>{product.image_source_url?'Reference image':'Source product'}</b>{product.image_source_url?'Third-party reference — not the restaurant’s actual dish':'Displayed directly; no fake reconstruction'}</span></div>}
     {assetModel&&<div className="twin-viewer-controls">
      <div className="twin-viewer-controls-head"><strong>3D VIEW CONTROLS</strong><button type="button" onClick={resetViewer}>Reset</button></div>
      <label className="twin-control-wide"><span>Size <b>{viewerScale.toFixed(2)}×</b></span><input type="range" min="0.35" max="2.2" step="0.05" value={viewerScale} onChange={e=>setViewerScale(Number(e.target.value))}/></label>
      <div className="twin-move-grid">
       <label><span>Move X <b>{viewerX.toFixed(2)}</b></span><input type="range" min="-1.5" max="1.5" step="0.05" value={viewerX} onChange={e=>setViewerX(Number(e.target.value))}/></label>
       <label><span>Move Y <b>{viewerY.toFixed(2)}</b></span><input type="range" min="-1.5" max="1.5" step="0.05" value={viewerY} onChange={e=>setViewerY(Number(e.target.value))}/></label>
       <label><span>Move Z <b>{viewerZ.toFixed(2)}</b></span><input type="range" min="-1.5" max="1.5" step="0.05" value={viewerZ} onChange={e=>setViewerZ(Number(e.target.value))}/></label>
      </div>
      <label className="twin-control-wide"><span>Lighting <b>{viewerLight.toFixed(2)}</b></span><input type="range" min="0.35" max="2.5" step="0.05" value={viewerLight} onChange={e=>setViewerLight(Number(e.target.value))}/></label>
      <label className="twin-grid-toggle"><input type="checkbox" checked={viewerGrid} onChange={e=>setViewerGrid(e.target.checked)}/><span>Show floor grid</span></label>
     </div>}
     {!assetModel&&product.image_url&&<div className="twin-real3d">
      <button className="twin-generate" onClick={generate3d} disabled={generationState==='working'}>{generationState==='working'?<LoaderCircle className="spin-icon"/>:<Sparkles/>}{generationState==='working'?(`Generating real 3D… ${generationProgress}%`):generationState==='error'?'Retry real 3D generation':'Generate real 3D from this image'}</button>
      <small>Ashes TRELLIS reconstructs and textures a genuine GLB mesh. Multiple real views are used when the source provides them.</small>
      {generatedViews.length>0&&<div className="twin-generated-views">{generatedViews.map((view,index)=><img key={view||index} src={view} alt={`Generated product view ${index+1}`}/>)}</div>}
     </div>}
     {generationError&&<small className="prototype-error">{generationError}</small>}
     <div className="twin-status"><div><Check/><span><b>Catalog</b>Imported</span></div><div><Check/><span><b>Asset type</b>{assetModel?'Real interactive 3D':product.image_url?'Source photo only':'No 3D asset'}</span></div><div className={qrUrl?'ready':''}><QrCode/><span><b>Smart QR</b>{qrUrl?'Generated':'Ready to generate'}</span></div></div>
     {!qrUrl?<button className="twin-generate" onClick={makeQr} disabled={qrBusy}>{qrBusy?<LoaderCircle className="spin-icon"/>:<QrCode/>}{qrBusy?'Generating smart QR…':'Generate product QR'}</button>:<div className="twin-qr"><img src={qrUrl} alt="QR code to this product preview"/><div><strong>SCAN TO OPEN THIS TWIN</strong><button onClick={copy}>{copied?<Check/>:<Copy/>}{copied?'Copied':'Copy link'}</button><button onClick={download}><Download/>Download SVG</button></div></div>}
     {qrError&&<small className="prototype-error">{qrError}</small>}
     <button className="twin-share" onClick={copy}><Share2 size={15}/>{copied?'Preview link copied':'Share preview link'}</button>
    </aside>
   </div>
  </div>
 </section>
}
