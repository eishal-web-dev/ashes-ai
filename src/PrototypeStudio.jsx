import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Box, Check, ExternalLink, Globe2, Image, LoaderCircle, QrCode, Rotate3D, ScanLine, ShieldCheck, Sparkles } from 'lucide-react';
import PrototypeProductTwin from './PrototypeProductTwin';

const API_BASE=import.meta.env.VITE_API_BASE_URL||'http://localhost:8000';
const STAGES=['Connecting to website','Reading product structure','Extracting catalog data','Preparing Ashes drafts'];
const SHOWCASE=[
 {name:'Sculpted Lounge Chair',price:849,currency:'USD',image_url:'https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?auto=format&fit=crop&w=1000&q=85',description:'A soft architectural lounge chair prepared for an interactive product experience.',readiness:'image-ready'},
 {name:'Stone Pendant Light',price:289,currency:'USD',image_url:'https://images.unsplash.com/photo-1540932239986-30128078f3c5?auto=format&fit=crop&w=1000&q=85',description:'Hand-finished lighting with texture and scale customers can inspect before buying.',readiness:'image-ready'},
 {name:'Minimal Ceramic Set',price:124,currency:'USD',image_url:'https://images.unsplash.com/photo-1610701596007-11502861dcfa?auto=format&fit=crop&w=1000&q=85',description:'A tactile tabletop collection ready for the Ashes 3D pipeline.',readiness:'image-ready'},
];

function money(value,currency='USD'){if(value===null||value===undefined)return 'Price unavailable';try{return new Intl.NumberFormat('en',{style:'currency',currency}).format(value)}catch{return `${currency} ${value}`}}
function safeSharedImage(value){if(!value)return null;try{const parsed=new URL(value);return ['http:','https:'].includes(parsed.protocol)?parsed.toString():null}catch{return null}}

