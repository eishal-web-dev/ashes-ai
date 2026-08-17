import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';

const USER_AGENT='AshesCatalogBot/1.4 (+read-only public visual catalog scan)';
const MAX_HTML_BYTES=2_000_000;
const MAX_PAGES=8;
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

async function getHtml(raw){
  let current=await safeUrl(raw);
  for(let redirects=0;redirects<4;redirects+=1){
    const response=await fetch(current,{redirect:'manual',signal:AbortSignal.timeout(10000),headers:{'user-agent':USER_AGENT,accept:'text/html,application/xhtml+xml'}});
    if(response.status>=300&&response.status<400&&response.headers.get('location')){
      current=await safeUrl(new URL(response.headers.get('location'),current).toString());
      continue;
    }
    if(!response.ok)throw new Error(`Website returned ${response.status}.`);
    const type=(response.headers.get('content-type')||'').toLowerCase();
    if(!type.includes('html'))throw new Error('The URL did not return a public HTML page.');
    const text=await response.text();
    if(Buffer.byteLength(text,'utf8')>MAX_HTML_BYTES)throw new Error('The website page was too large to scan safely.');
    return {url:current.toString(),html:text};
  }
  throw new Error('The website redirected too many times.');
}

function attr(tag,name){
  const pattern=new RegExp(`\\b${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`,'i');
  const match=String(tag||'').match(pattern);
  return match?(match[1]??match[2]??match[3]??''):'';
}

function cleanText(value){
  return String(value||'')
    .replace(/<script[\s\S]*?<\/script>/gi,' ')
    .replace(/<style[\s\S]*?<\/style>/gi,' ')
    .replace(/<[^>]+>/g,' ')
    .replace(/&amp;/gi,'&').replace(/&quot;/gi,'"').replace(/&#39;|&apos;/gi,"'")
    .replace(/&nbsp;/gi,' ').replace(/\s+/g,' ').trim();
}

function meta(html,key){
  const escaped=key.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  const patterns=[
    new RegExp(`<meta\\b[^>]*(?:property|name)=["']${escaped}["'][^>]*content=["']([^"']+)["'][^>]*>`,'i'),
    new RegExp(`<meta\\b[^>]*content=["']([^"']+)["'][^>]*(?:property|name)=["']${escaped}["'][^>]*>`,'i'),
  ];
  for(const pattern of patterns){const match=html.match(pattern);if(match)return cleanText(match[1]);}
  return '';
}

function pageTitle(html){
  return meta(html,'og:title')||meta(html,'twitter:title')||cleanText(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]||'');
}

function pageDescription(html){
  return meta(html,'og:description')||meta(html,'description')||meta(html,'twitter:description')||'';
}

function normaliseImage(raw,pageUrl){
  const value=String(raw||'').trim().replaceAll('&amp;','&');
  if(!value||value.startsWith('data:')||value.startsWith('blob:'))return null;
  try{
    const url=new URL(value,pageUrl);
    if(!['http:','https:'].includes(url.protocol))return null;
    return url.toString();
  }catch{return null;}
}

function bestImageFromTag(tag,pageUrl){
  const src=attr(tag,'data-src')||attr(tag,'data-lazy-src')||attr(tag,'data-original')||attr(tag,'src');
  const srcset=attr(tag,'srcset')||attr(tag,'data-srcset');
  if(srcset){
    const candidates=srcset.split(',').map(part=>part.trim().split(/\s+/)[0]).filter(Boolean);
    const picked=candidates.at(-1);
    const url=normaliseImage(picked,pageUrl);
    if(url)return url;
  }
  return normaliseImage(src,pageUrl);
}

function imageLooksUseful(url,tag=''){
  const lower=`${url} ${attr(tag,'alt')} ${attr(tag,'class')} ${attr(tag,'id')}`.toLowerCase();
  if(/logo|favicon|icon|sprite|avatar|profile|social|facebook|instagram|youtube|whatsapp|payment|badge|loader|placeholder|tracking|pixel/.test(lower))return false;
  const width=Number(attr(tag,'width')||0),height=Number(attr(tag,'height')||0);
  if((width&&width<120)||(height&&height<120))return false;
  return true;
}

