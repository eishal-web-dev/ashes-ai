# Ashes AI LinkedIn Prototype Plan

## Target demo

A visitor pastes a public merchant website URL and sees one continuous story:

1. Ashes scans the website.
2. Brand and product data becomes a reviewable draft catalog.
3. A selected product opens in an interactive 3D viewer.
4. Ashes creates a product QR code.
5. Scanning the QR opens the mobile product experience.

The demo must be understandable in under 60 seconds and must never claim that a 3D model was generated when only an image fallback exists.

## Audit summary

### Already present

- Authenticated business accounts and multi-tenant data
- Website catalog crawler with basic JSON-LD/Open Graph product extraction
- Draft product creation
- Product experience and GLB storage fields
- QR creation endpoints
- Public product/menu deep links
- PWA configuration
- MongoDB, FastAPI and React/Vite structure

### Gaps to close

- The import feature is hidden inside an authenticated commerce-source modal.
- There is no single public prototype route joining import, catalog review, 3D and QR.
- The importer misses many listing-page and Shopify/WooCommerce catalog shapes.
- The 3D pipeline has no hosted provider fallback when the local command is absent.
- Product readiness states are fragmented and can over-promise what is actually available.
- QR creation is business/table oriented; the demo needs a clearer product QR studio.
- Frontend code is spread across global enhancer overlays and many cascading CSS layers.
- There are no browser-level prototype tests.
- Generated environments and credential files were committed and must be removed from history.

## Delivery chunks

### Chunk 1 — Foundation and safety

- Remove tracked secrets from the current branch.
- Ignore local environments, secrets, build output and generated media.
- Rotate MongoDB Atlas and any other exposed keys.
- Remove the committed virtual environment from Git history in a dedicated cleanup.
- Lock a stable Node/Python toolchain.

Acceptance: a clean checkout contains no secret files or virtual environment.

### Chunk 2 — Prototype Studio

- Add a first-class `/prototype` experience.
- Accept and validate one public website URL.
- Show honest stages: connecting, scanning, extracting, preparing drafts.
- Display import results with product count, image, name, price and source URL.
- Provide a curated demo dataset when the live merchant blocks crawling.

Acceptance: a LinkedIn viewer can understand the product within 60 seconds.

### Chunk 3 — Import quality

- Add Shopify product JSON and collection extraction.
- Add WooCommerce JSON-LD/listing extraction.
- Resolve relative image URLs and normalize currency.
- Deduplicate by canonical URL/SKU.
- Return per-product warnings and import provenance.
- Add crawl limits, response-size limits and clear blocked-site messages.

Acceptance: the chosen showcase website imports a useful catalog consistently.

### Chunk 4 — 3D experience

- Define explicit states: image received, queued, processing, 3D ready, failed.
- Connect a hosted image-to-3D provider or pre-generated showcase GLBs.
- Preserve an honest image turntable fallback.
- Optimize GLB size, lighting, camera controls and mobile performance.

Acceptance: at least three showcase products have real interactive GLBs and graceful fallbacks.

### Chunk 5 — QR and share

- Generate one product QR per imported item.
- Add copy-link and PNG-download actions.
- Ensure QR targets use the deployed public base URL.
- Create a polished mobile scan destination.

Acceptance: a QR scanned from another phone opens the correct product directly.

### Chunk 6 — LinkedIn polish and deployment

- Responsive cinematic UI and concise product storytelling.
- Demo reset/replay controls for screen recording.
- Error, empty and slow-network states.
- Frontend build, API tests and end-to-end happy-path test.
- Deploy frontend/API and record the final demo.

Acceptance: deployed demo works on desktop and mobile and is ready to record.
