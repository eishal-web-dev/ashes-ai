function decodeText(value){
  return String(value||'').replace(/<[^>]*>/g,' ').replace(/&nbsp;|&#160;/gi,' ').replace(/&amp;/gi,'&').replace(/&quot;/gi,'"').replace(/&#0*39;|&apos;/gi,"'").replace(/\s+/g,' ').trim();
}

function money(value){
  const match=String(value??'').match(/-?\d[\d,]*(?:\.\d+)?/);
  return match?Number(match[0].replaceAll(',','')):null;
}

function imageFromCard(pageUrl,html){
  const tag=html.match(/<img\b[^>]*>/i)?.[0];
  if(!tag)return null;
  const raw=(tag.match(/\bsrc=["']([^"']+)["']/i)?.[1]||'').replaceAll('&amp;','&');
  if(!raw)return null;
  try{
    const resolved=new URL(raw,pageUrl);
    // Prefer the original asset behind a Next.js optimization URL.
    if(resolved.pathname==='/_next/image'&&resolved.searchParams.get('url')){
      return new URL(resolved.searchParams.get('url'),pageUrl).toString();
    }
    return resolved.toString();
  }catch{return null;}
}

export function productsFromMenuCards(pageUrl,html){
  const starts=[];
  const cardPattern=/<(?:article|li|div)\b[^>]*class=["'][^"']*(?:card-lift|product-card|product-item|menu-card|menu-item|food-card|food-item|item-card)[^"']*["'][^>]*>/gi;
  for(const match of html.matchAll(cardPattern))starts.push(match.index);
  const found=[];
  const seen=new Set();
  for(let index=0;index<starts.length;index+=1){
    const card=html.slice(starts[index],starts[index+1]??html.length);
    const heading=card.match(/<h[2-4]\b[^>]*>([\s\S]*?)<\/h[2-4]>/i);
    const text=decodeText(card);
    const priceText=text.match(/(Rs\.?|PKR|£|GBP|\$|USD|€|EUR|AED|SAR)\s*([0-9][0-9,]*(?:\.\d+)?)/i)
      ||text.match(/([0-9][0-9,]*(?:\.\d+)?)\s*(PKR|GBP|USD|EUR|AED|SAR)\b/i);
    const name=decodeText(heading?.[1]);
    if(!name||name.length<3||name.length>180||!priceText)continue;
    const key=name.toLowerCase();
    if(seen.has(key))continue;
    seen.add(key);
    const paragraph=card.match(/<p\b[^>]*>([\s\S]*?)<\/p>/i);
    const imageUrl=imageFromCard(pageUrl,card);
    const token=(/\d/.test(priceText[1])?priceText[2]:priceText[1]).toUpperCase();
    const currency=token.startsWith('RS')||token==='PKR'?'PKR':token==='£'||token==='GBP'?'GBP':token==='$'||token==='USD'?'USD':token==='€'||token==='EUR'?'EUR':token;
    const priceValue=/\d/.test(priceText[1])?priceText[1]:priceText[2];
    found.push({name,description:decodeText(paragraph?.[1]).slice(0,320)||null,image_url:imageUrl,price:money(priceValue),currency,source_url:pageUrl,external_product_id:null,model_url:null,readiness:imageUrl?'image-ready':'needs-image'});
  }
  return found.slice(0,16);
}
