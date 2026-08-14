# ASHES — Canonical Product Source of Truth

> **Status:** Active product direction as of August 2026.
>
> This document is the canonical source of truth for Ashes. If an older README, prototype, chat, or legacy module conflicts with this file, follow this file unless a later dated decision in `docs/decision-log.md` explicitly replaces it.

## 1. One-sentence definition

**Ashes is an AI-powered product digital-twin and visual-commerce platform that turns existing ecommerce product imagery into reusable 3D/AR/try-on assets, stores each asset once, and distributes the same product twin across connected commerce channels such as Shopify, Amazon, and future platforms.**

## 2. Company/product structure

The intended umbrella company name is **Ashes Stack Ltd**. Ashes Commerce is the first major commercial product line.

Possible future product families may include:

- Ashes Commerce — merchant-facing visual commerce platform
- Ashes 3D Engine — product reconstruction and optimization infrastructure
- Ashes API — developer/enterprise access
- Ashes Spatial — AR/spatial-commerce experiences

These future names are directional only. The immediate priority is making **Ashes Commerce** work.

## 3. What changed from the original concept

Ashes originally focused heavily on restaurant/cafe menus, QR codes, food products, nutrition, direct ordering, and a standalone Ashes PWA.

Those modules may remain useful as prototypes or future vertical features, but they are **not the current primary commercial strategy**.

The current primary strategy is global ecommerce infrastructure:

1. connect a merchant's existing store/catalog,
2. identify products,
3. create or reuse a canonical Ashes product twin,
4. generate a commerce-ready 3D model only when needed,
5. store it permanently,
6. publish/reuse it across channels,
7. add AR, virtual try-on, recommendations and analytics over time.

The model generator is therefore an **engine underneath Ashes**, not the entire company.

## 4. Core product principle

### Generate once. Store permanently. Reuse everywhere.

The GPU is used to create a product asset. It is **not** part of the shopper viewing path.

```text
Merchant catalog/product image
          |
          v
Does Ashes already have a valid Product Twin?
       /      \
     yes       no
      |         |
      |     Generation job
      |         |
      |         v
      |   Disposable GPU worker
      |         |
      |         v
      |   Commerce-ready GLB
      |         |
      +-----> Object storage + CDN
                    |
                    v
        Shopify / Amazon / Web / AR
```

A product can receive one view or one million views without rerunning the generation model.

## 5. Merchant identity and channel connections

A merchant should have **one Ashes account** and connect multiple selling channels to that account.

Example:

```text
Ashes Merchant M-8271
├── Shopify store: modernliving.myshopify.com
├── Amazon seller account
└── future WooCommerce/custom store
```

Ashes may show an internal merchant/linking code for convenience, but official platform authorization must still use the platform's supported OAuth/API authorization flow.

The merchant should not pay separate Ashes subscriptions merely because the same business sells on more than one connected channel unless future pricing explicitly says so.

## 6. Product Twin / Asset Registry

The most important long-term data model is the **canonical product twin**.

One physical product may exist on several channels:

```text
Ashes Product Twin PT-427
├── canonical merchant_id
├── canonical SKU / merchant product identity
├── Shopify product / variant IDs
├── Amazon ASIN / seller SKU
├── future channel IDs
├── source product images
├── dimensions / variants / colors where available
├── canonical 3D asset
├── AR metadata
├── try-on metadata where applicable
└── analytics references
```

Before starting any GPU job, Ashes should check whether a compatible asset already exists.

### Product matching strategy

Initial matching can use:

- same merchant
- SKU / seller SKU
- GTIN/UPC/EAN where available
- title and variant data
- image similarity
- manual merchant confirmation

Never regenerate merely because the product was discovered through another channel.

## 7. Current MVP

The immediate MVP is deliberately narrower than the long-term vision.

A real merchant should be able to:

1. authenticate to Ashes,
2. connect or import products,
3. select a product,
4. request 3D generation,
5. have Ashes queue the job asynchronously,
6. send the product image to disposable GPU compute,
7. receive a generated GLB,
8. persist the GLB to S3/R2-compatible object storage,
9. keep that model available after the GPU shuts down,
10. display the model in a lightweight product viewer.

