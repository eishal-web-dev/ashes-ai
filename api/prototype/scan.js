import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';

const USER_AGENT='AshesCatalogBot/1.1 (+read-only prototype catalog scan)';

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

async function getHtml(raw){
  let current=await safeUrl(raw);
  for(let redirects=0;redirects<4;redirects+=1){
    const response=await fetch(current,{redirect:'manual',signal:AbortSignal.timeout(10000),headers:{'user-agent':USER_AGENT,accept:'text/html,application/xhtml+xml'}});
    if(response.status>=300&&response.status<400&&response.headers.get('location')){current=await safeUrl(new URL(response.headers.get('location'),current).toString());continue;}
    if(!response.ok)throw new Error(`Website returned ${response.status}.`);
    if(!(response.headers.get('content-type')||'').toLowerCase().includes('html'))throw new Error('The URL did not return an HTML page.');
    return {url:current.toString(),html:(await response.text()).slice(0,2_000_000)};
  }
  throw new Error('The website redirected too many times.');
}

function walk(value,visit){
  if(Array.isArray(value))value.forEach(item=>walk(item,visit));
  else if(value&&typeof value==='object'){visit(value);Object.values(value).forEach(item=>walk(item,visit));}
}

function money(value){
  const match=String(value??'').match(/-?\d[\d,]*(?:\.\d+)?/);
  return match?Number(match[0].replaceAll(',','')):null;
}

function modelUrl(pageUrl,html){
  const normalized=html.replaceAll('\\/','/').replaceAll('\\u002F','/').replaceAll('\\u002f','/');
  const match=normalized.match(/https?:\/\/[^"'<>\s]+?(?:\.glb(?:\?[^"'<>\s]*)?|glb_draco[^"'<>\s]*)/i)||normalized.match(/(?:src|data-src|gltf-model)=["']([^"']*(?:\.glb|glb_draco)[^"']*)["']/i);
  if(!match)return null;
  try{return new URL(match[1]||match[0],pageUrl).toString()}catch{return null;}
}

function productsFromPage(pageUrl,html){
  const found=[];
  const model=modelUrl(pageUrl,html);
  const scriptPattern=/<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  for(const match of html.matchAll(scriptPattern)){
    try{
      const data=JSON.parse(match[1].trim());
      walk(data,node=>{
        const types=Array.isArray(node['@type'])?node['@type']:[node['@type']];
        if(!types.includes('Product')||!node.name)return;
        const offer=Array.isArray(node.offers)?node.offers[0]:(node.offers||{});
        let image=Array.isArray(node.image)?node.image[0]:node.image;
        if(image&&typeof image==='object')image=image.url||image.contentUrl;
        found.push({name:String(node.name).trim().slice(0,180),description:String(node.description||'').replace(/<[^>]*>/g,' ').trim().slice(0,320)||null,image_url:typeof image==='string'?new URL(image,pageUrl).toString():null,price:money(offer.price),currency:offer.priceCurrency||'USD',source_url:pageUrl,external_product_id:node.sku||node.productID||node.mpn||null,model_url:model,readiness:model?'real-3d':(image?'image-ready':'needs-image')});
      });
    }catch{/* Ignore malformed merchant JSON-LD. */}
  }
  return found;
}

function productLinks(pageUrl,html){
  const root=new URL(pageUrl);
  const links=[];
  for(const match of html.matchAll(/<a\b[^>]*href=["']([^"'#]+)["']/gi)){
    try{const url=new URL(match[1].replaceAll('&amp;','&'),pageUrl);if(url.hostname===root.hostname&&/(\/products?\/|\/p\/|\/item\/|\/shop\/)/i.test(url.pathname))links.push(url.toString().split('#')[0]);}catch{/* Ignore invalid links. */}
  }
  return [...new Set(links)];
}

export default async function handler(request,response){
  if(request.method!=='POST')return response.status(405).json({detail:'Method not allowed.'});
  try{
    const start=await getHtml(request.body?.url);
    const limit=Math.max(1,Math.min(Number(request.body?.max_pages)||8,16));
    const pages=[start];
    for(const link of productLinks(start.url,start.html).slice(0,limit)){
      try{pages.push(await getHtml(link));}catch{/* Continue when an individual product blocks crawling. */}
    }
    const dedup=new Map();
    for(const page of pages)for(const product of productsFromPage(page.url,page.html)){const key=String(product.external_product_id||product.source_url||product.name).toLowerCase();if(!dedup.has(key))dedup.set(key,product);}
    const products=[...dedup.values()].slice(0,16);
    if(!products.length)return response.status(422).json({detail:'The website responded, but no structured products were found. Try a direct store or collection page.'});
    const host=new URL(start.url).hostname.replace(/^www\./,'');
    return response.status(200).json({mode:'live',website_url:start.url,merchant:host,found:products.length,products,notice:'Read-only preview. Nothing was saved or published.'});
  }catch(error){return response.status(400).json({detail:error.message||'The website could not be scanned.'});}
}
