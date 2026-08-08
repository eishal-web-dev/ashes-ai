# Ashes AI — UI Direction

## Visual identity

Ashes AI should feel like a next-generation AI commerce platform rather than a standard restaurant dashboard.

### Core look
- Near-black / deep plum background
- Electric magenta, violet and cyan glow accents
- Glassmorphism cards with thin luminous borders
- Soft radial glows behind hero content
- Futuristic display typography for headings
- Clean sans-serif typography for body text
- Rounded rectangular controls with neon edge highlights
- Floating data chips and status pills
- Large cinematic product/3D imagery
- Sparse particles / ambient light specks used carefully

### Product personality
Premium, futuristic, intelligent, immersive, high-tech, polished.

Avoid:
- Generic bootstrap/admin templates
- Flat white cards
- Cartoonish gradients
- Excessive glow on every element
- NFT/crypto wording or visual motifs copied literally

## Landing page

### Header
- ASHES AI logo left
- Explore
- For Businesses
- How It Works
- Pricing
- Sign In
- Primary CTA: Join Ashes

### Hero
Left side:
- Eyebrow: AI-POWERED 3D COMMERCE
- Headline: `TURN PRODUCTS INTO EXPERIENCES`
- Supporting text explaining one-photo-to-3D, QR and AR
- CTAs: `Explore Ashes` and `Join as a Business`

Right side:
- Large floating 3D product viewer / hero model
- Floating glass data chips such as:
  - `3D Ready`
  - `AR Enabled`
  - `Nutrition AI`
  - `QR Live`
- Orbit / glow effect behind product

### Business showcase
Glass container featuring joined businesses and featured products.
Cards show:
- product image / 3D preview
- business name
- product name
- price
- optional nutrition badges
- `View in 3D`
- `View in AR`

## Customer experience
When a QR is scanned:
- business logo/name
- immersive hero product
- tabs: Menu / Details / Nutrition
- interactive 3D viewer
- AR CTA
- price
- calories/macros/allergens when relevant
- add to order / buy / contact business CTA

## Business dashboard
Keep the same visual language, but more functional.

Navigation:
- Overview
- Products
- 3D Generator
- QR Codes
- Orders
- Analytics
- Business Profile
- Billing

Dashboard hero cards:
- total products
- 3D-ready products
- QR scans
- AR views
- conversion rate

### 3D generation workflow
A visually important flow:
1. Upload one product photo
2. AI isolates product
3. Generate 3D
4. Preview model
5. Add/edit metadata
6. Generate QR
7. Publish

Show generation as a glowing processing pipeline rather than a plain progress bar.

## Color tokens
Use these as starting values, refined during implementation:

- `--bg-0`: `#05030a`
- `--bg-1`: `#0b0613`
- `--surface`: `rgba(25, 15, 35, 0.68)`
- `--surface-strong`: `rgba(36, 20, 49, 0.82)`
- `--border`: `rgba(255, 255, 255, 0.12)`
- `--pink`: `#ff2da1`
- `--violet`: `#8b5cff`
- `--cyan`: `#53e8ff`
- `--text`: `#f8f5ff`
- `--muted`: `#aaa0ba`

Use gradients primarily for accents and glows, not large text blocks everywhere.

## Motion
- slow floating hero product
- cursor-reactive glow on desktop
- card lift on hover
- subtle neon border sweep
- QR scan pulse
- AI generation particle/progress animation
- 3D model rotates very slowly when idle

Respect `prefers-reduced-motion`.

## Mobile/PWA
The design must remain premium on phones.
- sticky bottom action bar where useful
- large AR CTA
- horizontal product carousels
- no tiny desktop-style navigation
- fast loading and progressive enhancement

## Brand line ideas
Primary working line:

**Reality, rendered.**

Alternates:
- `See it before you choose it.`
- `From one photo to another dimension.`
- `Scan. See. Experience.`
