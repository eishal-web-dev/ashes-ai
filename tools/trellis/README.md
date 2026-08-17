# Ashes TRELLIS worker

This folder contains the disposable GPU image-to-3D worker for Ashes AI. The worker wraps the TRELLIS pipeline that successfully exported the multiview burger GLB in `Untitled0.ipynb`.

The architectural rule is **generate once, store permanently, serve many times**. The GPU worker is never part of the shopper viewing path. Ashes uploads one merchant product image to the worker, receives a generated GLB, persists that GLB through the main S3/R2 storage layer, and can then shut the GPU worker down.

## Recommended deployment: Modal from GitHub

`modal_ashes_worker.py` is the persistent, scale-to-zero worker for Ashes. It preserves the same HTTP contract as the Colab worker, requests one T4 container at a time, uses 24 reconstruction steps by default, and sends 3–4 real product views through TRELLIS multidiffusion when available.

No local install or clone is required. Deployment is handled by `.github/workflows/deploy-modal-worker.yml`.

### One-time setup

1. Create a Modal account and create an API token in Modal.
2. In this GitHub repository open **Settings → Secrets and variables → Actions**.
3. Add:
   - `MODAL_TOKEN_ID`
   - `MODAL_TOKEN_SECRET`
   - optional but recommended `ASHES_TRELLIS_WORKER_TOKEN`
4. Open **Actions → Deploy Ashes Modal Worker → Run workflow**.
5. The workflow runs `modal deploy tools/trellis/modal_ashes_worker.py` entirely in GitHub Actions. The laptop does not need Python, CUDA, TRELLIS, or Modal installed.
6. Copy the deployed Modal web URL into the Ashes API environment as `ASHES_TRELLIS_WORKER_URL`.
7. If `ASHES_TRELLIS_WORKER_TOKEN` was configured, set the same token on the Ashes API.

After the first deployment, changes to `modal_ashes_worker.py` merged to `main` automatically redeploy the worker. Modal keeps the web endpoint deployed while GPU containers scale to zero when idle.

### Modal architecture

```text
Ashes API
  -> POST /v1/product-to-3d or /v1/product-to-3d-file
  -> Modal CPU web endpoint returns task_id
  -> one T4 generation container wakes
  -> TRELLIS single-image or real multi-view reconstruction
  -> GLB written to temporary Modal Volume
  -> Ashes API polls task_id and downloads GLB
  -> Ashes persists GLB to S3/R2
  -> T4 scales back to zero
```

The Modal image pins Microsoft TRELLIS commit `442aa1e1afb9014e80681d3bf604e8d728a86ee7`, PyTorch 2.4.0, torchvision 0.19.0 and CUDA 12.1. Native TRELLIS CUDA extensions are compiled during the Modal image build using a T4-aware build step. Hugging Face model weights are cached in a Modal Volume after the first successful load.

## Colab development fallback

1. Open `Untitled0.ipynb` in Google Colab.
2. Select **Runtime → Change runtime type → T4 GPU**.
3. Run the cells in order.
4. Upload either:
   - one clean product photograph and set `SPLIT_2X2_SHEET = False`, or
   - one consistent 2×2 turntable sheet and leave it `True`.
5. Run the final **Ashes API worker** cells. They start FastAPI and print a temporary `https://...trycloudflare.com` URL.
6. Add that URL to the Ashes API environment as `ASHES_TRELLIS_WORKER_URL`.
7. If a worker token is configured, set the same value as `ASHES_TRELLIS_WORKER_TOKEN`.

The same HTTP contract can sit behind Modal, Colab, an AWS GPU instance, or Ashes-owned GPU workers without changing the merchant-facing API.

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

The URL workflow supports real multi-view generation. When at least three distinct `view_urls` are supplied, the worker uses `run_multi_image(..., mode="multidiffusion")`. Otherwise it uses the single `image_url` and does single-image inference.

### Poll

`GET /v1/product-to-3d/{task_id}`

Statuses progress through `QUEUED` / `PROCESSING` to either `COMPLETED` or `FAILED`.

### Temporary worker output

`GET /v1/files/{model_id}/model.glb`

The main Ashes API downloads this file and writes it to permanent object storage. Storefronts should not use this temporary worker URL.

## Current reconstruction behavior

The worker accepts one clean product image, reconstructs hidden geometry, simplifies the mesh, bakes a 2048px texture, and returns a GLB. It uses real `run_multi_image(..., mode="multidiffusion")` when three or four explicit product views are supplied. The direct upload path is single-image reconstruction; it does not pretend duplicated or mirrored images are real side views.

The reference-locked/material-aware Ashes refinement stage is intentionally separate from this base reconstruction worker and can be inserted before the final GLB is persisted.

## Limits

Serverless GPU capacity is suitable for development and early production, but availability and pricing are provider-controlled. TRELLIS requires Linux and substantial NVIDIA VRAM. A single image produces inferred—not measured—hidden geometry.

## Licence

TRELLIS models and most source code are MIT licensed. Preserve Microsoft's licence notice and verify the licences of TRELLIS submodules. This integration is provided by Ashes AI; Microsoft does not sponsor or endorse Ashes AI.
