# Ashes Shopify Integration

This folder contains the Shopify connector for Ashes.

## Goal

Merchant installs Ashes → Ashes reads Shopify products → merchant selects a product → Ashes generates a GLB → Ashes uploads and attaches the 3D model to that Shopify product.

## Current setup

- Embedded app configuration
- Product scopes: `read_products,write_products`
- GraphQL-first integration plan
- Separate branch so the existing Ashes app is not broken

## Next steps

1. Create/register the Ashes app in Shopify Partners/Dev Dashboard.
2. Replace `REPLACE_WITH_SHOPIFY_CLIENT_ID` and `REPLACE_WITH_YOUR_APP_URL` in `shopify.app.toml`.
3. Add OAuth/session handling on the Ashes backend.
4. Query the first 10 products through Shopify Admin GraphQL API.
5. Connect selected Shopify product images to the existing Ashes image-to-3D pipeline.
6. Use Shopify staged uploads to upload the generated GLB.
7. Attach the 3D model to the original Shopify product.

Do not commit Shopify client secrets, access tokens, or merchant tokens to GitHub.
