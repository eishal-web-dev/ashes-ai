from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.mongo_main import app, auth_user, owned_business
from apps.api.mongo_db import collection, clean_doc


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckoutItem(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=99)


class CheckoutPayload(BaseModel):
    items: list[CheckoutItem]
    table_code: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    fulfillment_type: Literal['dine_in', 'takeaway', 'delivery'] = 'takeaway'
    payment_method: Literal['cash', 'pay_on_delivery', 'manual'] = 'cash'
    notes: Optional[str] = None


class OperationsSettingsPayload(BaseModel):
    service_fee: float = Field(default=0, ge=0)
    delivery_fee: float = Field(default=0, ge=0)
    allow_dine_in: bool = True
    allow_takeaway: bool = True
    allow_delivery: bool = True
    currency: str = 'PKR'


class OrderOperationsPatch(BaseModel):
    payment_status: Optional[Literal['unpaid', 'pending', 'paid', 'refunded']] = None
    payment_method: Optional[str] = None
    fulfillment_type: Optional[Literal['dine_in', 'takeaway', 'delivery']] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    merchant_note: Optional[str] = None


def business_by_slug(slug: str) -> dict:
    business = clean_doc(collection('businesses').find_one({'slug': slug}))
    if not business:
        raise HTTPException(404, 'Business not found')
    return business


def settings_for(business: dict) -> dict:
    return {
        'service_fee': float(business.get('service_fee') or 0),
        'delivery_fee': float(business.get('delivery_fee') or 0),
        'allow_dine_in': bool(business.get('allow_dine_in', True)),
        'allow_takeaway': bool(business.get('allow_takeaway', True)),
        'allow_delivery': bool(business.get('allow_delivery', True)),
        'currency': business.get('currency') or 'PKR',
    }


@app.get('/api/businesses/{business_slug}/operations-settings')
def public_operations_settings(business_slug: str):
    return settings_for(business_by_slug(business_slug))


@app.patch('/api/businesses/{business_slug}/operations-settings')
def update_operations_settings(business_slug: str, payload: OperationsSettingsPayload, user: dict = Depends(auth_user)):
    business = owned_business(user['id'], business_slug)
    updates = payload.model_dump()
    collection('businesses').update_one({'id': business['id']}, {'$set': updates})
    return settings_for({**business, **updates})


@app.post('/api/orders/checkout')
def checkout(payload: CheckoutPayload):
    if not payload.items:
        raise HTTPException(400, 'Order needs at least one item')

    first = clean_doc(collection('products').find_one({'id': payload.items[0].product_id, 'is_published': True}))
    if not first:
        raise HTTPException(400, 'Product unavailable')
    business = clean_doc(collection('businesses').find_one({'id': first['business_id']}))
    if not business:
        raise HTTPException(400, 'Business unavailable')
    settings = settings_for(business)

    enabled = {
        'dine_in': settings['allow_dine_in'],
        'takeaway': settings['allow_takeaway'],
        'delivery': settings['allow_delivery'],
    }
    if not enabled.get(payload.fulfillment_type, False):
        raise HTTPException(400, f"{payload.fulfillment_type.replace('_', ' ').title()} is not available")
    if payload.fulfillment_type == 'delivery' and not (payload.delivery_address or '').strip():
        raise HTTPException(400, 'Delivery address is required')

    normalized = []
    subtotal = 0.0
    for item in payload.items:
        product = clean_doc(collection('products').find_one({'id': item.product_id, 'is_published': True}))
        if not product or product.get('business_id') != business['id']:
            raise HTTPException(400, 'Invalid or unavailable product in order')
        unit = float(product.get('price') or 0)
        line = unit * item.quantity
        subtotal += line
        normalized.append({
            'product_id': product['id'], 'product_name': product['name'], 'unit_price': unit,
            'quantity': item.quantity, 'line_total': line,
        })

    service_fee = settings['service_fee']
    delivery_fee = settings['delivery_fee'] if payload.fulfillment_type == 'delivery' else 0.0
    total = subtotal + service_fee + delivery_fee
    stamp = now_iso()
    order = {
        'id': str(uuid.uuid4()), 'business_id': business['id'], 'business_slug': business['slug'],
        'table_code': payload.table_code if payload.fulfillment_type == 'dine_in' else None,
        'customer_name': (payload.customer_name or '').strip() or None,
        'customer_phone': (payload.customer_phone or '').strip() or None,
        'delivery_address': (payload.delivery_address or '').strip() or None,
        'fulfillment_type': payload.fulfillment_type,
        'payment_method': payload.payment_method,
        'payment_status': 'unpaid' if payload.payment_method in {'cash', 'pay_on_delivery'} else 'pending',
        'notes': (payload.notes or '').strip() or None,
        'merchant_note': None,
        'status': 'new', 'subtotal': subtotal, 'service_fee': service_fee, 'delivery_fee': delivery_fee,
        'total': total, 'currency': settings['currency'], 'items': normalized,
        'history': [{'status': 'new', 'created_at': stamp}], 'notified_business': False,
        'created_at': stamp, 'updated_at': stamp,
    }
    collection('orders').insert_one(order)
    return clean_doc(order)


@app.patch('/api/businesses/{business_slug}/orders/{order_id}/operations')
def patch_order_operations(business_slug: str, order_id: str, payload: OrderOperationsPatch, user: dict = Depends(auth_user)):
    business = owned_business(user['id'], business_slug)
    order = clean_doc(collection('orders').find_one({'id': order_id, 'business_id': business['id']}))
    if not order:
        raise HTTPException(404, 'Order not found')
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if updates:
        updates['updated_at'] = now_iso()
        collection('orders').update_one({'id': order_id, 'business_id': business['id']}, {'$set': updates})
    return clean_doc(collection('orders').find_one({'id': order_id, 'business_id': business['id']}))
