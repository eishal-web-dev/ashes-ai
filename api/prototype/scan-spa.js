import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';

const USER_AGENT='AshesCatalogBot/1.2 (+read-only SPA catalog scan)';
const MAX_HTML_BYTES=2_000_000;
const MAX_SCRIPT_BYTES=5_000_000;
const MAX_TOTAL_SCRIPT_BYTES=14_000_000;
export const config={maxDuration:60};

function privateIp(address){
  if(!isIP(address))return true;
  if(address.includes(':'))return address==='::1'||address.startsWith('fc')||address.startsWith('fd')||address.startsWith('fe8')||address.startsWith('fe9')||address.startsWith('fea')||address.startsWith('feb');
  const [a,b]=address.split('.').map(Number);
  return a===10||a===127||a===0||(a===169&&b===254)||(a===172&&b>=16&&b<=31)||(a===192&&b===168)||(a>=224);
}

async function safeUrl(raw){
  let value=String(raw||'').trim();
  if(!/^https?:\/\//i.test(value))value=`https://${value}`;
  let parsed;
  try{parsed=new URL(value)}catch{throw new Error('Enter a valid public website URL.');}
  if(!['http:','https:'].includes(parsed.protocol)||!parsed.hostname)throw new Error('Only public HTTP or HTTPS websites can be scanned.');
  if(parsed.hostname==='localhost'||parsed.hostname.endsWith('.local'))throw new Error('Private websites cannot be scanned.');
  const addresses=await lookup(parsed.hostname,{all:true});
  if(!addresses.length||addresses.some(({address})=>privateIp(address)))throw new Error('Private-network websites cannot be scanned.');
  return parsed;
}

async function getText(raw,{accept,maxBytes}){
  let current=await safeUrl(raw);
  for(let redirects=0;redirects<4;redirects+=1){
    const response=await fetch(current,{redirect:'manual',signal:AbortSignal.timeout(12000),headers:{'user-agent':USER_AGENT,accept}});
    if(response.status>=300&&response.status<400&&response.headers.get('location')){
      current=await safeUrl(new URL(response.headers.get('location'),current).toString());
      continue;
    }
    if(!response.ok)throw new Error(`Website returned ${response.status}.`);
    const length=Number(response.headers.get('content-length')||0);
    if(length&&length>maxBytes)throw new Error('A website asset was too large to scan safely.');
    const text=await response.text();
    if(Buffer.byteLength(text,'utf8')>maxBytes)throw new Error('A website asset was too large to scan safely.');
    return {url:current.toString(),text};
  }
  throw new Error('The website redirected too many times.');
}

function sameSite(candidate,root){
  const host=candidate.hostname.replace(/^www\./,'');
  const rootHost=root.hostname.replace(/^www\./,'');
  return host===rootHost||host.endsWith(`.${rootHost}`)||rootHost.endsWith(`.${host}`);
}

function scriptLinks(pageUrl,html){
  const root=new URL(pageUrl);
  const links=[];
  const add=raw=>{
    try{
      const url=new URL(String(raw||'').replaceAll('&amp;','&'),pageUrl);
      if(sameSite(url,root)&&['http:','https:'].includes(url.protocol)&&/\.m?js(?:\?|$)/i.test(url.pathname+url.search))links.push(url.toString());
    }catch{/* Ignore malformed asset URLs. */}
  };
  for(const match of html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi))add(match[1]);
  for(const match of html.matchAll(/<link\b[^>]*\brel=["'][^"']*modulepreload[^"']*["'][^>]*\bhref=["']([^"']+)["'][^>]*>/gi))add(match[1]);
  for(const match of html.matchAll(/<link\b[^>]*\bhref=["']([^"']+)["'][^>]*\brel=["'][^"']*modulepreload[^"']*["'][^>]*>/gi))add(match[1]);
  return [...new Set(links)];
}

function referencedScriptLinks(baseUrl,script){
  const root=new URL(baseUrl);
  const links=[];
  for(const match of script.matchAll(/["'`]([^"'`\s]+\.m?js(?:\?[^"'`]*)?)["'`]/gi)){
    try{
      const url=new URL(match[1],baseUrl);
      if(sameSite(url,root)&&['http:','https:'].includes(url.protocol))links.push(url.toString());
    }catch{/* Ignore malformed chunk references. */}
  }
  return [...new Set(links)];
}

function money(value){
  const match=String(value??'').match(/-?\d[\d,]*(?:\.\d+)?/);
  return match?Number(match[0].replaceAll(',','')):null;
}

function decodeJsString(value){
  return String(value||'').replace(/\\n/g,' ').replace(/\\r/g,' ').replace(/\\t/g,' ').replace(/\\(["'`\\])/g,'$1').replace(/\s+/g,' ').trim();
}

function currencyFromText(text){
  if(/\bPKR\b|\bRs\.?\s*\d|₨/i.test(text))return 'PKR';
  if(/\bAED\b|د\.إ/.test(text))return 'AED';
  if(/\bSAR\b|ر\.س/.test(text))return 'SAR';
  if(/£/.test(text))return 'GBP';
  if(/€/.test(text))return 'EUR';
  if(/\bCAD\b/i.test(text))return 'CAD';
  if(/\bAUD\b/i.test(text))return 'AUD';
  return 'USD';
}

function assetAssignments(baseUrl,script){
  const assets=new Map();
  const assign=(name,raw)=>{
    try{
      const value=decodeJsString(raw);
      if(!/\.(?:png|jpe?g|webp|avif|gif)(?:\?|$)/i.test(value))return;
      assets.set(name,new URL(value,baseUrl).toString());
    }catch{/* Ignore invalid asset references. */}
  };
  for(const match of script.matchAll(/\b([A-Za-z_$][\w$]*)\s*=\s*["'`]([^"'`]+\.(?:png|jpe?g|webp|avif|gif)(?:\?[^"'`]*)?)["'`]/gi))assign(match[1],match[2]);
  for(const match of script.matchAll(/\b([A-Za-z_$][\w$]*)\s*=\s*new\s+URL\(\s*["'`]([^"'`]+\.(?:png|jpe?g|webp|avif|gif)(?:\?[^"'`]*)?)["'`]\s*,\s*import\.meta\.url\s*\)\.href/gi))assign(match[1],match[2]);
  return assets;
}

function resolveImageToken(baseUrl,token,assets){
  if(!token)return null;
  const trimmed=String(token).trim();
  if(/^["'`]/.test(trimmed)){
    try{return new URL(decodeJsString(trimmed.slice(1,-1)),baseUrl).toString()}catch{return null;}
  }
  return assets.get(trimmed)||null;
}

function productsFromScript(pageUrl,script){
  const assets=assetAssignments(pageUrl,script);
  const currency=currencyFromText(script);
  const found=[];
  const nameMatches=[...script.matchAll(/\bname\s*:\s*(["'`])((?:\\.|(?!\1).){2,180}?)\1/g)];
  for(let index=0;index<nameMatches.length;index+=1){
    const match=nameMatches[index];
    const start=match.index||0;
    const next=nameMatches[index+1]?.index;
    const end=Math.min(next??start+2600,start+2600);
    const window=script.slice(start,end);
    const priceMatch=window.match(/\bprice\s*:\s*(?:(["'`])([^"'`]{1,48})\1|(-?\d[\d,.]*))/i);
    if(!priceMatch)continue;
    const price=money(priceMatch[2]??priceMatch[3]);
    if(price===null||!Number.isFinite(price)||price<0)continue;
    const name=decodeJsString(match[2]).slice(0,180);
    if(name.length<2||/^(product|products|menu|catalog|item|items)$/i.test(name))continue;
    const descriptionMatch=window.match(/\bdescription\s*:\s*(["'`])((?:\\.|(?!\1).){2,520}?)\1/i);
    const imageMatch=window.match(/\b(?:image|imageUrl|image_url|thumbnail|photo)\s*:\s*([A-Za-z_$][\w$]*|["'`][^"'`]+["'`])/i);
    const idMatch=window.match(/\bid\s*:\s*(?:(["'`])([^"'`]{1,80})\1|(\d+))/i);
    const localCurrency=window.match(/\bcurrency\s*:\s*["'`]([A-Z]{3})["'`]/)?.[1]||currency;
    const image=resolveImageToken(pageUrl,imageMatch?.[1],assets);
    found.push({
      name,
      description:descriptionMatch?decodeJsString(descriptionMatch[2]).slice(0,320):'Imported from a client-rendered product catalog.',
      image_url:image,
      price,
      currency:localCurrency,
      source_url:pageUrl,
      external_product_id:idMatch?(idMatch[2]||idMatch[3]||null):null,
      model_url:null,
      readiness:image?'image-ready':'needs-image',
    });
  }
  return found;
}

export default async function handler(request,response){
  response.setHeader('Cache-Control','no-store, max-age=0');
  if(request.method!=='POST')return response.status(405).json({detail:'Method not allowed.'});
  try{
    const start=await getText(request.body?.url,{accept:'text/html,application/xhtml+xml',maxBytes:MAX_HTML_BYTES});
    const root=new URL(start.url);
    const queue=scriptLinks(start.url,start.text);
    const visited=new Set();
    const scripts=[];
    let totalBytes=0;
    while(queue.length&&visited.size<8&&totalBytes<MAX_TOTAL_SCRIPT_BYTES){
      const url=queue.shift();
      if(!url||visited.has(url))continue;
      visited.add(url);
      try{
        const script=await getText(url,{accept:'text/javascript,application/javascript,application/ecmascript,text/plain,*/*;q=0.5',maxBytes:MAX_SCRIPT_BYTES});
        const bytes=Buffer.byteLength(script.text,'utf8');
        if(totalBytes+bytes>MAX_TOTAL_SCRIPT_BYTES)continue;
        totalBytes+=bytes;scripts.push(script);
        for(const link of referencedScriptLinks(script.url,script.text))if(!visited.has(link)&&queue.length<12)queue.push(link);
      }catch{/* One chunk may be unavailable; continue with the others. */}
    }
    const dedup=new Map();
    for(const script of scripts){
      for(const product of productsFromScript(start.url,script.text)){
        const key=String(product.external_product_id||product.name).toLowerCase();
        const existing=dedup.get(key);
        if(!existing||(!existing.image_url&&product.image_url))dedup.set(key,product);
      }
    }
    const products=[...dedup.values()].slice(0,24);
    if(!products.length)return response.status(422).json({detail:`${root.hostname} responded, but Ashes could not find a static product catalog in its client-side JavaScript bundles. The products may be loaded from a private API after login or location selection.`,code:'SPA_CATALOG_UNREADABLE',script_count:scripts.length});
    return response.status(200).json({mode:'live',scan_method:'spa-bundle',website_url:start.url,merchant:root.hostname.replace(/^www\./,''),found:products.length,products,notice:'Read-only SPA bundle extraction. Nothing was saved or published.'});
  }catch(error){return response.status(400).json({detail:error.message||'The client-side catalog could not be scanned.'});}
}
