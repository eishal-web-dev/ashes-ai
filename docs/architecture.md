# Ashes Architecture

> Read `docs/ASHES-MASTER-PLAN.md` first. This file describes the technical architecture that implements the current product direction.

## 1. Architectural objective

Ashes is a multi-tenant visual-commerce platform. A merchant can connect multiple commerce channels to one Ashes identity, create/reuse one canonical product twin per physical product, and distribute that asset across supported storefronts.

The core rule is:

> **Generate once. Store permanently. Reuse everywhere.**

The GPU is disposable creation compute. Shopper traffic must never depend on the GPU worker remaining online.

## 2. High-level system

```text
                         ASHES

      Shopify          Amazon          Future channels
          \              |                /
           \             |               /
            +------ Channel Connectors --+
                         |
                         v
                 Merchant / Catalog API
                         |
                         v
                 Product Twin Registry
                  /               \
          asset exists?         asset missing?
               |                    |
               |                    v
               |             Generation Queue
               |                    |
               |                    v
               |             Disposable GPU Worker
               |                    |
               |                    v
               |              TRELLIS/provider
               |                    |
               +-----------> Optimized GLB
                                  |
                                  v
                        S3/R2 Object Storage
                                  |
                                  v
                                 CDN
                                  |
                   +--------------+--------------+
                   |              |              |
                   v              v              v
             Shopify viewer   AR placement   Amazon export
```

## 3. Primary entities

### User

- id
- email
- password_hash / auth_provider
- role
- created_at

### Merchant / Business

Legacy code may still use `Business` naming. Conceptually this is the merchant tenant.

- id
- owner_user_id
- name
- slug
- business_type
- logo_path
- description
- currency
- subscription_plan
- subscription_status
- created_at

### ChannelConnection

Represents one external commerce account connected to the same Ashes merchant.

- id
- merchant_id
- provider (`shopify`, `amazon`, `woocommerce`, ...)
- external_account_id
- external_shop/domain identifier
- encrypted credential/token reference
- status
- scopes / permissions
- connected_at
- last_sync_at

Official provider OAuth/API authorization is required where the platform requires it. An Ashes linking code may help identify the same merchant internally but does not replace platform authorization.

### ProductTwin

Canonical Ashes identity for one physical sellable product.

- id
- merchant_id
- canonical_sku
- gtin/upc/ean (optional)
- title
- product_type/category
- canonical_image_path
- model_path
- model_status
- model_version
- dimensions / scale metadata
- created_at
- updated_at

### ChannelProductLink

Maps a canonical ProductTwin to external listings.

- id
- product_twin_id
- channel_connection_id
- external_product_id
- external_variant_id
- asin (Amazon where applicable)
- seller_sku
- external_url
- sync_status
- last_synced_at

### ProductAsset

A future-normalized asset registry can hold several reusable outputs.

- id
- product_twin_id
- asset_type (`source_image`, `glb`, `thumbnail`, `ar`, `tryon_metadata`, ...)
- storage_key
- content_type
- version
- checksum
- file_size
- status
- created_at

Current code stores image/model paths directly on product records; migration to a normalized registry can happen incrementally.

### ModelGenerationJob

- id
- merchant_id
- product_twin_id / product_id
- provider
- source_image reference
- status
- stage
- progress
- output_model reference
- error_message
- gpu_seconds (future)
- generation_cost (future)
- created_at
- started_at
- completed_at

### Subscription / Usage

- merchant_id
- plan
- billing status
- monthly generation usage/budget
- active product allowance
- optional add-on usage

Do not assume the current legacy billing constants are the final public pricing model.

## 4. Product matching / deduplication

Before generation, Ashes should attempt to resolve whether the product already has a valid ProductTwin.

Suggested confidence inputs:

1. merchant identity
2. exact SKU/seller SKU
3. GTIN/UPC/EAN
4. channel variant IDs already linked
5. normalized title/category
6. image similarity
7. merchant confirmation

A cross-channel match should link the external listing to the existing ProductTwin rather than create another GPU job.

## 5. 3D generation pipeline

Current desired path:

```text
Merchant selects/imports image
        |
        v
Create/queue ModelGenerationJob
        |
        v
Ashes 3D provider adapter
        |
        +--> remote TRELLIS worker (current active path)
        +--> local command fallback (development)
        +--> future provider/model
        |
        v
Temporary generated GLB
        |
        v
Post-process / validate / optimize
        |
        v
S3/R2 permanent object storage
        |
        v
Update ProductTwin/Product.model_path
        |
        v
GPU worker can terminate
```

