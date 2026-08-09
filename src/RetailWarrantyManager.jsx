import { useEffect, useMemo, useState } from 'react';
import { BadgeCheck, PackageSearch, Save, ShieldCheck, X } from 'lucide-react';
import { getBusinessProducts } from './api';
import { getOwnerRetailMetadata, saveOwnerRetailMetadata } from './retail-api';

const CATEGORIES = ['Solar equipment','Electronics','Mobile accessories','UPS and batteries','Water filters','Furniture','Mattresses','Home appliances','LED lights','Retail'];

export default function RetailWarrantyManager({ business }) {
  const [open, setOpen] = useState(false);
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState('');
  const [form, setForm] = useState({ product_type:'retail', category:'Electronics', model_number:'', warranty_period:'', warranty_details:'', support_contact:'' });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const slug = business?.slug;
  const retailBusiness = useMemo(() => !['restaurant','cafe'].includes(String(business?.kind || '').toLowerCase()), [business]);

  useEffect(() => {
    if (!open || !slug) return;
    getBusinessProducts(slug, true).then(items => { setProducts(items || []); if (!productId && items?.[0]) setProductId(items[0].id); }).catch(() => {});
  }, [open, slug]);

  useEffect(() => {
    if (!open || !slug || !productId) return;
    getOwnerRetailMetadata(slug, productId).then(meta => setForm({
      product_type: meta.product_type || 'retail', category: meta.category || 'Electronics', model_number: meta.model_number || '',
      warranty_period: meta.warranty_period || '', warranty_details: meta.warranty_details || '', support_contact: meta.support_contact || '',
    })).catch(() => {});
  }, [open, slug, productId]);

  if (!retailBusiness) return null;

  const save = async () => {
    if (!productId) return;
    setSaving(true); setMessage('');
    try { await saveOwnerRetailMetadata(slug, productId, { ...form, product_type:'retail' }); setMessage('Warranty details saved to this product QR.'); }
    catch (err) { setMessage(err.message || 'Could not save warranty details'); }
    finally { setSaving(false); }
  };

  return <>
    <button className="retail-warranty-fab" onClick={() => setOpen(true)}><ShieldCheck size={18}/><span>Product warranties</span></button>
    {open && <div className="retail-manager-backdrop" onClick={() => setOpen(false)}><section className="retail-manager" onClick={e=>e.stopPropagation()}>
      <header><div><span>ASHES RETAIL</span><h2>QR warranty manager</h2><p>Add warranty and model details customers should see after scanning.</p></div><button onClick={() => setOpen(false)}><X size={18}/></button></header>
      <label><span>Product</span><select value={productId} onChange={e=>setProductId(e.target.value)}>{products.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <div className="retail-manager-grid"><label><span>Product category</span><select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{CATEGORIES.map(x=><option key={x}>{x}</option>)}</select></label><label><span>Model / SKU</span><input value={form.model_number} onChange={e=>setForm({...form,model_number:e.target.value})} placeholder="INV-6KW-X2"/></label></div>
      <label><span>Warranty period</span><input value={form.warranty_period} onChange={e=>setForm({...form,warranty_period:e.target.value})} placeholder="2 years / 10 years panel warranty"/></label>
      <label><span>Warranty terms</span><textarea rows="4" value={form.warranty_details} onChange={e=>setForm({...form,warranty_details:e.target.value})} placeholder="Coverage, exclusions, replacement/repair terms..."/></label>
      <label><span>Support / claim contact</span><input value={form.support_contact} onChange={e=>setForm({...form,support_contact:e.target.value})} placeholder="Phone, WhatsApp or support email"/></label>
      {message && <div className="retail-manager-message"><BadgeCheck size={15}/>{message}</div>}
      <button className="retail-save" onClick={save} disabled={saving}><Save size={16}/>{saving ? 'Saving…' : 'Save to QR experience'}</button>
      <div className="retail-help"><PackageSearch size={17}/><span>Works for solar equipment, electronics, mobile accessories, UPS/batteries, water filters, furniture, mattresses, home appliances, LED lights and other retail products.</span></div>
    </section></div>}
  </>;
}
