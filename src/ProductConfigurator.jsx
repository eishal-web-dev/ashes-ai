import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, RotateCcw, SlidersHorizontal, Sparkles } from 'lucide-react';

const CONFIG_KEY='ashes_product_config_v1';
const PALETTES=[['obsidian','Obsidian','#17171c',0],['ivory','Ivory','#eee8dc',0],['olive','Olive','#68734a',2500],['rust','Rust','#a34f32',3000],['ocean','Ocean','#315d79',3000],['rose','Rose','#b86c79',3500]];

function inferSchema(product={}){
 const category=(product.category||'').toLowerCase(); const tags=(product.tags||[]).map(String).join(' ').toLowerCase();
 const furniture=/sofa|furniture|chair|bed|mattress|table/.test(`${category} ${tags} ${product.name||''}`.toLowerCase());
 const retail=/electronic|mobile|ups|battery|filter|appliance|light|solar/.test(`${category} ${tags}`);
 if(furniture)return {title:'Design yours',groups:[
  {id:'layout',label:'Layout',type:'chips',options:[['standard','Standard',0],['large','Large',12000],['l_left','L · Left',24000],['l_right','L · Right',24000]]},
  {id:'material',label:'Material',type:'swatches',options:PALETTES},
  {id:'finish',label:'Leg / finish',type:'chips',options:[['black','Black metal',0],['wood','Natural wood',4500],['concealed','Concealed',2500]]},
 ]};
 if(retail)return {title:'Configure yours',groups:[
  {id:'finish',label:'Finish',type:'swatches',options:PALETTES.slice(0,4)},
  {id:'package',label:'Package',type:'chips',options:[['standard','Standard',0],['plus','Plus',3500],['premium','Premium',7500]]},
  {id:'warranty',label:'Warranty',type:'chips',options:[['standard','Standard',0],['2yr','2 years',2500],['3yr','3 years',4500]]},
 ]};
 return {title:'Make it yours',groups:[
  {id:'size',label:'Size',type:'chips',options:[['regular','Regular',0],['large','Large',250],['xl','XL',450]]},
  {id:'style',label:'Style / variant',type:'chips',options:[['classic','Classic',0],['signature','Signature',300],['premium','Premium',550]]},
 ]};
}
function readSaved(id){try{return JSON.parse(localStorage.getItem(CONFIG_KEY)||'{}')[id]||null}catch{return null}}
export function configurationSurcharge(config){return Object.values(config?.priceAdjustments||{}).reduce((a,b)=>a+Number(b||0),0)}
export default function ProductConfigurator({product,onChange,compact=false}){
 const schema=useMemo(()=>inferSchema(product),[product?.id,product?.category,product?.name]);
 const defaults=useMemo(()=>Object.fromEntries(schema.groups.map(g=>[g.id,g.options[0][0]])),[schema]);
 const [selections,setSelections]=useState(()=>readSaved(product?.id)?.selections||defaults);
 useEffect(()=>{setSelections(readSaved(product?.id)?.selections||defaults)},[product?.id,defaults]);
 const config=useMemo(()=>{const priceAdjustments={};const labels={};schema.groups.forEach(g=>{const o=g.options.find(x=>x[0]===selections[g.id])||g.options[0];priceAdjustments[g.id]=Number(o?.[3]??o?.[2]??0);labels[g.label]=o?.[1]});return {version:1,productId:product?.id,selections,labels,priceAdjustments,surcharge:configurationSurcharge({priceAdjustments})}},[schema,selections,product?.id]);
 useEffect(()=>{if(!product?.id)return;let all={};try{all=JSON.parse(localStorage.getItem(CONFIG_KEY)||'{}')}catch{}all[product.id]=config;localStorage.setItem(CONFIG_KEY,JSON.stringify(all));onChange?.(config)},[config,product?.id]);
 const choose=(group,value)=>setSelections(s=>({...s,[group]:value}));
 return <section className={`ashes-configurator ${compact?'compact':''}`}><div className="configurator-title"><div><span><Sparkles size={13}/> LIVE CONFIGURATION</span><h3>{schema.title}</h3></div><button onClick={()=>setSelections(defaults)} title="Reset"><RotateCcw size={15}/></button></div>{schema.groups.map(g=><div className="config-group" key={g.id}><label>{g.label}</label><div className={g.type==='swatches'?'config-swatches':'config-chips'}>{g.options.map(o=>{const active=selections[g.id]===o[0],color=g.type==='swatches'?o[2]:null,add=Number(o?.[3]??o?.[2]??0);return <button key={o[0]} className={active?'active':''} onClick={()=>choose(g.id,o[0])} title={o[1]}>{color&&<i style={{background:color}}/>}<span>{o[1]}</span>{add>0&&<small>+Rs {add.toLocaleString()}</small>}{active&&<Check size={12}/>}</button>})}</div></div>)}<div className="config-price-line"><span><SlidersHorizontal size={14}/> Configuration</span><strong>{config.surcharge?`+ Rs ${config.surcharge.toLocaleString()}`:'Included'}</strong></div></section>
}
