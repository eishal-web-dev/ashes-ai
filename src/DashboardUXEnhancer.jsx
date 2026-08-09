import { useEffect } from 'react';

function escapeHtml(value=''){return String(value).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

function mountQrStudio(){
  const shell=document.querySelector('.business-shell');
  const panel=shell?.querySelector('.table-qr-panel');
  if(!panel||panel.dataset.studio==='true')return;
  panel.dataset.studio='true';
  panel.classList.add('qr-studio');
  panel.id='qr-studio';
  const business=(()=>{try{return JSON.parse(localStorage.getItem('ashes_business')||'{}')}catch{return {}}})();
  const cards=[...panel.querySelectorAll('.table-qr-card')];
  const intro=document.createElement('div');
  intro.className='qr-studio-hero';
  intro.innerHTML=`<div class="qr-studio-copy"><span>SMART QR STUDIO</span><h2>Every scan is an entry point.</h2><p>Create branded table and product experiences, preview exactly where customers land, and keep every QR organized from one place.</p><div class="qr-studio-stats"><div><b>${cards.length}</b><small>LIVE QRs</small></div><div><b>${business.kind==='restaurant'||business.kind==='cafe'?'TABLE':'STORE'}</b><small>PRIMARY MODE</small></div><div><b>3D + AR</b><small>EXPERIENCE</small></div></div></div><div class="qr-phone-preview"><div class="qr-phone-notch"></div><div class="qr-phone-brand">${escapeHtml(business.name||'Your business')}</div><div class="qr-phone-orb">QR</div><strong>Scan. Explore. Order.</strong><span>Mobile storefront preview</span><div class="qr-phone-button">Open experience</div></div>`;
  panel.prepend(intro);

  const builder=panel.querySelector('.table-qr-builder');
  if(builder){
    const title=document.createElement('div'); title.className='qr-builder-title';
    title.innerHTML='<span>CREATE ENTRY POINT</span><strong>New smart QR</strong><small>Choose a location/table code and optionally make the scan open a specific product first.</small>';
    builder.prepend(title);
  }

  cards.forEach(card=>{
    const img=card.querySelector('img'); const strong=card.querySelector('strong'); const urlSpan=card.querySelector('span');
    const url=urlSpan?.textContent?.trim()||'';
    card.classList.add('qr-studio-card');
    if(!card.querySelector('.qr-type-pill')){const pill=document.createElement('i');pill.className='qr-type-pill';pill.textContent='LIVE';card.prepend(pill)}
    if(url){
      urlSpan.classList.add('qr-url');
      const actions=document.createElement('div'); actions.className='qr-card-actions';
      const copy=document.createElement('button');copy.type='button';copy.className='qr-mini-action';copy.textContent='Copy link';copy.onclick=async()=>{try{await navigator.clipboard.writeText(url);copy.textContent='Copied ✓';setTimeout(()=>copy.textContent='Copy link',1400)}catch{}};
      const open=document.createElement('button');open.type='button';open.className='qr-mini-action';open.textContent='Preview';open.onclick=()=>window.open(url,'_blank','noopener,noreferrer');
      actions.append(copy,open); card.querySelector('div')?.append(actions);
    }
    if(img)img.loading='lazy'; if(strong)strong.title='Customer scan destination';
  });
}

function wireDashboardNav(){
  const shell=document.querySelector('.business-shell'); if(!shell||shell.dataset.navwired==='true')return;
  const nav=[...shell.querySelectorAll('.side-nav button')]; if(nav.length<5)return;
  shell.dataset.navwired='true';
  const targets=[['Overview','.dashboard-header'],['Products','.catalog-panel'],['Orders','.orders-panel'],['QR Codes','.table-qr-panel'],['Analytics','.analytics-panel']];
  targets.forEach(([label,selector],i)=>{
    const button=nav[i]; if(!button)return;
    button.onclick=()=>{const target=shell.querySelector(selector);if(target){nav.forEach(x=>x.classList.remove('active'));button.classList.add('active');target.scrollIntoView({behavior:'smooth',block:'start'});history.replaceState({},'',`#${label.toLowerCase().replace(/\s+/g,'-')}`)}};
  });
  nav[5]&&(nav[5].onclick=()=>{nav.forEach(x=>x.classList.remove('active'));nav[5].classList.add('active');shell.querySelector('#business-settings')?.scrollIntoView({behavior:'smooth',block:'start'})});
}

function addSectionAnchors(){
  const shell=document.querySelector('.business-shell');if(!shell)return;
  const map={'.catalog-panel':'products-section','.orders-panel':'orders-section','.analytics-panel':'analytics-section'};
  Object.entries(map).forEach(([sel,id])=>{const el=shell.querySelector(sel);if(el&&!el.id)el.id=id});
}

export default function DashboardUXEnhancer(){
  useEffect(()=>{const sync=()=>{addSectionAnchors();mountQrStudio();wireDashboardNav()};sync();const observer=new MutationObserver(sync);observer.observe(document.body,{childList:true,subtree:true});return()=>observer.disconnect()},[]);
  return null;
}
