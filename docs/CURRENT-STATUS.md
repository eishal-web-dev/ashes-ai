# Ashes — Current Status: Done / Doing / Next

> **Updated:** 14 August 2026
>
> This file is the fast operational summary of Ashes. Read `docs/ASHES-MASTER-PLAN.md` for the full product vision and `docs/decision-log.md` for the reasoning behind major decisions.
>
> **Important protection rule:** the existing prototype view, prototype UI and prototype runtime code are preserved. Do not redesign, rewrite or remove the prototype merely to align it with the new product direction. New product work should be built around it or beside it unless the founder explicitly requests a prototype change.

---

# 1. What Ashes is now

Ashes is being built as a **global AI visual-commerce / Product Twin platform** for ecommerce merchants.

The central idea is:

> A merchant connects their commerce channels once. Ashes identifies their products, creates or reuses one canonical digital Product Twin for each physical product, generates expensive 3D assets only when needed, stores those assets permanently, and reuses them across Shopify, Amazon and future channels.

The long-term customer experience can include:

- interactive 3D product viewing,
- AR room placement for furniture/home products,
- virtual try-on / AI fitting-room experiences for fashion,
- color/variant experiences,
- `complete the look` product suggestions,
- room-set recommendations,
- visual-commerce analytics and conversion intelligence.

The first commercial connector is **Shopify**. Amazon and other channels follow after the first Shopify path works end-to-end.

---

# 2. DONE — what already exists

## Product / strategy work

- The company/product direction has been changed from a restaurant/QR-first product into a broader ecommerce visual-commerce platform.
- The canonical long-term concept is **Product Twin + multi-channel reuse**.
- The architectural rule is locked: **Generate once. Store permanently. Reuse everywhere.**
- Shopify is defined as Connector #1.
- Amazon is defined as a later connected channel using the same Ashes merchant identity and the same compatible Product Twin whenever possible.
- TRELLIS is treated as a replaceable generation provider, not the entire Ashes product or moat.
- Furniture AR, fashion try-on, product recommendations and commerce intelligence are documented as post-core-MVP modules.
- Working pricing hypotheses have been documented, but pricing remains experimental until real compute cost and merchant retention are measured.

## Existing application / repo capabilities

The repository already contains substantial infrastructure from earlier and current Ashes work:

- React + Vite frontend,
- FastAPI backend,
- MongoDB-backed business and product flows,
- authentication/business account logic,
- commerce-source/catalog work,
- billing/subscription modules,
- local development storage,
- S3-compatible object-storage abstraction,
- GLB/product viewer capability,
- QR/menu/restaurant modules from the earlier product direction,
- website-to-3D prototype/demo,
- TRELLIS notebooks and worker tooling,
- tests around storage/generation and subscriptions.

## Remote disposable-GPU integration

The remote-worker integration has been implemented and merged into the repo.

The Ashes API can now be structured around this flow:

```text
product image
   -> Ashes API
   -> remote/disposable GPU worker
   -> TRELLIS generation task
   -> poll generation status
   -> download GLB
   -> Ashes storage layer
   -> permanent model asset
```

The TRELLIS worker also has a direct image-upload endpoint so the main Ashes API does not have to expose a temporary public image URL just to start a generation.

This is the correct architecture for testing Colab, ZeroGPU-compatible infrastructure, Modal or other future GPU providers without rebuilding the merchant-facing product every time the compute provider changes.

## Permanent-storage foundation

Ashes already has an S3-compatible storage abstraction.

The intended rule is:

```text
GPU creates asset once
        ↓
Ashes saves final GLB in permanent storage
        ↓
GPU may shut down/disappear
        ↓
shopper still loads saved GLB
```

The GPU must never be required merely to view an already-created product.

## Documentation foundation

The repo now has / is adding:

- `docs/ASHES-MASTER-PLAN.md` — canonical product direction,
- `docs/architecture.md` — target technical architecture,
- `docs/roadmap.md` — ordered product roadmap,
- `docs/business-model.md` — commercial/pricing hypotheses,
- `docs/decision-log.md` — dated strategic decisions,
- `docs/CURRENT-STATUS.md` — this operational summary.

---

# 3. PRESERVED — what we are NOT changing right now

The existing prototype is intentionally preserved.

