# Ashes TRELLIS worker

This folder contains the zero-subscription image-to-3D prototype worker for Ashes AI. The API worker wraps the exact TRELLIS pipeline that successfully exported the multiview burger GLB in `Untitled0.ipynb`.

## Run

1. Open `Untitled0.ipynb` in Google Colab.
2. Select **Runtime → Change runtime type → T4 GPU**.
3. Run the cells in order.
4. Upload either:
   - one clean product photograph and set `SPLIT_2X2_SHEET = False`, or
   - one consistent 2×2 turntable sheet and leave it `True`.
5. Run the final **Ashes API worker** cells. They start FastAPI and print a temporary `https://...trycloudflare.com` URL.
6. Add that URL to Vercel as `ASHES_TRELLIS_WORKER_URL`. If you set a worker token in Colab, add the same value as `ASHES_TRELLIS_WORKER_TOKEN`.
7. Redeploy Ashes AI, then keep the Colab runtime open while testing.

The worker accepts one clean product image, reconstructs hidden geometry, simplifies the mesh, bakes a 2048px texture, and returns a GLB. It uses real `run_multi_image(..., mode="multidiffusion")` when three or four explicit `view_urls` are supplied. The current website sends one source image, so that path uses TRELLIS single-image reconstruction; it does not pretend duplicated or mirrored images are real side views.

## Limits

Free Colab GPUs are not guaranteed. TRELLIS requires Linux and at least 16 GB NVIDIA VRAM, so a T4 is the minimum supported target. A single image produces inferred—not measured—hidden geometry.

## Licence

TRELLIS models and most source code are MIT licensed. Preserve Microsoft's licence notice and verify the licences of TRELLIS submodules. This integration is provided by Ashes AI; Microsoft does not sponsor or endorse Ashes AI.
