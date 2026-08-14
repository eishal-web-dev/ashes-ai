# Ashes TRELLIS worker

This folder contains the disposable GPU image-to-3D worker for Ashes AI. The worker wraps the TRELLIS pipeline that successfully exported the multiview burger GLB in `Untitled0.ipynb`.

The architectural rule is **generate once, store permanently, serve many times**. The GPU worker is never part of the shopper viewing path. Ashes uploads one merchant product image to the worker, receives a generated GLB, persists that GLB through the main S3/R2 storage layer, and can then shut the GPU worker down.

## Run for development

1. Open `Untitled0.ipynb` in Google Colab.
2. Select **Runtime → Change runtime type → T4 GPU**.
3. Run the cells in order.
4. Upload either:
   - one clean product photograph and set `SPLIT_2X2_SHEET = False`, or
   - one consistent 2×2 turntable sheet and leave it `True`.
5. Run the final **Ashes API worker** cells. They start FastAPI and print a temporary `https://...trycloudflare.com` URL.
6. Add that URL to the Ashes API environment as `ASHES_TRELLIS_WORKER_URL`.
7. If a worker token is configured, set the same value as `ASHES_TRELLIS_WORKER_TOKEN`.

The same HTTP contract can later sit behind Hugging Face, Modal, an AWS GPU instance, or Ashes-owned GPU workers without changing the merchant-facing API.

## Worker contract

### Health

`GET /health`

### Generate from a direct image upload

`POST /v1/product-to-3d-file`

- Request body: raw PNG/JPEG bytes
- `Content-Type`: `image/png`, `image/jpeg`, or `application/octet-stream`
- Optional `Authorization: Bearer <token>`
- Optional `X-Product-Name`
- Returns `202` with a `task_id`

### Generate from public image URLs

`POST /v1/product-to-3d`

The existing URL workflow remains available for multi-view generation.

### Poll

`GET /v1/product-to-3d/{task_id}`

Statuses progress through `QUEUED` / `PROCESSING` to either `COMPLETED` or `FAILED`.

### Temporary worker output

`GET /v1/files/{task_id}/model.glb`

The main Ashes API downloads this file and writes it to permanent object storage. Storefronts should not use this temporary worker URL.

## Current reconstruction behavior

The worker accepts one clean product image, reconstructs hidden geometry, simplifies the mesh, bakes a 2048px texture, and returns a GLB. It uses real `run_multi_image(..., mode="multidiffusion")` when three or four explicit `view_urls` are supplied. The direct upload path is single-image reconstruction; it does not pretend duplicated or mirrored images are real side views.

## Limits

Free GPU services are testing infrastructure, not guaranteed production capacity. TRELLIS requires Linux and substantial NVIDIA VRAM. A single image produces inferred—not measured—hidden geometry.

## Licence

TRELLIS models and most source code are MIT licensed. Preserve Microsoft's licence notice and verify the licences of TRELLIS submodules. This integration is provided by Ashes AI; Microsoft does not sponsor or endorse Ashes AI.