Do **not** change these simply because the company direction evolved:

- prototype view,
- prototype UI/visual layout,
- prototype routes,
- prototype demo behavior,
- existing demo assets,
- old restaurant/QR code paths that the prototype currently relies on.

They may remain useful for demos, historical context or later vertical products.

The new strategy should be implemented in new/current commerce modules and integrations rather than destroying a working prototype.

Also do not currently prioritize:

- a complete prototype redesign,
- full Amazon automation,
- Alibaba integration,
- unlimited automatic generation for every product in a merchant catalog,
- virtual try-on before the base 3D pipeline is reliable,
- training an Ashes foundation model from scratch,
- rebuilding Shopify checkout,
- buying our own GPU cluster before demand exists.

---

# 4. DOING NOW — current active work

## A. Preserve the new direction in documentation

This is the current repo-management task.

We are making sure future chats, developers and contributors can clearly distinguish:

- what exists,
- what is being tested,
- what is planned,
- what is only an experiment/hypothesis,
- what legacy/prototype code must not be mistaken for the current commercial priority.

## B. Validate the real image-to-3D production path

The next technical validation is not another mockup. It is a **real generation**.

Required test:

```text
real ecommerce product photo
      ↓
Ashes API
      ↓
remote/free/disposable GPU
      ↓
TRELLIS real reconstruction
      ↓
real GLB
      ↓
permanent S3/R2-compatible storage
      ↓
permanent URL
      ↓
viewer works after GPU is gone
```

This must be tested on multiple normal ecommerce products, not only one curated demo asset.

Suggested first test categories:

- chair / sofa,
- shoe,
- handbag,
- lamp / decor item,
- packaged product,
- food product for comparison with earlier Ashes work.

## C. Test free/low-cost GPU options

During validation, free/disposable GPU infrastructure is acceptable.

Candidates include:

- Hugging Face ZeroGPU where technically compatible,
- Google Colab for development,
- startup/serverless GPU credits,
- Modal or equivalent when needed.

The goal is not to find a forever-free production GPU. The goal is to prove the workflow cheaply before revenue exists.

## D. Measure unit economics

For each successful generation record:

- GPU type,
- total generation time,
- successful/failed,
- retry count,
- output GLB size,
- visual quality,
- texture quality,
- approximate compute cost,
- final storage size,
- mobile load performance.

Primary metric:

> **Cost per successful commerce-ready GLB.**

This metric should inform final subscription/generation allowances.

---

# 5. NEXT — after the generation/storage gate passes

## Phase 1 — Shopify merchant MVP

Build the first true commercial connector.

Merchant flow:

```text
Install/connect Ashes
        ↓
Shopify authorization
        ↓
Ashes imports merchant catalog
        ↓
merchant sees detected products
        ↓
select product(s)
        ↓
check whether Ashes asset already exists
        ↓
reuse existing Product Twin OR generate once
        ↓
publish lightweight 3D experience on product page
```

Important:

- Do not generate the merchant's entire catalog automatically without a bounded plan/budget.
- Existing product pages and Shopify checkout remain the merchant's normal commerce flow.
- The first storefront feature can be a lightweight `View in 3D` experience.

### First commercial proof

> One real Shopify merchant + one real product + one real stored 3D model + one real shopper able to interact with it on the live product page.

Then:

```text
1 merchant
 -> 5 merchants
 -> 10 merchants
 -> first paid renewals
 -> $1k MRR
 -> $10k MRR
```

---

# 6. NEXT — canonical Product Twin registry

Once the first Shopify path is working, formalize the Product Twin / Asset Registry.

One physical product should have one Ashes identity even if sold through multiple channels.

Example:

```text
Ashes Product Twin PT-427
├── merchant_id
├── canonical SKU / product identity
├── Shopify product + variant IDs
├── Amazon ASIN / seller SKU
├── source images
├── canonical GLB
├── variants/colors/dimensions where known
├── AR metadata
├── try-on metadata later
└── analytics references
```

Before starting a GPU job:

```text
Does compatible Ashes asset already exist?
      |
   yes -> reuse it
      |
    no -> generate
```

This is how Ashes reduces duplicate compute and lets a merchant generate once for Shopify and later reuse the same compatible asset for Amazon or another channel.

---

# 7. NEXT — Amazon connection

