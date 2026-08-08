# Ashes AI

Ashes AI is a multi-tenant AI-powered 3D/AR commerce platform for restaurants, cafés, retailers, and product brands.

## Vision

One platform. Many businesses. One customer experience.

Businesses join Ashes AI, create a storefront, upload a product or menu photo, attach or generate a 3D asset, and receive QR codes. Customers scan the QR with their phone and open the same Ashes web app/PWA to view the item in interactive 3D or AR — no separate app per restaurant or brand.

## MVP

- Business onboarding
- Multi-tenant business profiles
- Restaurant / café / retail support
- Product and menu item management
- One-photo upload workflow
- 3D asset status and GLB support
- QR code generation
- Public QR landing pages
- Interactive 3D viewer
- AR-ready viewer architecture
- Nutrition fields for food items
- Calories, protein, carbs, fats, allergens and ingredients
- Business dashboard
- Pricing/subscription-ready architecture
- PWA-first customer experience

## Core customer flow

1. Scan an Ashes QR code.
2. Open the business/product instantly in the browser.
3. View the product in 3D.
4. Launch AR where the device supports it.
5. See price, ingredients, nutrition, allergens and product details.
6. Continue to order or purchase.

## Core business flow

1. Create a business account.
2. Add restaurant, café, store or brand.
3. Add products/menu items.
4. Upload one primary product photo.
5. Generate or attach a `.glb` 3D asset.
6. Review AI-generated product information.
7. Generate a QR code.
8. Place the QR on tables, menus, packaging or store displays.
9. View scans and engagement from the Ashes dashboard.

## Architecture

```text
Customer Phone
     |
     | Scan QR
     v
Ashes PWA / Web App
     |
     +--> Business storefront
     +--> Product/menu details
     +--> 3D/AR viewer
     |
     v
Ashes API
     |
     +--> Authentication
     +--> Multi-tenant businesses
     +--> Products/menu items
     +--> QR links
     +--> Nutrition metadata
     +--> Orders (later)
     +--> Analytics (later)
     |
     +--> Image-to-3D service
     |
     v
Database + Object Storage
```

## Proposed stack

- **Frontend:** React + Vite + TypeScript
- **PWA:** Vite PWA
- **3D/AR:** `<model-viewer>` first, Three.js / WebXR where needed
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **Object storage:** S3-compatible storage
- **Auth:** JWT/session-based auth
- **QR:** server-generated links and QR images
- **3D generation:** provider-agnostic adapter so we can test TripoSR, Stable Fast 3D, Hunyuan3D or an external API without rewriting the product

## Multi-tenant model

```text
Ashes AI
├── Business A
│   ├── Branches
│   ├── Products / Menu Items
│   └── QR Codes
├── Business B
│   ├── Products
│   └── QR Codes
└── Business C
```

Every record is scoped by `business_id`, so Ashes can support hundreds or thousands of businesses inside the same platform.

## Repository layout

```text
ashes-ai/
├── apps/
│   ├── web/              # React PWA
│   └── api/              # FastAPI backend
├── packages/
│   ├── shared/           # Shared schemas/types
│   └── ar-viewer/        # Reusable 3D/AR viewer logic
├── services/
│   └── image-to-3d/      # Provider abstraction + generation workers
├── docs/
│   ├── architecture.md
│   └── roadmap.md
└── README.md
```

## Important product rule

AI-generated nutrition and allergen information must be treated as an estimate until confirmed by the business. Businesses should review and approve generated data before publishing.

## Status

🚧 MVP foundation in progress.
