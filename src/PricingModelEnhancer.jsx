import { useEffect } from 'react';

function mountPublicPricing(){
  const shell=document.querySelector('.site-shell');
  const footer=shell?.querySelector('.footer');
  if(!shell||!footer||shell.querySelector('#pricing'))return;
  const section=document.createElement('section');
  section.id='pricing'; section.className='public-pricing-section container';
  section.innerHTML=`<div class="public-pricing-copy"><span>ONE SIMPLE MEMBERSHIP</span><h2>Try all of Ashes free for 30 days.</h2><p>No per-product pricing. No Starter-versus-Pro confusion. Connect your existing website or run the full store on Ashes, then keep the platform for one monthly membership.</p><div class="public-price-trust"><i>✓ 3D + AR</i><i>✓ Smart QR</i><i>✓ Commerce integration</i><i>✓ Orders & analytics</i></div></div><div class="public-price-card"><span>ASHES MONTHLY</span><strong><b>Rs 1,400</b><small>/month</small></strong><em>or $5/month internationally</em><div class="public-trial-pill">FIRST 30 DAYS FREE</div><button type="button" class="primary-btn public-pricing-cta">Start free</button><small>Website design/build work is quoted separately when a business needs a complete new site.</small></div>`;
  section.querySelector('.public-pricing-cta')?.addEventListener('click',()=>document.querySelector('.nav .ghost-btn')?.click());
  shell.insertBefore(section,footer);
  const nav=shell.querySelector('.nav-links');
  if(nav&&!nav.querySelector('a[href="#pricing"]')){const a=document.createElement('a');a.href='#pricing';a.textContent='Pricing';nav.appendChild(a)}
}

function fixAdminPricing(){
  const admin=document.querySelector('.admin-shell'); if(!admin)return;
  const mini=admin.querySelector('.admin-plan-mini');
  if(mini&&!mini.dataset.singlePlan){mini.dataset.singlePlan='true';const spans=[...mini.querySelectorAll('span')];if(spans[0])spans[0].childNodes[0].textContent='Trial ';if(spans[1])spans[1].childNodes[0].textContent='Ashes ';if(spans[2])spans[2].style.display='none'}
  [...admin.querySelectorAll('.admin-billing-settings label')].forEach(label=>{
    const text=label.textContent||'';
    if(text.includes('Starter monthly price')) label.querySelector('span')&&(label.querySelector('span').textContent='Ashes monthly price');
    if(text.includes('Starter enabled')) label.querySelector('span')&&(label.querySelector('span').textContent='Ashes membership enabled');
    if(text.includes('Pro monthly price')||text.includes('Pro enabled')) label.style.display='none';
  });
  const heading=[...admin.querySelectorAll('h2')].find(x=>x.textContent?.includes('Billing & subscription pricing'));
  if(heading)heading.textContent='Membership & payment settings';
}

export default function PricingModelEnhancer(){
  useEffect(()=>{const sync=()=>{mountPublicPricing();fixAdminPricing()};sync();const observer=new MutationObserver(sync);observer.observe(document.body,{childList:true,subtree:true});return()=>observer.disconnect()},[]);return null;
}
