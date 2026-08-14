# Ashes

Ashes is an AI-powered **product digital-twin and visual-commerce platform** for ecommerce merchants.

The core idea is simple:

> **Generate a product once, store it permanently, and reuse the same digital twin everywhere the merchant sells.**

Ashes is being built to turn existing product imagery into reusable 3D commerce assets, starting with Shopify and expanding later to Amazon, WooCommerce and other channels. Future modules include AR placement, virtual try-on, product recommendations and visual-commerce analytics.

## Canonical documentation

The product direction changed significantly from the original restaurant/QR-first prototype. To avoid old modules or old chats becoming the source of truth, read these files before making major changes:

1. **[`docs/ASHES-MASTER-PLAN.md`](docs/ASHES-MASTER-PLAN.md)** — canonical product vision and current strategy
2. **[`docs/architecture.md`](docs/architecture.md)** — technical architecture and Product Twin model
3. **[`docs/roadmap.md`](docs/roadmap.md)** — ordered MVP/growth roadmap
4. **[`docs/business-model.md`](docs/business-model.md)** — pricing, monetization and unit-economics hypotheses
5. **[`docs/decision-log.md`](docs/decision-log.md)** — dated record of major decisions and why they were made

If an older prototype or document conflicts with the master plan, follow the master plan unless a later decision explicitly supersedes it.

## Current product definition

```text
Merchant catalog / product image
          |
          v
     Ashes Product Twin
          |
     asset exists?
       /      \
     yes       no
      |         |
      |     generation job
      |         |
      |         v
      |   disposable GPU worker
      |         |
      |         v
      |     TRELLIS/provider
      |         |
      +----> commerce-ready GLB
                 |
                 v
           S3/R2 + CDN
                 |
       +---------+---------+
       |                   |
       v                   v
    Shopify             Amazon later
       |
       v
  3D / AR / future try-on
```

The GPU is used only to **create** a missing product asset. Shopper views load the already-stored model and do not require reconstruction compute.

## Current engineering milestone

Before expanding the platform, Ashes must reliably prove this path:

```text
real product image
 -> Ashes API
 -> asynchronous generation
 -> disposable/free GPU during testing
 -> real GLB
 -> permanent S3/R2 object
 -> viewer still works after GPU shuts down
```

After this is stable, the next major build is the Shopify installation/catalog/publishing flow.

## Immediate commercial direction

### Connector #1: Shopify

A merchant should eventually be able to:

1. install/connect Ashes,
2. authorize Shopify,
3. let Ashes detect their products,
4. select products or approve Ashes recommendations,
5. generate or reuse a Product Twin,
6. publish a lightweight `View in 3D` experience,
7. keep normal Shopify cart/checkout,
8. see Ashes interaction/commerce analytics over time.

### Connector #2: Amazon

The same merchant account and Product Twin library should later map the same physical products to Amazon listings so Ashes can reuse the existing 3D asset rather than regenerate it.

## Long-term visual-commerce modules

These are strategic directions, not MVP requirements:

- furniture/home-decor AR placement
- fashion virtual try-on / AI fitting room
- `Complete the look` recommendations using real merchant inventory
- room-set recommendations
- multi-channel Product Twin publishing
- commerce analytics and influenced-revenue reporting
- enterprise API and bulk catalog workflows

## Tech stack

- **Frontend:** React + Vite
- **Backend:** FastAPI
- **Database:** MongoDB / MongoDB Atlas
- **3D viewing:** `<model-viewer>`, Three.js / WebXR where needed
- **3D generation:** provider-agnostic Ashes adapter; TRELLIS is the current active testing path
- **Storage:** local in development; S3-compatible object storage in production
- **GPU:** disposable/remote workers during validation; cloud/dedicated/hybrid later
- **Billing:** existing billing modules are present but public plan logic is being realigned with the current commerce model

## Relevant implementation paths

```text
apps/api/services/three_d.py          generation provider/remote worker adapter
apps/api/storage.py                   local + S3-compatible storage abstraction
apps/api/storage_main.py              background generation + permanent storage handoff
tools/trellis/ashes_trellis_worker.py disposable TRELLIS GPU worker
src/                                   React frontend
```

## Backend development

The MongoDB-backed API entrypoint is:

```bash
uvicorn apps.api.mongo_main:app --host 0.0.0.0 --port 8000
```

Minimum local database environment:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=ashes_ai
```

See `.env.example` and `docs/mongodb-setup.md` for environment details.

## Storage / GPU configuration

Development may use local storage. Production should use S3-compatible storage.

The current remote 3D worker path is configured with:

```env
ASHES_TRELLIS_WORKER_URL=
ASHES_TRELLIS_WORKER_TOKEN=
ASHES_3D_TIMEOUT=900
ASHES_STORAGE_PROVIDER=local
```

For S3/R2-compatible production storage, see `.env.example`.

## Current repository history / legacy modules

Ashes previously explored restaurants, QR menus, nutrition, table ordering and a standalone PWA experience. Much of that code remains because it is real working history and may still provide reusable components.

However:

> **Do not assume every existing restaurant/menu/QR module is part of the current primary roadmap.**

The current commercial priority is Ashes Commerce: reusable Product Twins for ecommerce channels.

## Validation rule

Do not optimize for feature count. Optimize for evidence.

```text
1 real generated product
 -> 1 real Shopify merchant
 -> 10 merchants
 -> first paid renewals
 -> $1k MRR
 -> $10k MRR
 -> multi-channel expansion
```

The first proof is not a beautiful landing page. It is a real merchant product becoming a permanent, useful 3D commerce asset.
