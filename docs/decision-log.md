# Ashes Decision Log

This file records major product and architecture decisions so future contributors and chats can understand **why** Ashes looks the way it does.

Use this format for future decisions:

```text
## YYYY-MM-DD — Decision title
Status: Active | Superseded | Experimental
Decision:
Reason:
Consequences:
Supersedes:
```

---

## 2026-08-14 — Ashes becomes a global visual-commerce platform

**Status:** Active

**Decision:** Ashes is no longer primarily positioned as a restaurant/QR menu product. The main commercial direction is a global ecommerce Product Twin / visual-commerce platform.

**Reason:** The underlying 3D technology has broader value across Shopify, Amazon and product-based ecommerce. A global merchant SaaS has a larger repeatable market than a restaurant-only workflow.

**Consequences:** Existing restaurant/menu/QR modules are treated as legacy or secondary capabilities unless deliberately reused later.

---

## 2026-08-14 — Shopify is Connector #1

**Status:** Active

**Decision:** Prove the complete merchant/product/storefront workflow on Shopify before building every marketplace integration.

**Reason:** The product needs one real commercial end-to-end path before multi-platform complexity.

**Consequences:** Amazon, WooCommerce and other connectors remain part of the platform vision but follow Shopify validation.

---

## 2026-08-14 — Generate once, store permanently, reuse everywhere

**Status:** Active

**Decision:** Product reconstruction runs only when a compatible canonical asset does not already exist. Generated GLBs are stored permanently in Ashes object storage and reused for shopper views and future channels.

**Reason:** GPU generation is expensive; viewing a stored model is comparatively cheap. Reusing assets dramatically improves unit economics.

**Consequences:** GPU availability must never be required for a shopper to view a previously generated product.

---

## 2026-08-14 — One merchant identity can connect multiple channels

**Status:** Active

**Decision:** One Ashes merchant account can connect Shopify, Amazon and future channels. The same physical product should map to one canonical Ashes ProductTwin.

**Reason:** A seller frequently sells the same product in more than one place. Duplicate generation wastes compute and fragments data.

**Consequences:** Ashes needs ChannelConnection, channel-product mapping and product matching/deduplication concepts.

---

## 2026-08-14 — An Ashes linking code does not replace platform OAuth

**Status:** Active

**Decision:** Ashes may expose a merchant/linking code internally, but Shopify/Amazon authorization must still follow official supported authentication/API flows.

**Reason:** External commerce platforms control access to merchant data and require their authorization mechanisms.

---

## 2026-08-14 — TRELLIS is a provider, not the company moat

**Status:** Active

**Decision:** TRELLIS is the current reconstruction engine under testing, but Ashes must keep a provider abstraction so the engine can be replaced or supplemented later.

**Reason:** 3D foundation models will evolve, repositories can disappear, and model generation itself may commoditize.

**Consequences:** Commerce/business logic should call an Ashes generation interface rather than hard-code TRELLIS behavior.

---

## 2026-08-14 — Preserve critical open-source dependencies reproducibly

**Status:** Active

**Decision:** Keep a known-working source/version/environment record for critical dependencies and preserve required licences/attribution. Avoid depending on downloading an upstream repository at runtime.

**Reason:** A production company should not fail because an upstream repository changes or disappears.

**Consequences:** Large checkpoints should live in controlled object storage rather than normal Git history; source/version/checksum/environment metadata belongs in repo documentation.

---

## 2026-08-14 — Free/disposable GPUs are acceptable during validation

**Status:** Active

**Decision:** Colab, ZeroGPU-compatible testing, serverless/free credits or similar disposable compute may be used while validating the product.

**Reason:** The company should not buy expensive infrastructure before proving the end-to-end product and merchant demand.

**Consequences:** The Ashes API must isolate GPU providers behind a worker contract so compute can change without rebuilding the merchant/storefront product.

---

## 2026-08-14 — Long-term compute can become hybrid

**Status:** Active

**Decision:** If Ashes reaches predictable volume, baseline generation may move to dedicated/Ashes-owned GPU workers while cloud/serverless compute handles bursts.

**Reason:** Dedicated hardware can improve economics at sustained utilization, while cloud elasticity is useful for peaks.

---

## 2026-08-14 — Early plans require bounded generation

**Status:** Active

