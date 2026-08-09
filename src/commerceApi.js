import { getToken } from './api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function message(error,status){const d=error?.detail;if(typeof d==='string')return d;if(Array.isArray(d))return d.map(x=>x?.msg||'Invalid value').join(' · ');return d?.message||`Request failed (${status})`}
async function call(path,options={},auth=false){const headers={...(options.headers||{})};if(auth){const token=getToken();if(token)headers.Authorization=`Bearer ${token}`}const r=await fetch(`${API_BASE}${path}`,{...options,headers});if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(message(e,r.status))}return r.json()}

export function getCommerceSource(slug){return call(`/api/businesses/${slug}/commerce-source`,{},true)}
export function getPublicCommerceSource(slug){return call(`/api/public/businesses/${slug}/commerce-source`)}
export function saveCommerceSource(slug,values){return call(`/api/businesses/${slug}/commerce-source`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)},true)}
export function importCommerceWebsite(slug,url,maxPages=12){return call(`/api/businesses/${slug}/commerce-source/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,max_pages:maxPages})},true)}
export function getProductCommerce(productId){return call(`/api/products/${productId}/commerce`)}
export function saveProductCommerce(slug,productId,values){return call(`/api/businesses/${slug}/products/${productId}/commerce`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)},true)}
export function createCommerceHandoff(slug,values){return call(`/api/businesses/${slug}/commerce-handoff`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)})}
