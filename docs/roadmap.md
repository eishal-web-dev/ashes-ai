# Ashes Commerce Roadmap

> This roadmap follows `docs/ASHES-MASTER-PLAN.md`. Items are ordered by validation value, not by how exciting they sound.

## Phase 0 — Product direction and safety rails

- [x] Define Ashes as a global visual-commerce / Product Twin platform
- [x] Define **generate once, store permanently, reuse everywhere** principle
- [x] Keep 3D engine provider-agnostic
- [x] Preserve S3-compatible storage abstraction
- [x] Keep Shopify as Connector #1
- [x] Treat Amazon/multi-channel as the next layer, not day-one scope
- [x] Record current pricing as a hypothesis rather than hard-coded truth

## Phase 1 — Real image -> permanent 3D asset

Goal: prove one real product can be generated on disposable compute and survive after the GPU disappears.

- [x] Existing background product generation path
- [x] Existing local/S3-compatible storage abstraction
- [x] TRELLIS worker prototype
- [x] Remote worker adapter in Ashes API branch
- [x] Direct image upload contract to worker
- [x] Poll remote generation status
- [x] Download worker GLB into Ashes API
- [x] Persist generated GLB through Ashes storage layer
- [ ] Run end-to-end generation against a live disposable/free GPU
- [ ] Confirm stored GLB remains reachable after worker shutdown
- [ ] Benchmark 10 representative ecommerce products
- [ ] Record GPU time, failures, output size and visual quality
- [ ] Measure cost per successful commerce-ready GLB
- [ ] Add first reliable optimization/validation pass

### Phase 1 exit criterion

> Upload one real product image -> generate a real GLB -> store it permanently -> shut down GPU -> model still loads correctly.

## Phase 2 — Canonical Product Twin / asset registry

Goal: stop unnecessary regeneration and prepare for cross-channel reuse.

- [ ] Define canonical ProductTwin model
- [ ] Add ChannelConnection model
- [ ] Add ChannelProductLink model
- [ ] Add normalized ProductAsset model or compatible incremental migration
- [ ] Match existing products by merchant + SKU where possible
- [ ] Add GTIN/UPC/EAN matching where available
- [ ] Add manual merge/confirm UI for ambiguous matches
- [ ] Ensure generation checks for an existing compatible model before using GPU
- [ ] Track model version/checksum

### Phase 2 exit criterion

> The same merchant product discovered twice reuses one stored Ashes model rather than generating again.

## Phase 3 — Shopify MVP

Goal: one real Shopify merchant can install/connect Ashes and put a generated product model on a live product page.

- [ ] Create Shopify app configuration
- [ ] Implement Shopify OAuth / authorization
- [ ] Store Shopify channel connection securely
- [ ] Import merchant products/variants/images
- [ ] Show detected catalog in Ashes dashboard
- [ ] Let merchant select product(s) for 3D
- [ ] Reuse existing ProductTwin where matched
- [ ] Trigger generation when needed
- [ ] Show queued / generating / optimizing / ready / failed status
- [ ] Create Theme App Extension / supported storefront block
- [ ] Add lightweight `View in 3D` experience
- [ ] Lazy-load model assets
- [ ] Keep normal Shopify cart/checkout flow
- [ ] Add uninstall/data-cleanup behavior
- [ ] Add Shopify-compatible billing path

### Phase 3 exit criterion

> One real Shopify merchant connects Ashes, one product becomes 3D, and a real shopper interacts with it on the live merchant product page.

## Phase 4 — First commercial validation

Goal: prove merchants will keep paying.

- [ ] Recruit first 5-10 merchants manually
- [ ] Prioritize furniture/home decor, footwear, bags/accessories and visual consumer products
- [ ] Offer controlled 30-day trial
- [ ] Trial generation allowance: working hypothesis of 3 total generations
- [ ] Collect merchant onboarding friction
- [ ] Collect viewer interaction analytics
- [ ] Measure free-to-paid conversion
- [ ] Measure month-2 retention
- [ ] Collect testimonials/case studies with permission
- [ ] Improve model quality based on failed examples
- [ ] Improve store performance based on real storefront measurements

### Phase 4 exit criterion

> Multiple merchants renew after the free period because they perceive Ashes as useful enough to pay for.

## Phase 5 — Pricing and unit economics

Goal: ensure every growth step can become profitable.