**Decision:** Early free/paid plans should limit new GPU generations even if the future UX hides credits behind catalog-size plans or automatic budgets.

**Reason:** Unlimited generation allows a large catalog to create unbounded compute cost.

**Consequences:** Active stored products and new-generation allowance are distinct concepts.

---

## 2026-08-14 — Working pricing hypothesis

**Status:** Experimental

**Decision:** Current planning numbers are:

- Trial: 30 days, 3 total generations
- Starter: $19.99/month, about 5 new generations/month, about 15 active products
- Standard: $45.99/month, about 20 new generations/month, about 50 active products
- Pro: $149.99/month, about 75 new generations/month, about 250 active products
- Enterprise: custom

**Reason:** $5/month was considered too low for a GPU-backed SaaS without measured unit economics.

**Consequences:** These are not final prices and should not be treated as immutable code requirements. Update after real GPU cost, conversion and retention data.

---

## 2026-08-14 — Furniture AR is a post-MVP priority

**Status:** Active roadmap decision

**Decision:** Furniture/home-decor AR placement is a high-value expansion after core 3D commerce works.

**Reason:** A stored sofa/table/chair model can be placed in a shopper's room without reconstructing it per shopper, giving good utility with manageable compute.

---

## 2026-08-14 — Personalized fashion try-on is a later inference product

**Status:** Active roadmap decision

**Decision:** Virtual try-on is strategic but not part of the first 3D MVP. It may require fresh inference for each user/photo/session.

**Reason:** It is technically and economically different from viewing a stored 3D product and adds privacy requirements.

**Consequences:** Build after core commerce pipeline and define explicit shopper consent/data-retention rules first.

---

## 2026-08-14 — Optional customer-paid fitting room is an experiment

**Status:** Experimental

**Decision:** A roughly $0.99/$1 personalized try-on session may be tested in the future, alongside merchant-sponsored or first-free models.

**Reason:** Personalized inference has per-use cost and can create consumer value, but payment friction may reduce merchant conversion.

**Consequences:** Do not hard-code this charge until tested.

---

## 2026-08-14 — Recommendations should use real merchant inventory

**Status:** Active roadmap decision

**Decision:** `Complete the look` and room-set recommendations should suggest products the merchant actually sells and can add to cart.

**Reason:** The recommendation layer should increase merchant commerce value rather than merely generate attractive but non-purchasable concepts.

---

## 2026-08-14 — Do not rebuild checkout for the Shopify MVP

**Status:** Active

**Decision:** Shoppers use the merchant's existing Shopify cart/checkout. Ashes supplies the visual-commerce layer.

**Reason:** Replacing checkout adds unnecessary payments, compliance and integration complexity before Ashes proves its core value.

---

## 2026-08-14 — Current engineering gate

**Status:** Active

**Decision:** The immediate milestone is one real product image -> disposable GPU -> real GLB -> permanent S3/R2 asset -> viewer still works after GPU shutdown.

**Reason:** This proves the core economics and architecture before Shopify integration is expanded.

**Consequences:** Do not prioritize Amazon, try-on, complex analytics or unrelated UI polish before this gate passes reliably.

---

## 2026-08-14 — Preserve the working prototype unless explicitly asked to change it

**Status:** Active

**Decision:** The existing Ashes prototype view, prototype UI, prototype routes, demo behavior and prototype runtime code must not be redesigned, rewritten or removed merely to make it visually or structurally match the new commerce strategy.

**Reason:** The prototype is already a working demonstration and historical product asset. The strategy can evolve without destroying useful existing work.

**Consequences:** Current documentation may describe the new Shopify/Product Twin direction, while new implementation work should be added around or beside the prototype. Any future change to the prototype requires an explicit founder request. Documentation-only alignment must not be used as justification to alter prototype code.

---

## 2026-08-14 — Maintain a Done / Doing / Next operational status document

**Status:** Active

**Decision:** `docs/CURRENT-STATUS.md` is the fast operational summary for the project and separates implemented work from current validation and future plans.

**Reason:** The Ashes vision is evolving quickly. Future chats and contributors need a simple way to avoid confusing planned features with already-working features.

**Consequences:** Update `CURRENT-STATUS.md` whenever a major milestone moves from NEXT to DOING or from DOING to DONE.
