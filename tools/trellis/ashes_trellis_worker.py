import ipaddress
import os
import socket
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
import torch
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

os.environ.setdefault("ATTN_BACKEND", "xformers")
os.environ.setdefault("SPCONV_ALGO", "native")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils

ROOT = Path("/content/ashes-worker")
ROOT.mkdir(parents=True, exist_ok=True)
TOKEN = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
TASKS: dict[str, dict] = {}
GPU_LOCK = threading.Lock()

app = FastAPI(title="Ashes TRELLIS Worker", version="1.0")
pipeline = None


class GenerationRequest(BaseModel):
    image_url: str
    product_name: str = "Product"
    view_urls: list[str] | None = None
    generate_views: dict | None = None
    reconstruction: dict | None = None


def authorize(authorization: str | None):
    if TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Invalid worker token")


def public_https(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only public HTTPS images are accepted")
    for info in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("Private-network images are not accepted")
    return value


def download_image(url: str, target: Path) -> Image.Image:
    url = public_https(url)
    with requests.get(url, timeout=25, stream=True, headers={"User-Agent": "Ashes-TRELLIS/1.0"}) as response:
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("image/"):
            raise ValueError("URL did not return an image")
        size = 0
        with target.open("wb") as output:
            for chunk in response.iter_content(1024 * 256):
                size += len(chunk)
                if size > 12_000_000:
                    raise ValueError("Image exceeds 12 MB")
                output.write(chunk)
    return Image.open(target).convert("RGB")


def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
        pipeline.cuda()
    return pipeline


def update(task_id: str, **values):
    TASKS[task_id].update(values)


def generate(task_id: str, payload: GenerationRequest, public_url: str):
    task_dir = ROOT / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    try:
        update(task_id, status="PROCESSING", stage="DOWNLOADING_IMAGES", progress=8)
        urls = (payload.view_urls or [])[:4]
        if len(urls) < 3:
            urls = [payload.image_url]
        images = [download_image(url, task_dir / f"view_{index}.png") for index, url in enumerate(urls)]
        update(task_id, stage="RECONSTRUCTING_GEOMETRY", progress=25, views=urls)
        with GPU_LOCK:
            model = get_pipeline()
            if len(images) >= 3:
                outputs = model.run_multi_image(
                    images, seed=42, formats=["mesh", "gaussian"], mode="multidiffusion",
                    sparse_structure_sampler_params={"steps": 16, "cfg_strength": 7.5},
                    slat_sampler_params={"steps": 16, "cfg_strength": 3.0},
                )
                method = "TRELLIS_MULTIDIFFUSION"
            else:
                outputs = model.run(
                    images[0], seed=42, formats=["mesh", "gaussian"],
                    sparse_structure_sampler_params={"steps": 12, "cfg_strength": 7.5},
                    slat_sampler_params={"steps": 12, "cfg_strength": 3.0},
                )
                method = "TRELLIS_SINGLE_IMAGE"
            update(task_id, stage="BAKING_TEXTURE", progress=78)
            glb = postprocessing_utils.to_glb(
                outputs["gaussian"][0], outputs["mesh"][0], simplify=0.70, texture_size=2048
            )
            output = task_dir / "model.glb"
            glb.export(output)
            torch.cuda.empty_cache()
        model_url = f"{public_url}/v1/files/{task_id}/model.glb"
        update(task_id, status="COMPLETED", stage=method, progress=100, model_url=model_url)
    except Exception as exc:
        update(task_id, status="FAILED", stage="FAILED", error=str(exc)[:500])


@app.get("/health")
def health():
    return {"status": "ok", "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}


@app.post("/v1/product-to-3d", status_code=202)
def start_generation(
    payload: GenerationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    public_url = (
        f"{forwarded_proto}://{forwarded_host}"
        if forwarded_host
        else str(request.base_url).rstrip("/")
    )
    task_id = uuid.uuid4().hex
    TASKS[task_id] = {"task_id": task_id, "status": "QUEUED", "stage": "QUEUED", "progress": 0, "views": []}
    threading.Thread(target=generate, args=(task_id, payload, public_url), daemon=True).start()
    return TASKS[task_id]


@app.get("/v1/product-to-3d/{task_id}")
def generation_status(task_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    if task_id not in TASKS:
        raise HTTPException(404, "Generation task not found")
    return TASKS[task_id]


@app.get("/v1/files/{task_id}/model.glb")
def model_file(task_id: str):
    path = ROOT / task_id / "model.glb"
    if not path.is_file():
        raise HTTPException(404, "Model not found")
    return FileResponse(path, media_type="model/gltf-binary", filename=f"ashes-{task_id}.glb")
