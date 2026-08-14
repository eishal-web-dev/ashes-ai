# Ashes Accurate v0.1 — Colab benchmark

This branch is an experimental development branch. It must not replace the live Hugging Face worker until its outputs are reviewed.

## Objective

Choose a repeatable configuration that preserves product geometry and texture detail in the exported GLB—not merely in the Gaussian preview video.

## Fixed test assets

Use the same source assets for every run:

1. Burger: single image and four/eight real views when available.
2. Phoenix: single image and four/eight consistent real views when available.
3. A rigid product with text or a logo.
4. A thin-detail product such as footwear, jewellery, feathers, or layered food.

Do not use AI-generated side views in an accuracy benchmark.

## Controlled variables

Keep the seed fixed at 0 for the first comparison.

| Run | Views | SS steps | SLAT steps | Simplify | Texture |
|---|---:|---:|---:|---:|---:|
| P1 preview | 1 | 8 | 8 | 0.75 | 1024 |
| B1 baseline | 1 | 12 | 12 | 0.50 | 2048 |
| D1 detail | 1 | 20 | 20 | 0.25 | 4096 |
| M1 accurate | 4 | 20 | 20 | 0.25 | 4096 |
| M2 accurate | 8 | 20 | 20 | 0.10 | 4096 |
| M3 master | 8 | 24 | 24 | 0.00 | 4096 |

Only increase sampling steps after comparing the previous run. More steps cost GPU time and are not automatically more accurate.

## Save for every run

```text
experiments/<product>/<run-id>/
  inputs/
  ashes-preview.mp4
  ashes-gaussian.ply
  ashes-model.glb
  ashes-generation-config.json
  notes.md
```

Record runtime, GPU, GLB size, visible defects, and whether the run completed.

## Review protocol

Review the GLB itself from front, back, left, right, top, and two diagonal angles.

Score each category from 0–5:

- silhouette accuracy
- hidden-side consistency
- thin-part preservation
- texture and logo sharpness
- material appearance
- holes/floating geometry
- resemblance to the real product

Reject a result if any required view has a major shape error, missing component, unreadable important branding, or disconnected geometry.

## Promotion rule

A configuration becomes an Ashes preset only when it:

1. beats the current baseline GLB on at least three different product categories;
2. remains reproducible with a fixed seed;
3. completes within the declared GPU budget;
4. has an acceptable storefront asset size;
5. is evaluated from the GLB, not solely from the preview video.

## Planned production presets

### Ashes Preview

Target: quick plausibility check.

- one image allowed
- 8/8 sampling steps initially
- 1024 texture
- stronger simplification
- shorter 60-frame preview
- never labelled measurement-accurate

### Ashes Accurate

Target: faithful ecommerce asset.

- minimum four real views; six to eight preferred
- fixed/reported seed
- 20/20 sampling steps initially
- 4096 master texture
- 0–0.25 master simplification
- Gaussian and master GLB retained
- optimized storefront GLB derived from the master

## Storage contract

Generated files must eventually be copied out of Colab/Hugging Face temporary storage:

```text
products/<product-id>/master/model.ply
products/<product-id>/master/model.glb
products/<product-id>/web/model.glb
products/<product-id>/preview.webp
products/<product-id>/generation-config.json
products/<product-id>/quality-report.json
```

The generation worker creates assets once. Storefront visitors only download saved assets and never trigger GPU generation.