After Shopify validation:

- merchant connects Amazon to the **same Ashes account** using supported authorization,
- Ashes imports/reads the seller catalog where approved APIs allow,
- Ashes matches Amazon listings to existing Product Twins,
- matching products reuse stored Ashes assets,
- missing products may be generated within plan limits,
- Ashes prepares Amazon-compatible 3D assets,
- initial publication may include an export/manual submission step if automated 3D upload is not available through an approved API.

The important value is not `generate for Amazon again`.

It is:

> **This is the same physical product. Ashes already has its digital twin. Reuse it.**

---

# 8. LATER — furniture AR / room placement

For furniture and home decor:

```text
shopper opens product
      ↓
View in my room
      ↓
phone camera / AR
      ↓
place existing sofa/chair/table Product Twin in real space
```

The base product model is reused. The sofa should not be reconstructed every time a shopper opens the camera.

Potential later features:

- move/rotate product,
- scale calibration,
- color variants,
- suggest matching table/lamp/rug from the same merchant catalog,
- add the room set to cart.

---

# 9. LATER — fashion try-on / AI fitting room

Fashion is a separate inference layer and comes after core 3D commerce is working.

Potential flow:

```text
shopper opens dress/shirt/etc.
       ↓
Try it on me
       ↓
upload photo or supported camera experience
       ↓
preview product on shopper
       ↓
change available color/variant
       ↓
Ashes suggests real shoes/bag/jacket from merchant catalog
       ↓
preview complete look
       ↓
add selected products to merchant cart
```

Unlike a normal stored 3D view, personalized try-on may require fresh inference per shopper/session.

Therefore it needs:

- explicit privacy/consent rules,
- image-retention policy,
- abuse controls,
- measured per-use inference cost.

Potential monetization models remain experiments:

- merchant-sponsored try-on,
- first try-on free,
- paid extra try-ons,
- optional approximately $0.99/$1 premium fitting-room session,
- usage included in higher merchant plans.

Do not treat the $1 consumer charge as final until actual conversion testing proves it helps rather than hurts sales.

---

# 10. LATER — commerce intelligence

Once enough real merchants/shoppers exist, Ashes should measure whether visual commerce improves outcomes.

Potential funnel:

```text
product view
 -> 3D opened
 -> 3D interacted
 -> AR/try-on used
 -> add to cart
 -> checkout started
 -> purchase completed
```

Possible merchant insights:

- which products benefit from 3D,
- which products should be converted next,
- which AR/try-on experiences are used,
- which combinations are frequently tried together,
- how shoppers who interact with Ashes convert compared with non-interactors,
- revenue influenced by visual experiences.

This is a later data/intelligence moat, not a reason to delay the first Shopify merchant.

---

# 11. LATER — compute scaling

Expected progression:

```text
validation
 -> free/disposable GPU
 -> paid serverless/cloud GPU
 -> dedicated rented compute
 -> Ashes-owned GPU workers when economically justified
 -> hybrid owned baseline + cloud overflow
```

Do not buy large GPU infrastructure until real utilization makes ownership cheaper/more reliable than serverless compute.

---

# 12. Long-term Ashes direction

The intended evolution is:

```text
Image-to-3D capability
       ↓
Shopify visual-commerce app
       ↓
Multi-channel Product Twin platform
       ↓
3D + AR + Try-On shopping layer
       ↓
AI cross-sell / product recommendations
       ↓
Visual-commerce intelligence
       ↓
Global product digital-twin infrastructure
```

The long-term statement remains:

> **A physical product enters Ashes once. Its digital twin can then power every supported visual shopping experience and commerce channel.**

---

# 13. Rule for every future chat or contributor

Before proposing or implementing Ashes work:

1. Do not modify the existing prototype unless the founder explicitly asks for a prototype change.
2. Read `docs/ASHES-MASTER-PLAN.md`.
3. Read this `docs/CURRENT-STATUS.md`.
4. Read `docs/decision-log.md` for strategic context.
5. Determine whether the requested work belongs to **DONE**, **DOING NOW**, **NEXT**, or **LATER**.
6. Do not present a future feature as if it is already implemented.
7. Do not present an old restaurant/QR module as if it is still the main business direction.
8. Update documentation when a major product decision changes.
