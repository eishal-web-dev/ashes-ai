import os
from pathlib import Path

import modal

APP_NAME = "ashes-trellis"
MODEL_ID = "microsoft/TRELLIS-image-large"
MODEL_DIR = Path("/models")
OUTPUT_DIR = Path("/outputs")

# This image mirrors the CUDA/PyTorch combination that already worked in the
# Ashes Colab notebook: Python 3.10, PyTorch 2.4.0, CUDA 11.8, xformers/spconv.
image = (
    modal.Image.from_registry(
        "nvidia/cuda:11.8.0-devel-ubuntu22.04",
        add_python="3.10",
    )
    .apt_install(
        "git",
        "build-essential",
        "libgl1",
        "libglib2.0-0",
        "libgomp1",
    )
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        index_url="https://download.pytorch.org/whl/cu118",
    )
    .pip_install(
        "fastapi[standard]",
        "requests",
        "pillow",
        "numpy",
        "imageio",
        "imageio-ffmpeg",
        "easydict",
        "rembg",
        "trimesh",
        "xatlas",
        "opencv-python-headless",
        "huggingface-hub",
        "xformers==0.0.27.post2",
        extra_index_url="https://download.pytorch.org/whl/cu118",
    )
    .pip_install("spconv-cu118")
    .run_commands(
        "git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git /opt/TRELLIS",
        "cd /opt/TRELLIS && bash -lc 'source ./setup.sh --basic --xformers --diffoctreerast --spconv --mipgaussian --kaolin --nvdiffrast'",
    )
    .env(
        {
            "PYTHONPATH": "/opt/TRELLIS",
            "ATTN_BACKEND": "xformers",
            "SPCONV_ALGO": "native",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
    )
)

app = modal.App(APP_NAME)
outputs = modal.Volume.from_name("ashes-trellis-outputs", create_if_missing=True)


@app.cls(
    image=image,
    gpu="T4",
    timeout=1800,
    startup_timeout=900,
    scaledown_window=300,
    volumes={str(OUTPUT_DIR): outputs},
)
class TrellisModel:
    @modal.enter()
    def load(self):
        import torch
        from trellis.pipelines import TrellisImageTo3DPipeline

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available inside the Modal worker")

        self.pipeline = TrellisImageTo3DPipeline.from_pretrained(MODEL_ID)
        self.pipeline.cuda()

    @modal.method()
    def generate(self, image_url: str, product_name: str = "Product") -> str:
        import io
        import re
        import requests
        from PIL import Image
        from trellis.utils import postprocessing_utils

        response = requests.get(image_url, timeout=45)
        response.raise_for_status()
        source = Image.open(io.BytesIO(response.content)).convert("RGBA")

        result = self.pipeline.run(source, seed=1)
        glb = postprocessing_utils.to_glb(
            result["gaussian"][0],
            result["mesh"][0],
            simplify=0.95,
            texture_size=1024,
        )

        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", product_name).strip("-")[:80] or "product"
        filename = f"{safe}-{os.urandom(6).hex()}.glb"
        target = OUTPUT_DIR / filename
        glb.export(str(target))
        outputs.commit()
        return filename


web_image = modal.Image.debian_slim(python_version="3.10").pip_install(
    "fastapi[standard]"
)


@app.function(image=web_image, volumes={str(OUTPUT_DIR): outputs})
@modal.asgi_app()
def api():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse
    from pydantic import BaseModel

    web = FastAPI(title="Ashes TRELLIS Modal Worker")

    class GeneratePayload(BaseModel):
        image_url: str
        product_name: str = "Product"
        view_urls: list[str] | None = None

    @web.get("/health")
    def health():
        return {
            "ok": True,
            "provider": "modal",
            "engine": "trellis",
            "model": MODEL_ID,
            "gpu": "T4",
        }

    @web.post("/v1/product-to-3d", status_code=202)
    def start(payload: GeneratePayload):
        if not payload.image_url.startswith("https://"):
            raise HTTPException(400, "image_url must be a public HTTPS URL")

        call = TrellisModel().generate.spawn(payload.image_url, payload.product_name)
        return {
            "task_id": call.object_id,
            "status": "QUEUED",
            "stage": "QUEUED",
        }

    @web.get("/v1/product-to-3d/{task_id}")
    def status(task_id: str, request: Request):
        call = modal.FunctionCall.from_id(task_id)
        try:
            filename = call.get(timeout=0)
        except TimeoutError:
            return {
                "task_id": task_id,
                "status": "PROCESSING",
                "stage": "GENERATING_3D",
                "progress": 0.5,
            }
        except Exception as exc:
            return {
                "task_id": task_id,
                "status": "FAILED",
                "stage": "FAILED",
                "progress": 0,
                "error": str(exc)[:500],
            }

        model_url = str(request.base_url).rstrip("/") + f"/v1/model/{task_id}.glb"
        return {
            "task_id": task_id,
            "status": "COMPLETED",
            "stage": "COMPLETED",
            "progress": 1.0,
            "model_url": model_url,
            "filename": filename,
        }

    @web.get("/v1/model/{task_id}.glb")
    def model(task_id: str):
        call = modal.FunctionCall.from_id(task_id)
        try:
            filename = call.get(timeout=0)
        except TimeoutError as exc:
            raise HTTPException(409, "Generation is still running") from exc
        except Exception as exc:
            raise HTTPException(500, str(exc)[:500]) from exc

        outputs.reload()
        path = OUTPUT_DIR / filename
        if not path.exists():
            raise HTTPException(404, "Generated GLB is not available")
        return FileResponse(path, media_type="model/gltf-binary", filename=filename)

    return web
