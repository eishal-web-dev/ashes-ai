import test from 'node:test';
import assert from 'node:assert/strict';
import { productsFromMenuCards } from '../api/prototype/menu-cards.js';

test('extracts Bubble Brews-style server-rendered menu cards',()=>{
  const html=`
    <div class="card-lift bg-white rounded-2xl">
      <img alt="Strawberry Milk Bubble Tea" src="/_next/image?url=%2FfoodItems%2Fproducts%2F1001.png&amp;w=3840&amp;q=75" />
      <h3>Strawberry Milk Bubble Tea</h3>
      <p>Sweet strawberry milk tea served with chewy tapioca pearls.</p>
      <div>Rs. <!-- -->650</div>
      <button>Add to Cart</button>
    </div>
    <div class="card-lift bg-white rounded-2xl">
      <img alt="Stick Waffle" src="/foodItems/products/2001.png" />
      <h3>Stick Waffle</h3>
      <p>Freshly baked waffle with premium chocolate.</p>
      <div>Rs. 380</div>
    </div>`;

  const products=productsFromMenuCards('https://www.bubblebrews.pk/',html);
  assert.equal(products.length,2);
  assert.deepEqual(products[0],{
    name:'Strawberry Milk Bubble Tea',
    description:'Sweet strawberry milk tea served with chewy tapioca pearls.',
    image_url:'https://www.bubblebrews.pk/foodItems/products/1001.png',
    price:650,
    currency:'PKR',
    source_url:'https://www.bubblebrews.pk/',
    external_product_id:null,
    model_url:null,
    readiness:'image-ready'
  });
  assert.equal(products[1].name,'Stick Waffle');
  assert.equal(products[1].price,380);
});

test('ignores generic cards without a recognisable menu price',()=>{
  const html='<div class="product-card"><h3>Read our story</h3><p>No menu price here.</p></div>';
  assert.deepEqual(productsFromMenuCards('https://example.com',html),[]);
});
