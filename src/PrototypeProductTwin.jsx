import { Suspense, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { ContactShadows, Environment, Float, OrbitControls, Image as DreiImage, RoundedBox } from '@react-three/drei';
import { ArrowLeft, Box, Check, Copy, Download, LoaderCircle, QrCode, Rotate3D, Share2, Sparkles } from 'lucide-react';
import QRCode from 'qrcode';

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

function PhotoTwin({product}){
 return <group rotation={[0,-.12,0]}>
  <mesh position={[0,-1.42,0]} receiveShadow>
   <cylinderGeometry args={[1.75,2.05,.2,96]}/>
   <meshPhysicalMaterial color="#111315" metalness={.72} roughness={.2} clearcoat={1}/>
  </mesh>
  <mesh position={[0,-1.29,0]}>
   <torusGeometry args={[1.55,.025,16,96]}/>
   <meshStandardMaterial color="#b9ff67" emissive="#b9ff67" emissiveIntensity={2.4}/>
  </mesh>
  <RoundedBox args={[3.5,3.5,.18]} radius={.14} smoothness={8} position={[0,.25,-.12]} castShadow>
   <meshPhysicalMaterial color="#17191b" metalness={.3} roughness={.18} clearcoat={.9}/>
  </RoundedBox>
  <DreiImage url={product.image_url} position={[0,.25,.01]} scale={[3.28,3.28]} radius={.1} transparent toneMapped/>
  <mesh position={[0,.25,-.24]}>
   <planeGeometry args={[3.85,3.85]}/>
   <meshBasicMaterial color="#b9ff67" transparent opacity={.035}/>
  </mesh>
 </group>;
}

export default function PrototypeProductTwin({product,onClose}){
 const[copied,setCopied]=useState(false),[qrUrl,setQrUrl]=useState(''),[qrBusy,setQrBusy]=useState(false),[qrError,setQrError]=useState('');
 const shareUrl=useMemo(()=>{const u=new URL('/prototype',window.location.origin);u.searchParams.set('preview','1');u.searchParams.set('name',product.name||'Ashes product');if(product.image_url)u.searchParams.set('image',product.image_url);if(product.model_url)u.searchParams.set('model',product.model_url);if(product.price!=null)u.searchParams.set('price',String(product.price));u.searchParams.set('currency',product.currency||'USD');return u.toString()},[product]);
 const makeQr=async()=>{if(qrUrl)return;setQrBusy(true);setQrError('');try{const svg=await QRCode.toString(shareUrl,{type:'svg',errorCorrectionLevel:'M',margin:2,width:320,color:{dark:'#09090b',light:'#ffffff'}});setQrUrl(URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'})))}catch(e){setQrError(e.message||'QR generation failed.')}finally{setQrBusy(false)}};
 const copy=async()=>{await navigator.clipboard.writeText(shareUrl);setCopied(true);setTimeout(()=>setCopied(false),1800)};
 const download=()=>{if(!qrUrl)return;const a=document.createElement('a');a.href=qrUrl;a.download=`${(product.name||'ashes-product').toLowerCase().replace(/[^a-z0-9]+/g,'-')}-qr.svg`;a.click()};
 return <section className="twin-overlay" role="dialog" aria-modal="true" aria-label={`3D preview for ${product.name}`}>
  <div className="twin-shell">
   <header><button onClick={onClose}><ArrowLeft size={16}/> Catalog</button><span><i/> INTERACTIVE TWIN · LIVE</span></header>
   <div className="twin-layout">
    <div className="twin-canvas">
     <div className="twin-hud"><span><Sparkles size={13}/> {product.model_url?'REAL PRODUCT 3D · GLB':product.image_url?'SOURCE PHOTO · SPATIAL DISPLAY':'NO 3D ASSET'}</span><span><Rotate3D size={13}/> DRAG TO ROTATE</span></div>
     {product.model_url?<model-viewer src={product.model_url} alt={`Interactive 3D model of ${product.name}`} camera-controls auto-rotate shadow-intensity="1" exposure="1" interaction-prompt="auto" style={{width:'100%',height:'100%',background:'#09090b'}}/>:product.image_url?<Canvas shadows dpr={[1,1.75]} camera={{position:[0,.45,6.4],fov:34}} gl={{antialias:true,toneMappingExposure:1.08}}><color attach="background" args={['#070809']}/><fog attach="fog" args={['#070809',7.5,12]}/><ambientLight intensity={.45}/><spotLight position={[4,7,5]} intensity={58} angle={.38} penumbra={.85} color="#fff5e8" castShadow/><pointLight position={[-4,1.5,3]} intensity={18} color="#b9ff67"/><pointLight position={[3,-1,2]} intensity={10} color="#7b61ff"/><Suspense fallback={null}><Float speed={.72} rotationIntensity={.035} floatIntensity={.12}><PhotoTwin product={product}/></Float><Environment preset="studio"/><ContactShadows position={[0,-1.55,0]} opacity={.72} scale={9} blur={2.8} far={5}/></Suspense><OrbitControls enablePan={false} enableDamping dampingFactor={.06} minDistance={4.8} maxDistance={8} minPolarAngle={Math.PI*.32} maxPolarAngle={Math.PI*.64} autoRotate autoRotateSpeed={.22}/></Canvas>:<div className="image-empty"><Box/><span>No real 3D model or product photo available</span></div>}
     <div className="twin-badge"><Box size={15}/><span><b>{product.model_url?'Real 3D asset':product.image_url?'Spatial photo preview':'3D unavailable'}</b>{product.model_url?'Loaded from the merchant product page':product.image_url?'Displays the source product photo without inventing geometry':'A real model requires product photography or a GLB file'}</span></div>
    </div>
    <aside className="twin-panel">
     <span className="prototype-kicker">PRODUCT EXPERIENCE 03</span><h2>{product.name}</h2><p>{product.description||'An interactive Ashes product twin prepared from the imported catalog.'}</p>
     {product.image_url&&<div className="twin-source"><img src={product.image_url} alt="Product reference"/><span><b>{product.image_source_url?'Reference image':'Source product'}</b>{product.image_source_url?'Third-party reference — not the restaurant’s actual dish':'Displayed directly; no fake reconstruction'}</span></div>}
     <div className="twin-status"><div><Check/><span><b>Catalog</b>Imported</span></div><div><Check/><span><b>Asset type</b>{product.model_url?'Real interactive 3D':product.image_url?'Spatial photo preview':'No 3D asset'}</span></div><div className={qrUrl?'ready':''}><QrCode/><span><b>Smart QR</b>{qrUrl?'Generated':'Ready to generate'}</span></div></div>
     {!qrUrl?<button className="twin-generate" onClick={makeQr} disabled={qrBusy}>{qrBusy?<LoaderCircle className="spin-icon"/>:<QrCode/>}{qrBusy?'Generating smart QR…':'Generate product QR'}</button>:<div className="twin-qr"><img src={qrUrl} alt="QR code to this product preview"/><div><strong>SCAN TO OPEN THIS TWIN</strong><button onClick={copy}>{copied?<Check/>:<Copy/>}{copied?'Copied':'Copy link'}</button><button onClick={download}><Download/>Download SVG</button></div></div>}
     {qrError&&<small className="prototype-error">{qrError}</small>}
     <button className="twin-share" onClick={copy}><Share2 size={15}/>{copied?'Preview link copied':'Share preview link'}</button>
    </aside>
   </div>
  </div>
 </section>
}