- [ ] Replace legacy billing constants with current plan model
- [ ] Implement Trial / Starter / Standard / Pro / Enterprise plan structure
- [ ] Track active 3D products separately from new-generation usage
- [ ] Implement monthly generation budgets/allowances
- [ ] Add optional extra-generation packs
- [ ] Limit or cap credit rollover if credits remain user-visible
- [ ] Track storage/bandwidth cost per merchant
- [ ] Track GPU cost per successful generation
- [ ] Calculate gross margin by plan

Working pricing hypothesis:

| Plan | Price | Generation allowance | Suggested active 3D products |
|---|---:|---:|---:|
| Trial | $0 / 30 days | 3 total | 3 |
| Starter | $19.99/mo | ~5/mo | ~15 |
| Standard | $45.99/mo | ~20/mo | ~50 |
| Pro | $149.99/mo | ~75/mo | ~250 |
| Enterprise | Custom | Custom | Custom / 1,000+ |

These values are not final until generation cost and retention are measured.

## Phase 6 — Amazon / second-channel reuse

Goal: prove the same Ashes Product Twin can power more than one commerce channel.

- [ ] Connect Amazon seller account through approved authorization
- [ ] Import/read relevant catalog metadata
- [ ] Match Shopify products to Amazon listings by SKU/identifier
- [ ] Reuse existing GLB instead of generating again
- [ ] Validate Amazon asset requirements
- [ ] Provide Amazon-ready export/submission workflow
- [ ] Automate publishing only where approved APIs allow it

### Phase 6 exit criterion

> A merchant selling the same item on Shopify and Amazon uses one Ashes canonical model for both channels.

## Phase 7 — Furniture AR placement

Goal: make Ashes substantially more valuable for furniture/home-decor merchants.

- [ ] Validate physical scale/dimensions
- [ ] Add mobile AR launch
- [ ] Plane/world placement
- [ ] Move/rotate product in room
- [ ] Add room-scene persistence where useful
- [ ] Suggest complementary real catalog products
- [ ] Allow multi-product room preview later

This should reuse stored product models and should not rerun reconstruction per shopper.

## Phase 8 — Personalized virtual try-on

Goal: create a higher-value fashion experience after core 3D commerce is proven.

- [ ] Select first try-on category carefully
- [ ] Choose/benchmark try-on inference provider/model
- [ ] Define shopper photo consent/privacy policy
- [ ] Define image retention/deletion policy
- [ ] Support photo upload first; camera/live experiences later
- [ ] Map real merchant variants/colors/sizes
- [ ] Measure inference cost per try-on
- [ ] Test merchant-sponsored vs consumer-paid usage
- [ ] Add `Complete the look` recommendations from real merchant inventory
- [ ] Try shoes/bag/accessories with the selected clothing experience where technically appropriate

### Monetization experiment

Possible future options:

- merchant pays all try-on usage
- first try-on free, more looks paid
- optional ~$0.99/$1 customer-paid fitting session
- usage bundled into higher plans

Do not lock the consumer fee before testing conversion friction.

## Phase 9 — Commerce intelligence

Goal: move from visual feature to measurable revenue infrastructure.

- [ ] Track 3D opens/interactions
- [ ] Track AR usage
- [ ] Track try-on usage
- [ ] Track add-to-cart
- [ ] Track checkout progression where platform rules permit
- [ ] Track completed purchases
- [ ] Build conservative influenced-revenue reporting
- [ ] Compare product performance before/after visual experiences where possible
- [ ] Recommend which catalog products should become 3D next
- [ ] Learn useful product combinations for cross-sell

## Phase 10 — Scale and infrastructure ownership

- [ ] Durable queue with retries/dead-letter behavior
- [ ] Multiple GPU workers
- [ ] Serverless/cloud autoscaling
- [ ] CDN for models/textures
- [ ] Dedicated GPU workers when utilization justifies them
- [ ] Compare cloud cost vs owned hardware
- [ ] Hybrid model: owned/dedicated baseline + cloud overflow
- [ ] Enterprise SLA and priority generation

## Long-term direction

```text
Image-to-3D
   -> Shopify 3D commerce
   -> Multi-channel Product Twins
   -> AR + Try-On
   -> AI recommendations
   -> Visual commerce intelligence
   -> Global digital-product infrastructure
```

## Current priority

**Do not skip ahead.** The current engineering target is still Phase 1: a real image must become a permanent real 3D asset through disposable GPU compute.