function filenameName(url){
  try{
    const file=decodeURIComponent(new URL(url).pathname.split('/').pop()||'').replace(/\.[a-z0-9]{2,5}$/i,'').replace(/[-_]+/g,' ').replace(/\b(?:img|image|photo|product|webp|png|jpg|jpeg)\b/gi,' ').replace(/\s+/g,' ').trim();
    return file.length>=3?file:'';
  }catch{return '';}
}

function nearbyName(tag,url,fallback){
  const text=cleanText(attr(tag,'alt')||attr(tag,'title')||attr(tag,'aria-label'));
  if(text.length>=2&&!/^(image|photo|product|picture)$/i.test(text))return text.slice(0,180);
  return (filenameName(url)||fallback||'Product image').slice(0,180);
}

function productishLinks(pageUrl,html){
  const root=new URL(pageUrl);
  const out=[];
  for(const match of html.matchAll(/<a\b[^>]*href=["']([^"'#]+)["'][^>]*>/gi)){
    try{
      const url=new URL(match[1].replaceAll('&amp;','&'),pageUrl);
      const related=url.hostname.replace(/^www\./,'')===root.hostname.replace(/^www\./,'');
      if(related&&/(?:\/products?\/|\/shop\/|\/store\/|\/item\/|\/menu\/|\/flavou?r|\/collections?\/)/i.test(url.pathname))out.push(url.toString().split('#')[0]);
    }catch{/* ignore malformed links */}
  }
  return [...new Set(out)].slice(0,MAX_PAGES-1);
}

function candidatesFromPage(pageUrl,html,{rootPage=false}={}){
  const title=pageTitle(html);
  const description=pageDescription(html);
  const candidates=[];
  const add=(image,name,source=pageUrl,desc=description)=>{
    if(!image||!imageLooksUseful(image))return;
    candidates.push({
      name:(name||title||filenameName(image)||'Product image').slice(0,180),
      description:(desc||'Public product image candidate detected by Ashes. Review before generating 3D.').slice(0,320),
      image_url:image,
      price:null,
      currency:'USD',
      source_url:source,
      external_product_id:null,
      model_url:null,
      readiness:'image-ready',
      confidence:'visual-candidate',
    });
  };

  const ogImage=normaliseImage(meta(html,'og:image')||meta(html,'twitter:image'),pageUrl);
  if(ogImage)add(ogImage,title,pageUrl,description);

  for(const match of html.matchAll(/<img\b[^>]*>/gi)){
    const tag=match[0];
    const image=bestImageFromTag(tag,pageUrl);
    if(!image||!imageLooksUseful(image,tag))continue;
    add(image,nearbyName(tag,image,rootPage?title:''),pageUrl,description);
  }
  return candidates;
}

export default async function handler(request,response){
  response.setHeader('Cache-Control','no-store, max-age=0');
  if(request.method!=='POST')return response.status(405).json({detail:'Method not allowed.'});
  try{
    const start=await getHtml(request.body?.url);
    const root=new URL(start.url);
    const pages=[start];
    for(const link of productishLinks(start.url,start.html)){
      try{pages.push(await getHtml(link));}catch{/* one product page may be unavailable */}
      if(pages.length>=MAX_PAGES)break;
    }

    const dedup=new Map();
    for(let i=0;i<pages.length;i+=1){
      for(const item of candidatesFromPage(pages[i].url,pages[i].html,{rootPage:i===0})){
        const key=item.image_url.split('?')[0].toLowerCase();
        const existing=dedup.get(key);
        if(!existing||(/^product image$/i.test(existing.name)&&!/^product image$/i.test(item.name)))dedup.set(key,item);
      }
    }
    const products=[...dedup.values()].slice(0,24);
    if(!products.length)return response.status(422).json({detail:`${root.hostname} responded, but no usable public product data or product images were exposed. You can still upload a product image manually below.`,code:'PUBLIC_DATA_UNAVAILABLE'});
    return response.status(200).json({
      mode:'live',
      scan_method:'visual-candidate',
      website_url:start.url,
      merchant:root.hostname.replace(/^www\./,''),
      found:products.length,
      products,
      notice:'Ashes could not find a structured catalog, so it imported public visual product candidates. Review the detected images before generating 3D.',
    });
  }catch(error){
    return response.status(400).json({detail:`${error.message||'This website could not be scanned.'} You can still upload a product image manually below.`,code:'WEBSITE_SCAN_FAILED'});
  }
}
