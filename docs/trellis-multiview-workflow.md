# Ashes AI TRELLIS multiview workflow

The live prototype includes a real textured burger model generated with Microsoft TRELLIS on a Tesla T4. The successful pipeline was:

1. Prepare three or four consistent views of the same product.
2. Crop each view into an individual image.
3. Run `TrellisImageTo3DPipeline.run_multi_image()` with the `multidiffusion` mode.
4. Decode the mesh and Gaussian representations.
5. Bake a 2048px texture and export a web-ready GLB.

Verified generation settings:

- Python 3.10
- PyTorch 2.4.0 + CUDA 11.8
- xFormers 0.0.27.post2
- 16 sparse-structure steps
- 16 structured-latent steps
- `simplify=0.70`
- `texture_size=2048`

The showcase asset contains 54,220 vertices and 108,330 faces after post-processing. It is served from `/models/ashes-burger-multiview-hq.glb` and opened through the existing `<model-viewer>` product-twin experience.

Real photographs from multiple angles remain the preferred production input. AI-generated alternate views are suitable for prototypes but may invent hidden product details.
