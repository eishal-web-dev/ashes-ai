import test from 'node:test';
import assert from 'node:assert/strict';
import { productsFromMenuCards } from '../api/prototype/menu-cards.js';
import { catalogLinks,menuImageLinks } from '../api/prototype/scan.js';

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

test('discovers menu and related order pages from a homepage',()=>{
  const html='<a href="/menu/">Menu</a><a href="https://order.example.com/">Order online</a><a href="/about">About</a>';
  assert.deepEqual(catalogLinks('https://example.com/',html),['https://example.com/menu/','https://order.example.com/']);
});

test('finds Elementor image-only menu pages',()=>{
  const html='<a class="e-gallery-item elementor-gallery-item" href="/uploads/Website-Menu_pages-0001.jpg" data-elementor-lightbox-title="Website Menu page 1"></a>';
  assert.deepEqual(menuImageLinks('https://restaurant.example/menu/',html),['https://restaurant.example/uploads/Website-Menu_pages-0001.jpg']);
});

test('ignores generic cards without a recognisable menu price',()=>{
  const html='<div class="product-card"><h3>Read our story</h3><p>No menu price here.</p></div>';
  assert.deepEqual(productsFromMenuCards('https://example.com',html),[]);
});

test('supports common restaurant card names and international currencies',()=>{
  const html=`
    <article class="menu-card"><img src="/pizza.jpg"><h2>Truffle Pizza</h2><p>Wild mushrooms and truffle.</p><span>£14.50</span></article>
    <li class="food-item"><h3>Kunafa</h3><span>35 AED</span></li>
    <div class="product-item"><h3>Iced Latte</h3><strong>$5.25</strong></div>`;
  const products=productsFromMenuCards('https://restaurant.example/menu',html);
  assert.deepEqual(products.map(({name,price,currency})=>({name,price,currency})),[
    {name:'Truffle Pizza',price:14.5,currency:'GBP'},
    {name:'Kunafa',price:35,currency:'AED'},
    {name:'Iced Latte',price:5.25,currency:'USD'}
  ]);
});
