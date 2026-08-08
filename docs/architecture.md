# Ashes AI Architecture

## Product model

Ashes AI is a multi-tenant platform. A tenant is a business such as a restaurant, café, retailer, furniture store, bakery, fashion brand, or other product seller.

Customers do not install one app per business. A QR code opens the relevant Ashes experience directly in the browser/PWA.

## Primary entities

### User
- id
- email
- password_hash / auth_provider
- role
- created_at

### Business
- id
- owner_user_id
- name
- slug
- business_type
- logo_url
- description
- currency
- subscription_plan
- subscription_status
- created_at

### Branch
- id
- business_id
- name
- address
- latitude
- longitude

### Product
- id
- business_id
- branch_id (optional)
- name
- slug
- description
- category
- price
- currency
- primary_image_url
- model_3d_url
- model_status
- product_type
- is_available
- created_at

### FoodNutrition
- product_id
- serving_size
- calories_kcal
- protein_g
- carbs_g
- fat_g
- sugar_g
- fiber_g
- caffeine_mg
- ingredients
- allergens
- dietary_tags
- source
- verified_by_business

### QRCode
- id
- business_id
- product_id (optional)
- branch_id (optional)
- destination_path
- short_code
- scan_count
- created_at

### ModelGenerationJob
- id
- business_id
- product_id
- provider
- source_image_url
- status
- output_model_url
- error_message
- created_at
- completed_at

## Tenant isolation

Every business-owned row includes `business_id`. API queries must scope records using the authenticated user's permitted business IDs. Never trust a business ID sent by the browser without authorization checks.

## QR routing

Example destinations:

- `/b/hujra`
- `/b/hujra/menu`
- `/b/hujra/p/zinger-stack`
- `/q/Ab91xQ`

`/q/:shortCode` resolves to a business, product, branch or campaign destination and increments analytics before redirect/rendering.

## 3D generation pipeline

```text
Business uploads image
        |
        v
Object storage
        |
        v
Create ModelGenerationJob
        |
        v
Image-to-3D provider adapter
        |
        +--> TripoSR
        +--> Stable Fast 3D
        +--> Hunyuan3D
        +--> External API
        |
        v
Post-process / optimize GLB
        |
        v
Object storage + CDN
        |
        v
Product.model_3d_url
```

The rest of Ashes never talks directly to a specific AI model. It uses a provider interface so providers can be changed later.

## Viewer strategy

MVP:
- Google `<model-viewer>` for GLB rendering
- orbit controls
- camera controls
- poster/loading state
- AR modes where supported

Later:
- Three.js custom viewer
- WebXR hit testing
- product scale calibration
- scene lighting presets
- product annotations

## Nutrition pipeline

For food products, Ashes can accept:
- recipe/ingredient data supplied by restaurant
- serving weight
- packaging nutrition label
- optional AI estimate from image + description

AI-only estimates must be clearly labelled as estimates. Allergens must not be presented as verified unless the business confirms them.

## Security

- Never expose AI provider secrets in the PWA.
- Upload through signed URLs or the API.
- Validate image/model MIME types and size.
- Authorize every business mutation server-side.
- Rate-limit QR analytics and AI generation endpoints.
- Store billing webhook secrets only on backend.

## Scaling path

MVP can run as a modular monolith:
- one React web app
- one FastAPI service
- PostgreSQL
- object storage

Split generation workers and analytics into separate services only when usage requires it.
