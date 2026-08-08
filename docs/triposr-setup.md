# Ashes AI — TripoSR local setup

Ashes keeps GPU-heavy image-to-3D generation outside the FastAPI process. The API calls `tools/triposr_runner.py`, which runs a local TripoSR checkout and writes a `.glb` into Ashes' managed model folder.

## 1. Clone TripoSR beside Ashes

```powershell
git clone https://github.com/VAST-AI-Research/TripoSR.git
```

Example layout:

```text
Desktop/
├── ashes-ai/
└── TripoSR/
```

## 2. Install TripoSR in its own Python environment

Follow the TripoSR repository's installation instructions for the Python/PyTorch/CUDA versions supported by your machine. Keep its ML dependencies separate from the lightweight Ashes FastAPI virtual environment when possible.

Ashes additionally needs `trimesh` in the environment that runs `tools/triposr_runner.py`:

```powershell
pip install trimesh
```

## 3. Configure Ashes

In the PowerShell session used to start the Ashes API:

```powershell
$env:TRIPOSR_HOME="C:\Users\USER\Desktop\TripoSR"
$env:ASHES_3D_COMMAND="python tools/triposr_runner.py"
$env:ASHES_3D_TIMEOUT="1200"
```

Change the TripoSR path to the actual location on your computer.

## 4. Run Ashes

Backend:

```powershell
cd ashes-ai
.\.venv\Scripts\Activate.ps1
uvicorn apps.api.main:app --reload --port 8000
```

Frontend in a second terminal:

```powershell
cd ashes-ai
npm run dev
```

## 5. Test the pipeline

1. Open Ashes Business.
2. Add a product.
3. Upload one clean food/product photo.
4. Submit the product.
5. The API moves it through `queued` → `processing` → `ready` when TripoSR succeeds.
6. Open the customer experience. The generated GLB is loaded automatically.

## Notes

- A single photo cannot reveal hidden surfaces; the model reconstructs/invents unseen geometry.
- Clean backgrounds and a clearly isolated object usually give better reconstruction inputs.
- Food quality should be judged visually before selling the feature to restaurants.
- TripoSR is only the first Ashes provider. The worker interface is designed so Stable Fast 3D or Hunyuan3D can replace it later.