### First commercial integration

**Shopify is Connector #1.**

The first major validation milestone is:

> One real Shopify merchant installs/connects Ashes, selects one real product, Ashes generates and stores a real 3D model, and a real shopper can interact with that model on the live product page.

Amazon, WooCommerce and other channels come after this end-to-end Shopify path is proven.

## 8. Shopify direction

Planned merchant flow:

```text
Install Ashes
   |
Authorize Shopify
   |
Ashes imports catalog
   |
Products detected
   |
Merchant selects products / Ashes recommends candidates
   |
Generate or reuse Product Twin
   |
Publish lightweight "View in 3D" experience
   |
Track interaction and commerce outcomes
```

The shopper stays on the merchant's Shopify store and uses normal Shopify checkout.

Ashes should not become a replacement checkout just to collect its fee.

## 9. Amazon direction

The same canonical product twin should be reusable for a merchant's Amazon listing when the platform accepts the asset and the seller is eligible.

V1 may require an Amazon-ready export/manual submission if automated 3D upload is not available through approved APIs.

The key product value is still:

> generate once in Ashes, reuse the same valid product asset across channels.

## 10. 3D engine architecture

Ashes must remain provider-agnostic.

```text
Ashes Generation Service
├── TRELLIS provider
├── future TRELLIS version/provider
├── future Ashes proprietary model
└── optional fallback provider
```

The commerce application should request `generate(product)` rather than depending directly on a specific model repository.

### Current testing engine

TRELLIS is the current primary reconstruction path under active testing.

The repo contains an Ashes TRELLIS worker and a remote worker adapter. Free/temporary GPU infrastructure is acceptable during validation.

### TRELLIS preservation

Ashes should preserve a known-working version of critical open-source dependencies, including:

- source version / commit reference
- licence and attribution
- dependency versions
- CUDA/PyTorch environment
- Docker/reproducibility information
- approved model weight locations/checksums

Large model weights should not be blindly committed to normal Git history.

## 11. Storage architecture

Permanent assets belong in object storage, not on the GPU worker.

Current storage abstraction supports local development and S3-compatible storage.

Expected logical layout:

```text
products/{merchant_id}/{product_id}/source.webp
models/{merchant_id}/{product_id}.glb
thumbnails/{merchant_id}/{product_id}.webp
```

A CDN should eventually sit in front of permanent assets for international storefront delivery.

## 12. 3D optimization requirements

Raw research output is not automatically commerce-ready.

Ashes should progressively add:

- geometry cleanup
- mesh simplification
- texture compression
- GLB validation
- mobile performance checks
- lazy loading
- fallback poster image
- Draco/Meshopt or equivalent compression where useful
- appropriate image formats for textures

The storefront must not become slower merely because Ashes is installed.

## 13. Future visual-commerce modules

These are strategic product modules, **not MVP requirements**.

### A. AR placement

Best initial vertical: furniture/home decor.

A shopper can open the phone camera and place an existing product twin in the room. The sofa/table/chair model should not be regenerated for each shopper.

### B. Virtual try-on / AI fitting room

Best initial vertical: clothing/fashion/accessories.

A shopper may upload a photo or use a camera-supported experience to preview clothing or accessories. Personalized try-on can require fresh inference for each shopper, unlike normal 3D viewing.

### C. AI cross-sell / complete-the-look

Example:

```text
Try dress
  -> suggest shoes from merchant catalog
  -> suggest bag
  -> preview complete look
  -> add selected items to cart
```

The recommendation should use the merchant's real sellable catalog, not imaginary products.

### D. Room-set recommendations

Example:

```text
Place sofa
  -> suggest matching table
  -> suggest lamp
  -> place multiple real catalog products
  -> add set to cart
```

### E. Commerce intelligence

Over time Ashes should measure and learn from:

- 3D opens
- interaction duration
- AR opens
- try-on usage
- add-to-cart events
- checkout progression
- completed purchases
- product combinations

The long-term goal is to help the merchant understand **which visual experiences actually improve commerce outcomes**.

## 14. Business model — current working hypothesis

Pricing is **not permanently locked** until GPU cost and merchant retention are measured.

Current working plan:

| Plan | Working price | New generation allowance | Suggested active 3D products |
|---|---:|---:|---:|
| Trial | $0 for 30 days | 3 total | 3 |
| Starter | $19.99/mo | ~5/mo | ~15 |
| Standard | $45.99/mo | ~20/mo | ~50 |
| Pro | $149.99/mo | ~75/mo | ~250 |
| Enterprise | Custom | Custom | 1,000+ / custom |

### Why generation limits exist during validation

A merchant with thousands of products must not be able to consume unlimited GPU compute for free.

Credits/allowances are primarily a cost-control mechanism during the early stage. Later, Ashes may hide this complexity behind catalog-size plans, automatic generation budgets, or enterprise contracts.

### Extra generation

Potential add-on generation packs may be offered. Exact pricing must be based on measured **cost per successful commerce-ready GLB**, not guessed hourly GPU pricing.

### Personalized try-on monetization hypothesis

Personalized try-on creates new inference cost per user/session. Possible future models include:

- merchant-sponsored free try-on
- first try-on free, additional try-ons paid
- optional customer-paid fitting-room session (for example around $0.99/$1 as an experiment)
- usage bundled into higher merchant plans

Do not hard-code this consumer fee before conversion testing; charging a shopper can create checkout friction.

## 15. Metrics that matter

### Technical

- successful generation rate
- GPU minutes per successful model
- retries/failures
- output GLB size
- mobile load time
- storage/bandwidth use
- cost per successful commerce-ready GLB

### Product

- merchant install-to-first-model rate
- percentage of generated products actually published
- shopper 3D interaction rate
- AR/try-on usage
- merchant renewal/retention

### Business

- paying merchants
- MRR / ARR
- average revenue per merchant
- gross margin
- churn
- international customer count by country

## 16. Validation sequence

Do not skip these gates.

```text
0 -> 1 real end-to-end generated product
1 -> 1 real Shopify merchant
1 -> 10 merchants
10 -> first paid renewals
$0 -> $1k MRR
$1k -> $10k MRR
then broader channel expansion
```

Marketplace listing alone is not customer acquisition. Early sales should include founder-led outreach and direct merchant demos.

## 17. Long-term platform direction

If the initial product proves demand, Ashes can evolve from:

```text
Image-to-3D tool
      ↓
Shopify 3D app
      ↓
Multi-channel Product Twin platform
      ↓
3D + AR + Try-On visual-commerce layer
      ↓
Commerce intelligence / optimization platform
```

The long-term ambition is:

> **A physical product enters Ashes once and its digital twin powers every supported shopping experience and selling channel.**

## 18. What NOT to prioritize now

Do not delay validation for:

- excessive marketing-site animations
- every marketplace integration at once
- a proprietary foundation model trained from scratch
- enterprise-only complexity
- full virtual try-on before basic 3D commerce works
- automatic generation of an entire unbounded catalog
- rebuilding checkout
- unrelated AI features

## 19. Current implementation state

The repository already includes substantial legacy and current infrastructure:

- React/Vite frontend
- FastAPI backend
- MongoDB-backed business/product flows
- commerce source work
- billing/subscription modules
- local + S3-compatible storage abstraction
- product generation background job path
- TRELLIS worker tooling
- remote disposable-worker integration in progress
- GLB viewer/prototype assets

Some existing code and pricing settings were built for earlier Ashes versions and may not yet reflect this master product direction. Refactors should migrate toward this document rather than treating every legacy module as a current requirement.

## 20. Immediate next engineering milestone

Complete and validate this exact path:

```text
Real product image
   -> Ashes API
   -> asynchronous generation job
   -> disposable/free GPU worker during testing
   -> TRELLIS real GLB output
   -> permanent S3/R2 object
   -> permanent model URL
   -> lightweight viewer
   -> GPU can disappear and model still works
```

After this passes reliably, build the Shopify installation/catalog/publishing path around it.

## 21. Rule for future contributors and chats

Before making a major feature, architecture, pricing, or positioning change:

1. read this document,
2. read `docs/decision-log.md`,
3. decide whether the change supports the current milestone,
4. update documentation when the decision changes,
5. keep experimental ideas clearly labelled as experiments rather than implemented facts.