### Current repo implementation

- `apps/api/services/three_d.py` — provider/worker adapter
- `apps/api/storage_main.py` — background generation + permanent storage handoff
- `apps/api/storage.py` — local/S3-compatible storage abstraction
- `tools/trellis/ashes_trellis_worker.py` — disposable TRELLIS GPU worker

The worker may be hosted on Colab, Hugging Face-compatible infrastructure, Modal, cloud GPU, or later Ashes-owned GPU infrastructure as long as it satisfies the worker/provider contract.

## 6. Provider independence

The rest of Ashes must not depend on TRELLIS-specific APIs.

Conceptual interface:

```text
GenerationProvider.generate(input) -> generation job/result
```

Potential provider implementations:

- TrellisProvider
- FutureTrellisProvider
- FutureAshesModelProvider
- approved fallback provider

This makes the company resilient to repository disappearance, model changes, or a better reconstruction engine becoming available.

## 7. Permanent storage

Development:

- local filesystem

Production:

- S3-compatible object storage (AWS S3, R2, etc.)

Current environment switch:

```text
ASHES_STORAGE_PROVIDER=local|s3|r2
```

Model assets should have stable keys tied to merchant/product identity rather than temporary GPU task IDs.

Suggested logical structure:

```text
products/{merchant_id}/{product_id}/source.webp
models/{merchant_id}/{product_id}.glb
thumbnails/{merchant_id}/{product_id}.webp
```

A CDN should eventually front public model/texture assets.

## 8. Viewer strategy

MVP:

- `<model-viewer>` or equivalent lightweight GLB rendering
- orbit controls
- poster/loading state
- lazy loading
- AR modes where supported
- no blocking of initial storefront render

Later:

- richer Three.js viewer
- WebXR hit testing
- scale calibration
- material/color variants
- annotations
- multi-product room scenes

Storefront performance is a product requirement. Heavy 3D must not degrade merchant conversion or Core Web Vitals.

## 9. AR placement

Furniture/home-decor AR should reuse the existing ProductTwin GLB.

Flow:

```text
Stored sofa.glb
   -> shopper opens AR
   -> camera/world tracking
   -> place/move/scale validated product
```

No product reconstruction should happen per shopper.

## 10. Personalized try-on

Virtual try-on differs from normal product viewing because it can require fresh inference for each shopper/photo/session.

Conceptual flow:

```text
Stored merchant product data
      + shopper photo/camera input
      -> try-on inference
      -> temporary/personalized result
      -> optional recommendations
```

Personal photos require explicit privacy, retention and deletion rules before production launch of this module.

## 11. Commerce analytics

Long-term event model:

- product_viewed
- ashes_3d_opened
- ashes_3d_interacted
- ar_opened
- tryon_started
- tryon_completed
- recommendation_viewed
- add_to_cart
- checkout_started
- purchase_completed

Attribution must be conservative. Do not claim Ashes caused a sale merely because a user opened a 3D viewer.

## 12. Security

- Never expose provider/API secrets in storefront JavaScript.
- Encrypt/store commerce authorization tokens server-side.
- Validate image/model MIME type and size.
- Authorize every merchant mutation server-side.
- Rate-limit generation and analytics endpoints.
- Authenticate GPU worker calls.
- Prevent private-network/SSRF access in URL-based worker ingestion.
- Never trust checkout/order totals from a browser.
- Define privacy/deletion behavior before accepting shopper photos for try-on.

## 13. Scaling path

### Validation

- React/Vite frontend
- FastAPI modular monolith
- MongoDB
- S3/R2-compatible storage
- disposable/free GPU worker

### Early production

- durable generation queue
- serverless/paid GPU workers
- CDN
- Shopify connector
- generation cost telemetry

### Growth

- multiple GPU workers
- queue priorities/retries
- cloud autoscaling
- separate analytics pipeline
- multi-channel product registry

### Scale / hybrid compute

Normal predictable generation can move to dedicated or Ashes-owned GPU workers. Cloud/serverless GPU capacity remains useful for bursts and overflow.

## 14. Legacy modules

Restaurant QR, menu, nutrition, table-ordering and related modules may remain in the repository. They are not automatically deleted, but they should be treated as legacy/secondary capabilities unless explicitly pulled back into the current roadmap.
