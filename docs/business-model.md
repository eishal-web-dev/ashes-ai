# Ashes Business Model

> Strategic business assumptions for Ashes Commerce. Pricing and monetization are hypotheses until validated by real merchant behavior and measured infrastructure cost.

## 1. Customer

Primary paying customer:

- ecommerce merchant / brand
- initially Shopify merchants
- later Amazon sellers, WooCommerce stores, custom commerce, agencies and enterprise brands

High-priority verticals for validation:

- furniture / home decor
- footwear
- bags / accessories
- fashion
- visual consumer products

Restaurants/food remain possible verticals but are not the primary global SaaS wedge.

## 2. Customer value proposition

Ashes should sell business outcomes and operational simplicity, not merely a GLB file.

Core promise:

> **Connect your catalog once. Ashes creates or reuses a product digital twin, stores it permanently, and lets you use the same interactive product asset across supported sales channels and shopping experiences.**

Merchant value may include:

- no specialist 3D workflow
- reuse existing product photography
- reusable 3D assets
- cross-channel asset reuse
- AR product placement
- future virtual try-on
- richer shopper confidence/engagement
- future analytics and product recommendations

## 3. Revenue model

### A. Merchant subscriptions

Current working hypothesis:

| Plan | Price | Generation allowance | Active product guideline |
|---|---:|---:|---:|
| Trial | $0 / 30 days | 3 total | 3 |
| Starter | $19.99/mo | ~5/mo | ~15 |
| Standard | $45.99/mo | ~20/mo | ~50 |
| Pro | $149.99/mo | ~75/mo | ~250 |
| Enterprise | Custom | Custom | 1,000+ / custom |

These values are not final prices.

### B. Additional generation

Potential add-on packs for merchants who need more new product twins without changing plan.

Exact pack price must be set only after measuring:

- successful GPU generation cost
- retry/failure rate
- optimization cost
- storage/bandwidth impact
- payment/platform fees

### C. Enterprise contracts

Potential enterprise pricing can include:

- large catalog allowances
- API access
- priority generation
- bulk workflows
- multiple channel connections
- custom integrations
- SLA/support
- dedicated capacity

### D. Personalized try-on usage

Personalized try-on can create new compute cost for every shopper/session, unlike normal 3D viewing.

Future experiments:

1. merchant-sponsored usage
2. first try-on free + paid additional looks
3. optional customer-paid fitting-room session around $0.99/$1
4. bundled try-on allowances in higher merchant plans

The consumer-paid model is an experiment, not a locked product rule. Asking the shopper for payment may reduce conversion.

### E. Performance/usage pricing — later

Ashes may later experiment with usage or performance-linked pricing if attribution is technically and contractually reliable.

Do not charge merchants simply for `Add to Cart`; an add-to-cart is not completed revenue.

For the MVP, subscriptions + controlled generation usage are simpler and safer.

## 4. Why generation and active products are different

A generation is expensive GPU work.

An active product is a previously generated asset sitting in permanent storage and being served to shoppers.

These must remain distinct economically.

Example:

```text
Merchant has 50 active 3D products
but generates only 5 new products this month.
```

Ashes pays reconstruction compute for the five new jobs, not for every view of all 50 products.

## 5. Cost-control rules

### Never automatically generate an unbounded catalog during validation

A merchant may have 50, 500 or 50,000 products. Automatic unlimited generation could create large GPU bills before Ashes has revenue.

Early behavior:

- merchant selects products, or
- Ashes recommends candidates and merchant approves them

Later:

- automatic generation can be enabled under explicit plan/catalog budgets

### Reuse before regenerate

Before any generation job:

1. identify merchant
2. search for canonical ProductTwin
3. match SKU/GTIN/channel identity
4. check valid existing asset
5. reuse when compatible
6. only then consume GPU

### Keep free trial bounded

Current hypothesis: 3 total generations in a 30-day trial.

The free period is for proving merchant value, not bulk asset production followed by cancellation.

## 6. Unit economics metric

The critical infrastructure metric is:

> **Cost per successful commerce-ready GLB**

Not simply GPU hourly rate.

Measure:

- GPU model
- wall-clock generation time
- billed GPU seconds/minutes
- preprocessing/postprocessing
- failure and retry rate
- final asset size
- storage/bandwidth

A faster, more expensive GPU per second may still produce a cheaper completed model.

## 7. Shopper viewing economics

Normal 3D viewing should be cheap relative to generation because the same stored asset is reused.

```text
1 generation -> 1 stored GLB -> many shopper views
```

The viewing path should use CDN/object storage, not a reconstruction GPU.

## 8. Acquisition strategy

Do not rely only on marketplace discovery.

Early acquisition should include founder-led outreach:

1. identify a merchant/product with strong 3D value
2. show a compelling demo using their own product where appropriate
3. offer a controlled free trial
4. help them publish the first product
5. collect feedback and renewal data

Strong initial merchant categories are products where shape, fit, placement or detail matters.

## 9. Validation metrics

### Funnel

```text
merchant contacted
 -> installs/connects Ashes
 -> imports products
 -> generates first model
 -> publishes 3D
 -> shoppers interact
 -> trial expires
 -> merchant pays
 -> merchant renews again
```

### Key business metrics

- first-model activation rate
- free-to-paid conversion
- month-2 / month-3 retention
- MRR
- ARPU
- churn
- gross margin
- generation cost per merchant
- active assets per merchant
- international customers by country

## 10. Revenue milestones

Use evidence gates rather than fantasy forecasts.

```text
first paying merchant
 -> $1k MRR
 -> $10k MRR
 -> $100k MRR
 -> broader channel/enterprise expansion
```

Long-term high revenue is possible only if Ashes earns retention and distribution. Revenue forecasts should be updated from actual conversion, churn and ARPU data once available.

## 11. Company structure direction

The intended umbrella name is **Ashes Stack Ltd**, with Ashes Commerce as the first focused product.

The company should not launch many unrelated products before Ashes Commerce has traction. The "Stack" structure preserves future expansion without diluting the current goal.
