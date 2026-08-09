import { useEffect, useState } from 'react';
import { ArrowRight, Check, Globe2, LoaderCircle, RefreshCw, ShoppingCart, Sparkles, Store, X } from 'lucide-react';
import { getStoredBusiness } from './api';
import { getCommerceSource, importCommerceWebsite, saveCommerceSource } from './commerceApi';

const OPTIONS=[
  ['ashes','Ashes Full Store','No website yet. Ashes hosts the catalog, cart and checkout.',Store],
  ['website','Existing website','Keep your current website and use Ashes as the 3D/AR layer.',Globe2],
  ['shopify','Shopify','Connect product pages now; native cart API integration comes next.',ShoppingCart],
  ['woocommerce','WooCommerce','Use your WooCommerce store as the commerce source.',ShoppingCart],
  ['custom','Custom ecommerce','Route customers back into your own commerce system.',Globe2],
];

export default function CommerceSourceManager(){
 const [open,setOpen]=useState(false),[business,setBusiness]=useState(()=>getStoredBusiness()),[source,setSource]=useState(null),[saving,setSaving]=useState(false),[importing,setImporting]=useState(false),[result,setResult]=useState(null),[error,setError]=useState('');
 useEffect(()=>{const show=()=>{setBusiness(getStoredBusiness());setOpen(true)};window.addEventListener('ashes:open-commerce',show);return()=>window.removeEventListener('ashes:open-commerce',show)},[]);
 useEffect(()=>{if(!open||!business?.slug)return;setError('');getCommerceSource(business.slug).then(setSource).catch(e=>setError(e.message))},[open,business?.slug]);
 if(!open)return null;
 const form=source||{source_type:'ashes',website_url:'',checkout_url:'',sync_enabled:false,external_checkout:false,store_label:'Ashes Full Store'};
 const patch=v=>setSource({...form,...v});
 const save=async()=>{setSaving(true);setError('');try{setSource(await saveCommerceSource(business.slug,form))}catch(e){setError(e.message)}finally{setSaving(false)}};
 const runImport=async()=>{if(!form.website_url)return setError('Add the merchant website URL first.');setImporting(true);setError('');setResult(null);try{const r=await importCommerceWebsite(business.slug,form.website_url,14);setResult(r)}catch(e){setError(e.message)}finally{setImporting(false)}};
 return <div className="commerce-modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setOpen(false)}}><section className="commerce-studio">
  <header><div><span>ASHES COMMERCE SOURCES</span><h2>Use the store they already have.</h2><p>Import their catalog into Ashes for 3D/AR, then either hand checkout back to their website or let Ashes run the whole store.</p></div><button onClick={()=>setOpen(false)}><X size={20}/></button></header>
  {!source?<div className="commerce-loading"><LoaderCircle className="spin-icon"/> Loading commerce settings…</div>:<div className="commerce-layout"><div className="commerce-main">
   <div className="commerce-option-grid">{OPTIONS.map(([key,name,text,Icon])=><button key={key} className={form.source_type===key?'active':''} onClick={()=>patch({source_type:key,external_checkout:key!=='ashes'})}><Icon size={21}/><strong>{name}</strong><span>{text}</span>{form.source_type===key&&<i><Check size={12}/></i>}</button>)}</div>
   {form.source_type!=='ashes'&&<section className="commerce-fields"><label><span>Website / store URL</span><input value={form.website_url||''} onChange={e=>patch({website_url:e.target.value})} placeholder="https://merchant.com"/></label><label><span>Cart or checkout URL</span><input value={form.checkout_url||''} onChange={e=>patch({checkout_url:e.target.value})} placeholder="https://merchant.com/cart"/><small>For a generic website, multi-item orders are handed to this destination. One-item orders can use their exact product URL.</small></label><div className="commerce-switch-row"><label><input type="checkbox" checked={!!form.external_checkout} onChange={e=>patch({external_checkout:e.target.checked})}/><span><b>Use merchant checkout</b><small>Customers explore in Ashes, then continue on the business website to pay/order.</small></span></label><label><input type="checkbox" checked={!!form.sync_enabled} onChange={e=>patch({sync_enabled:e.target.checked})}/><span><b>Catalog sync enabled</b><small>Marks this source for future scheduled/API sync.</small></span></label></div></section>}
   {form.source_type==='ashes'&&<section className="ashes-store-upsell"><Sparkles size={24}/><div><span>ASHES FULL STORE</span><h3>No website? That becomes another sale.</h3><p>Ashes keeps the catalog, cart, QR, 3D/AR and ordering in one hosted customer storefront.</p></div></section>}
   {form.source_type!=='ashes'&&<section className="commerce-importer"><div><span>AUTHORIZED WEBSITE IMPORT</span><h3>Build their Ashes catalog from the site.</h3><p>Ashes reads structured product data and same-domain product-like pages, creates draft products, then the merchant reviews them before publishing.</p></div><button disabled={importing} onClick={runImport}>{importing?<><LoaderCircle className="spin-icon"/> Importing…</>:<><RefreshCw size={16}/> Import website catalog</>}</button></section>}
   {result&&<div className="commerce-import-result"><Check size={18}/><div><strong>{result.created} Ashes drafts created</strong><span>{result.found} products detected. Add/confirm photos before 3D generation and publishing.</span></div></div>}
   {error&&<div className="form-error">{error}</div>}
  </div><aside className="commerce-preview"><span>COMMERCE ROUTE</span><div className="commerce-route-step active"><i>1</i><div><strong>Customer scans QR</strong><small>Ashes opens 3D/AR experience</small></div></div><b>↓</b><div className="commerce-route-step active"><i>2</i><div><strong>Explore & configure</strong><small>Ashes owns the visual experience</small></div></div><b>↓</b><div className="commerce-route-step"><i>3</i><div><strong>{form.external_checkout?'Merchant checkout':'Ashes checkout'}</strong><small>{form.external_checkout?'Order/payment continues on their store':'Order stays inside Ashes'}</small></div></div><div className="commerce-route-badge">{form.source_type==='ashes'?'FULL STORE':'COMMERCE LAYER'}</div></aside></div>}
  <footer><div><span>Current model</span><strong>{form.source_type==='ashes'?'Ashes hosts commerce':'Ashes = 3D/AR layer · Merchant = commerce'}</strong></div><button className="secondary-btn" onClick={()=>setOpen(false)}>Cancel</button><button className="primary-btn" disabled={saving||!source} onClick={save}>{saving?'Saving…':'Save commerce source'} <ArrowRight size={16}/></button></footer>
 </section></div>;
}
