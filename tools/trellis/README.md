# Ashes TRELLIS worker

This folder contains the zero-subscription image-to-3D prototype worker for Ashes AI.

## Run

1. Open `Ashes_TRELLIS_Image_to_3D.ipynb` in Google Colab.
2. Select **Runtime → Change runtime type → T4 GPU**.
3. Run the cells in order.
4. Upload either:
   - one clean product photograph and set `SPLIT_2X2_SHEET = False`, or
   - one consistent 2×2 turntable sheet and leave it `True`.
5. Download `ashes-product.glb` and `ashes-turntable.mp4`.

The notebook removes the background, uses one or multiple image conditions, reconstructs hidden geometry, simplifies the mesh, bakes a 1024px texture, and exports GLB.

## Limits

Free Colab GPUs are not guaranteed. TRELLIS requires Linux and at least 16 GB NVIDIA VRAM, so a T4 is the minimum supported target. A single image produces inferred—not measured—hidden geometry.

## Licence

TRELLIS models and most source code are MIT licensed. Preserve Microsoft's licence notice and verify the licences of TRELLIS submodules. This integration is provided by Ashes AI; Microsoft does not sponsor or endorse Ashes AI.
