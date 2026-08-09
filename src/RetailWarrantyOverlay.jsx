import { useEffect, useState } from 'react';
import { BadgeCheck, Headphones, PackageSearch, ShieldCheck } from 'lucide-react';
import { getPublicRetailMetadata } from './retail-api';

export default function RetailWarrantyOverlay({ productId }) {
  const [meta, setMeta] = useState(null);

  useEffect(() => {
    if (!productId) return;
    let cancelled = false;
    getPublicRetailMetadata(productId).then(data => { if (!cancelled) setMeta(data?.is_retail ? data : null); }).catch(() => { if (!cancelled) setMeta(null); });
    return () => { cancelled = true; };
  }, [productId]);

  if (!meta) return null;

  return <aside className="retail-warranty-card">
    <div className="retail-warranty-head"><div><span>PRODUCT AUTHENTICITY</span><h3><ShieldCheck size={19}/> Warranty & product info</h3></div><BadgeCheck size={22}/></div>
    <div className="retail-warranty-grid">
      <div><PackageSearch size={16}/><span>Category</span><strong>{meta.category || 'Retail product'}</strong></div>
      <div><PackageSearch size={16}/><span>Model / SKU</span><strong>{meta.model_number || 'Not specified'}</strong></div>
      <div><ShieldCheck size={16}/><span>Warranty</span><strong>{meta.warranty_period || 'Seller warranty'}</strong></div>
      <div><Headphones size={16}/><span>Claims & support</span><strong>{meta.support_contact || 'Contact seller'}</strong></div>
    </div>
    {meta.warranty_details && <p className="retail-warranty-terms">{meta.warranty_details}</p>}
    <small>Warranty information is provided by the selling business and is attached to this Ashes product QR.</small>
  </aside>;
}
