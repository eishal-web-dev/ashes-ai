import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';
import pdf from 'pdf-parse/lib/pdf-parse.js';

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

async function getPdf(raw){
  const url=await safeUrl(raw);
  const response=await fetch(url,{signal:AbortSignal.timeout(18000),headers:{'user-agent':USER_AGENT,accept:'application/pdf'}});
  if(!response.ok)throw new Error(`Menu PDF returned ${response.status}.`);
  const length=Number(response.headers.get('content-length')||0);
  if(length>15_000_000)throw new Error('Menu PDF is too large to scan safely.');
  const bytes=Buffer.from(await response.arrayBuffer());
  if(bytes.length>15_000_000)throw new Error('Menu PDF is too large to scan safely.');
  return {url:url.toString(),text:(await pdf(bytes)).text};
}

async function getPdfWithRetry(raw){
  try{return await getPdf(raw)}catch(firstError){
    await new Promise(resolve=>setTimeout(resolve,350));
    try{return await getPdf(raw)}catch{throw firstError;}
  }
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

function pdfLinks(pageUrl,html){
  const root=new URL(pageUrl);
  const links=[];
  for(const match of html.matchAll(/<a\b[^>]*href=["']([^"'#]+\.pdf(?:\?[^"']*)?)["']/gi)){
    try{const url=new URL(match[1].replaceAll('&amp;','&'),pageUrl);if(url.hostname===root.hostname)links.push(url.toString());}catch{/* Ignore invalid links. */}
  }
  return [...new Set(links)];
}

function productsFromMenuPdf(pdfUrl,text){
  const cleaned=String(text||'').replace(/\r/g,'\n').replace(/[ \t]+/g,' ');
  const documentCurrency=/£/.test(cleaned)?'GBP':(/\bRs\.?\s*\d/i.test(cleaned)?'PKR':'USD');
  const found=[];
  const seen=new Set();
  const add=(rawName,rawPrice)=>{
    const name=String(rawName||'').replace(/\.{2,}/g,'').replace(/\s+/g,' ').trim();
    if(!name||name.length<3||name.length>80||/rs\s*\.?\s*\d/i.test(name)||/^(all prices|add |serving|full|half|menu|price|seasonal|please ask)/i.test(name))return;
    const key=name.toLowerCase();if(seen.has(key))return;seen.add(key);
    found.push({name:name.slice(0,180),description:'Imported from the restaurant’s published menu PDF.',image_url:null,price:money(rawPrice),currency:documentCurrency,source_url:pdfUrl,external_product_id:null,model_url:null,readiness:'needs-image'});
  };
  // Strongest case: name and Rs price share a line (common in restaurant PDFs).
  const inline=/(?:^|\n)\s*([A-Za-z][A-Za-z0-9 &'()+,./-]{2,70}?)\s*(?:\.{2,}|\s{2,})?\s*Rs\.?\s*([0-9][0-9,]{1,6})\b/gim;
  for(const match of cleaned.matchAll(inline))add(match[1],match[2]);
  // UK and international menus commonly use a dish name followed by a decimal
  // price, with the currency symbol shown once elsewhere in the document.
  const decimal=/(?:^|\n)\s*([A-Za-z][A-Za-z0-9 &'’()+,./-]{2,80}?)\s+(?:£\s*)?([0-9]{1,3}\.\d{2})(?=\s|$)/gim;
  for(const match of cleaned.matchAll(decimal))add(match[1],match[2]);
  // Many designed menus serialize a run of dotted item names followed by a run of prices.
  const lines=cleaned.split(/\n+/).map(line=>line.trim()).filter(Boolean);
  for(let i=0;i<lines.length;){
    const names=[];
    while(i<lines.length&&/^[A-Za-z].*\.{2,}/.test(lines[i])&&!/Rs\s*\.?\s*\d/i.test(lines[i])){names.push(lines[i]);i+=1;}
    if(!names.length){i+=1;continue;}
    const prices=[];
    while(i<lines.length&&prices.length<names.length){
      const price=lines[i].match(/^Rs\s*\.?\s*([0-9][0-9,]{1,6})(?:\s|\(|$)/i);
      if(!price)break;
      prices.push(price[1]);i+=1;
    }
    if(prices.length===names.length)names.forEach((name,index)=>add(name,prices[index]));
  }
  return found.slice(0,16);
}

async function findFoodReference(name){
  try{
    const searchName=name.replace(/\([^)]*\)/g,'').replace(/\b(baranh|special|pcs?|full|half)\b/gi,'').replace(/\s+/g,' ').trim();
    const params=new URLSearchParams({action:'query',format:'json',origin:'*',generator:'search',gsrnamespace:'0',gsrlimit:'5',gsrsearch:`${searchName} food`,prop:'pageimages|info',piprop:'thumbnail',pithumbsize:'900',inprop:'url'});
    const response=await fetch(`https://en.wikipedia.org/w/api.php?${params}`,{signal:AbortSignal.timeout(6500),headers:{'user-agent':USER_AGENT}});
    if(!response.ok)return null;
    const data=await response.json();
    const important=searchName.toLowerCase().split(/\s+/).filter(token=>token.length>3&&!['special','chicken','mutton','food'].includes(token));
    const pages=Object.values(data.query?.pages||{}).filter(page=>page.thumbnail?.source&&!/list of|disambiguation/i.test(page.title||''));
    const page=pages.find(candidate=>important.some(token=>(candidate.title||'').toLowerCase().includes(token)));
    const url=page?.thumbnail?.source;
    if(!url||!/^https:\/\/upload\.wikimedia\.org\//i.test(url))return null;
    return {image_url:url,image_source_url:page.fullurl||null,image_credit:'Wikipedia / Wikimedia Commons reference'};
  }catch{return null;}
}

export default async function handler(request,response){
  response.setHeader('Cache-Control','no-store, max-age=0');
  if(request.method!=='POST')return response.status(405).json({detail:'Method not allowed.'});
  try{
    const start=await getHtml(request.body?.url);
    const source=new URL(start.url);
    const sourceHost=source.hostname.replace(/^www\./,'');
    if(sourceHost==='qr.finedinemenu.com'&&(source.pathname==='/'||source.pathname==='')){
      return response.status(422).json({
        detail:'This is FineDine’s homepage, not a restaurant menu. Paste the complete link from the restaurant QR code, including the restaurant name and menu ID (for example: qr.finedinemenu.com/restaurant-name/menu/abc123).'
      });
    }
    const limit=Math.max(1,Math.min(Number(request.body?.max_pages)||8,16));
    const pages=[start];
    for(const link of productLinks(start.url,start.html).slice(0,limit)){
      try{pages.push(await getHtml(link));}catch{/* Continue when an individual product blocks crawling. */}
    }
    const dedup=new Map();
    for(const page of pages)for(const product of productsFromPage(page.url,page.html)){const key=String(product.external_product_id||product.source_url||product.name).toLowerCase();if(!dedup.has(key))dedup.set(key,product);}
    if(!dedup.size){
      const menus=pdfLinks(start.url,start.html);
      if(new URL(start.url).hostname.replace(/^www\./,'')==='baranh.pk'){
        menus.unshift('https://baranh.pk/pizzaro/images/mainMenuJhung.pdf','https://baranh.pk/pizzaro/images/mainMenu.pdf');
      }
      for(const menuUrl of [...new Set(menus)].slice(0,2)){
        try{const menu=await getPdfWithRetry(menuUrl);for(const product of productsFromMenuPdf(menu.url,menu.text)){const key=product.name.toLowerCase();if(!dedup.has(key))dedup.set(key,product);}}catch{/* Continue to another published menu. */}
      }
    }
    let products=[...dedup.values()].slice(0,16);
    if(products.some(product=>!product.image_url)){
      products=await Promise.all(products.map(async product=>{
        if(product.image_url)return product;
        const reference=await findFoodReference(product.name);
        return reference?{...product,...reference,readiness:product.model_url?'real-3d':'reference-image'}:product;
      }));
    }
    if(!products.length)return response.status(422).json({detail:`${new URL(start.url).hostname} responded, but no product data or readable menu was found. Please retry once or use a direct store, collection, or menu page.`});
    const host=sourceHost;
    return response.status(200).json({mode:'live',website_url:start.url,merchant:host,found:products.length,products,notice:'Read-only preview. Nothing was saved or published.'});
  }catch(error){return response.status(400).json({detail:error.message||'The website could not be scanned.'});}
}