export default function PrototypeStudio({onBack,onOpenProduct}){
 const[url,setUrl]=useState(''),[status,setStatus]=useState('idle'),[stage,setStage]=useState(0),[result,setResult]=useState(null),[error,setError]=useState(''),[selected,setSelected]=useState(0),[twinProduct,setTwinProduct]=useState(null);
 const timers=useRef([]);
 const products=result?.products||[];
 const merchant=useMemo(()=>result?.merchant||'Your imported store',[result]);
 useEffect(()=>{
  const params=new URLSearchParams(window.location.search);
  if(params.get('preview')==='1'&&params.get('name')){
   const parsedPrice=Number(params.get('price'));const shared={name:params.get('name').slice(0,180),image_url:safeSharedImage(params.get('image')),price:Number.isFinite(parsedPrice)&&parsedPrice>=0?parsedPrice:null,currency:/^[A-Z]{3}$/.test(params.get('currency')||'')?params.get('currency'):'USD',description:'Shared Ashes interactive product preview.'};
   setResult({mode:'shared',merchant:'Shared Ashes experience',found:1,products:[shared]});setStatus('ready');setTwinProduct(shared);
  }else if(params.get('demo')==='1')setTimeout(()=>useShowcase('Instant showcase selected.'),0);
  return()=>timers.current.forEach(clearTimeout);
 },[]);

 const resetTimers=()=>{timers.current.forEach(clearTimeout);timers.current=[]};
 const useShowcase=(reason='')=>{resetTimers();setStage(3);setError(reason);setSelected(0);setResult({mode:'showcase',merchant:'Ashes showcase catalog',found:SHOWCASE.length,products:SHOWCASE,notice:'Showcase catalog — used because no live merchant catalog is connected.'});setStatus('ready')};
 const scan=async e=>{
  e?.preventDefault();resetTimers();setError('');setResult(null);setSelected(0);
  let normalized=url.trim();if(!normalized)return setError('Paste a public merchant website URL first.');
  if(!/^https?:\/\//i.test(normalized))normalized='https://'+normalized;
  try{new URL(normalized)}catch{return setError('Enter a valid website URL, for example https://store.com');}
  setUrl(normalized);setStatus('scanning');setStage(0);
  [650,1350,2100].forEach((ms,i)=>timers.current.push(setTimeout(()=>setStage(i+1),ms)));
  try{
   const response=await fetch(`${API_BASE}/api/prototype/scan`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:normalized,max_pages:8})});
   if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:'This website blocked the live catalog scan.');}
   const data=await response.json();resetTimers();setStage(3);setResult(data);setStatus('ready');
  }catch(err){useShowcase(err.message||'Live scanning is unavailable right now.');}
 };
 const restart=()=>{resetTimers();window.history.replaceState({},'','/prototype');setStatus('idle');setResult(null);setError('');setStage(0);setSelected(0);setTwinProduct(null)};
 const item=products[selected];

 return <main className="prototype-page">
  <div className="prototype-grid"/>
  <nav className="prototype-nav"><button onClick={onBack}><ArrowLeft size={17}/> Back to Ashes</button><a className="brand" href="/"><span>ASHES</span><b>AI</b></a><span className="prototype-live"><i/> PROTOTYPE 01</span></nav>

  <section className="prototype-hero">
   <div className="prototype-kicker"><Sparkles size={15}/> WEBSITE → 3D COMMERCE</div>
   <h1>PASTE A STORE.<br/><span>WATCH IT BECOME AN EXPERIENCE.</span></h1>
   <p>A public Ashes AI prototype: scan a merchant website, extract its products, prepare the 3D layer and create scannable product experiences.</p>
   {status==='idle'&&<form className="prototype-url-form" onSubmit={scan}>
    <Globe2 size={20}/><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://merchant-website.com" aria-label="Merchant website URL"/>
    <button type="submit">Build catalog <ArrowRight size={17}/></button>
   </form>}
   {status==='idle'&&<button className="instant-showcase" onClick={()=>{window.history.replaceState({},'','/prototype?demo=1');useShowcase('Instant showcase selected.')}}><Sparkles size={14}/> Skip the scan — open instant showcase <ArrowRight size={14}/></button>}
   {status==='idle'&&<div className="prototype-trust"><span><ShieldCheck size={14}/> Read-only preview</span><span><ScanLine size={14}/> Public URLs only</span><span><Box size={14}/> Nothing published automatically</span></div>}
   {error&&status==='idle'&&<div className="prototype-error">{error}</div>}
  </section>

  {status==='scanning'&&<section className="prototype-scanner">
   <div className="scanner-orbit"><Globe2/><i/><i/><i/></div>
   <div><span className="prototype-kicker">ASHES VISION ENGINE</span><h2>{STAGES[stage]}</h2><p>{url}</p>
    <div className="stage-list">{STAGES.map((label,index)=><div className={index<stage?'done':index===stage?'active':''} key={label}><i>{index<stage?<Check size={13}/>:index+1}</i><span>{label}</span>{index===stage&&<LoaderCircle className="spin-icon" size={15}/>}</div>)}</div>
   </div>
  </section>}

  {status==='ready'&&item&&<section className="prototype-results">
   <header><div><span className="prototype-kicker">{result.mode==='live'?'LIVE CATALOG EXTRACT':'CURATED FALLBACK'}</span><h2>{merchant}</h2><p>{result.found} products prepared as reviewable Ashes drafts.</p></div><div className="result-actions"><button onClick={restart}>Scan another website</button><span><Check size={14}/> Extraction complete</span></div></header>
   {result.mode==='showcase'&&<div className="showcase-notice"><ShieldCheck size={17}/><div><strong>Showcase mode</strong><span>{error} The flow continues with clearly labelled sample products so the demo never dead-ends.</span></div></div>}
   <div className="prototype-workspace">
    <aside className="prototype-catalog"><div className="catalog-title"><span>EXTRACTED CATALOG</span><b>{products.length}</b></div>{products.map((product,index)=><button className={selected===index?'active':''} onClick={()=>setSelected(index)} key={product.source_url||product.name}><img src={product.image_url} alt=""/><div><strong>{product.name}</strong><span>{money(product.price,product.currency)}</span></div><i>{String(index+1).padStart(2,'0')}</i></button>)}</aside>
    <article className="prototype-product-stage">
     <div className="prototype-product-image"><div className="image-scan"/>{item.image_url?<img src={item.image_url} alt={item.name}/>:<div className="image-empty"><Image/><span>Image required</span></div>}<span className="draft-chip">DRAFT · NOT PUBLISHED</span></div>
     <div className="prototype-product-copy"><span>PRODUCT {String(selected+1).padStart(2,'0')}</span><h3>{item.name}</h3><strong>{money(item.price,item.currency)}</strong><p>{item.description||'Product information extracted from the merchant website and prepared for review.'}</p>
      <div className="readiness-row"><div><Check size={15}/><span><b>Catalog data</b>Ready</span></div><div><Rotate3D size={15}/><span><b>3D preview</b>Ready</span></div><div><QrCode size={15}/><span><b>Smart QR</b>Generate inside</span></div></div>
      <div className="prototype-product-actions"><button className="primary-btn" onClick={()=>setTwinProduct(item)}>Open interactive twin <ArrowRight size={16}/></button>{item.source_url&&<a href={item.source_url} target="_blank" rel="noreferrer">Source <ExternalLink size={14}/></a>}</div>
     </div>
    </article>
   </div>
   <footer className="prototype-next"><span>CHUNK 5 · LAUNCH READY</span><div><Rotate3D/><p><b>Interactive twins + smart QR</b>Open any product, rotate its spatial preview and generate a direct scan link.</p></div></footer>
  </section>}
  {twinProduct&&<PrototypeProductTwin product={twinProduct} onClose={()=>{setTwinProduct(null);if(new URLSearchParams(window.location.search).get('preview'))window.history.replaceState({},'','/prototype')}}/>}
 </main>
}
