import { Suspense, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { ContactShadows, Environment, Float, OrbitControls } from '@react-three/drei';
import { ArrowLeft, Box, Check, Copy, Download, LoaderCircle, QrCode, Rotate3D, Share2, Sparkles } from 'lucide-react';

const API_BASE=import.meta.env.VITE_API_BASE_URL||'http://localhost:8000';

function TwinGeometry({name}){
 const kind=(name||'').toLowerCase();
 if(/chair|sofa|seat|stool/.test(kind))return <group rotation={[0,-.35,0]}><mesh position={[0,-.55,0]}><boxGeometry args={[2.1,.32,1.8]}/><meshStandardMaterial color="#c9b79f" roughness={.48}/></mesh><mesh position={[0,.45,.72]} rotation={[-.12,0,0]}><boxGeometry args={[2.1,1.75,.3]}/><meshStandardMaterial color="#d7c6ae" roughness={.5}/></mesh>{[-.82,.82].map(x=><mesh key={x} position={[x,-1.1,0]}><cylinderGeometry args={[.09,.13,1.1,20]}/><meshStandardMaterial color="#1b1b1c" metalness={.7}/></mesh>)}</group>;
 if(/lamp|light|pendant/.test(kind))return <group><mesh position={[0,.15,0]}><coneGeometry args={[1.45,1.7,64,1,true]}/><meshPhysicalMaterial color="#d8d0bd" roughness={.32} side={2}/></mesh><mesh position={[0,1.6,0]}><cylinderGeometry args={[.06,.06,1.7,20]}/><meshStandardMaterial color="#262628" metalness={.8}/></mesh><pointLight position={[0,-.3,0]} intensity={18} color="#ffd99b"/></group>;
 if(/cup|mug|ceramic|bowl|plate|set/.test(kind))return <group>{[-.7,.7].map((x,i)=><mesh key={x} position={[x,-.25,i*.18]}><cylinderGeometry args={[.62,.48,1.35,64]}/><meshPhysicalMaterial color={i?'#b7a48e':'#e4ddd0'} roughness={.25} clearcoat={.35}/></mesh>)}<mesh position={[0,-1.02,0]}><cylinderGeometry args={[1.45,1.45,.12,64]}/><meshStandardMaterial color="#d5caba"/></mesh></group>;
 return <group rotation={[.08,-.35,0]}><mesh><boxGeometry args={[2.4,2.4,.75]}/><meshPhysicalMaterial color="#c2b59f" roughness={.28} metalness={.1}/></mesh><mesh position={[0,0,.4]}><boxGeometry args={[1.6,1.6,.04]}/><meshStandardMaterial color="#161618" emissive="#b9ff67" emissiveIntensity={.08}/></mesh></group>;
}

export default function PrototypeProductTwin({product,onClose}){
 const[copied,setCopied]=useState(false),[qrUrl,setQrUrl]=useState(''),[qrBusy,setQrBusy]=useState(false),[qrError,setQrError]=useState('');
 const shareUrl=useMemo(()=>{const u=new URL('/prototype',window.location.origin);u.searchParams.set('preview','1');u.searchParams.set('name',product.name||'Ashes product');if(product.image_url)u.searchParams.set('image',product.image_url);if(product.price!=null)u.searchParams.set('price',String(product.price));u.searchParams.set('currency',product.currency||'USD');return u.toString()},[product]);
 const makeQr=async()=>{if(qrUrl)return;setQrBusy(true);setQrError('');try{const response=await fetch(`${API_BASE}/api/prototype/qr`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:shareUrl})});if(!response.ok)throw new Error('QR service is unavailable.');const blob=await response.blob();setQrUrl(URL.createObjectURL(blob))}catch(e){setQrError(e.message)}finally{setQrBusy(false)}};
 const copy=async()=>{await navigator.clipboard.writeText(shareUrl);setCopied(true);setTimeout(()=>setCopied(false),1800)};
 const download=()=>{if(!qrUrl)return;const a=document.createElement('a');a.href=qrUrl;a.download=`${(product.name||'ashes-product').toLowerCase().replace(/[^a-z0-9]+/g,'-')}-qr.svg`;a.click()};
 return <section className="twin-overlay" role="dialog" aria-modal="true" aria-label={`3D preview for ${product.name}`}>
  <div className="twin-shell">
   <header><button onClick={onClose}><ArrowLeft size={16}/> Catalog</button><span><i/> INTERACTIVE TWIN · LIVE</span></header>
   <div className="twin-layout">
    <div className="twin-canvas">
     <div className="twin-hud"><span><Sparkles size={13}/> AI SHAPE PREVIEW</span><span><Rotate3D size={13}/> DRAG TO ROTATE</span></div>
     <Canvas camera={{position:[0,1,6],fov:38}}><color attach="background" args={['#09090b']}/><ambientLight intensity={1.2}/><spotLight position={[4,7,5]} intensity={45} angle={.45} penumbra={1} color="#f3eee4"/><pointLight position={[-4,1,3]} intensity={22} color="#b9ff67"/><Suspense fallback={null}><Float speed={1.25} rotationIntensity={.08} floatIntensity={.18}><TwinGeometry name={product.name}/></Float><Environment preset="studio"/><ContactShadows position={[0,-1.65,0]} opacity={.55} scale={8} blur={2.5}/></Suspense><OrbitControls enablePan={false} minDistance={4} maxDistance={8} autoRotate autoRotateSpeed={.55}/></Canvas>
     <div className="twin-badge"><Box size={15}/><span><b>Prototype twin</b>Procedural preview from catalog data</span></div>
    </div>
    <aside className="twin-panel">
     <span className="prototype-kicker">PRODUCT EXPERIENCE 03</span><h2>{product.name}</h2><p>{product.description||'An interactive Ashes product twin prepared from the imported catalog.'}</p>
     {product.image_url&&<div className="twin-source"><img src={product.image_url} alt="Source product"/><span><b>Source reference</b>Used to guide the final reconstruction</span></div>}
     <div className="twin-status"><div><Check/><span><b>Catalog</b>Imported</span></div><div><Check/><span><b>3D preview</b>Interactive</span></div><div className={qrUrl?'ready':''}><QrCode/><span><b>Smart QR</b>{qrUrl?'Generated':'Ready to generate'}</span></div></div>
     {!qrUrl?<button className="twin-generate" onClick={makeQr} disabled={qrBusy}>{qrBusy?<LoaderCircle className="spin-icon"/>:<QrCode/>}{qrBusy?'Generating smart QR…':'Generate product QR'}</button>:<div className="twin-qr"><img src={qrUrl} alt="QR code to this product preview"/><div><strong>SCAN TO OPEN THIS TWIN</strong><button onClick={copy}>{copied?<Check/>:<Copy/>}{copied?'Copied':'Copy link'}</button><button onClick={download}><Download/>Download SVG</button></div></div>}
     {qrError&&<small className="prototype-error">{qrError}</small>}
     <button className="twin-share" onClick={copy}><Share2 size={15}/>{copied?'Preview link copied':'Share preview link'}</button>
    </aside>
   </div>
  </div>
 </section>
}