import ipaddress
import os
import socket
import threading
import uuid
from io import BytesIO
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
MAX_IMAGE_BYTES = int(os.getenv("ASHES_TRELLIS_MAX_IMAGE_BYTES", "12000000"))

app = FastAPI(title="Ashes TRELLIS Worker", version="1.1")
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


def request_public_url(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    return (
        f"{forwarded_proto}://{forwarded_host}"
        if forwarded_host
        else str(request.base_url).rstrip("/")
    )


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
    with requests.get(url, timeout=25, stream=True, headers={"User-Agent": "Ashes-TRELLIS/1.1"}) as response:
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("image/"):
            raise ValueError("URL did not return an image")
        size = 0
        with target.open("wb") as output:
            for chunk in response.iter_content(1024 * 256):
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds worker size limit")
                output.write(chunk)
    return Image.open(target).convert("RGB")


def open_uploaded_image(raw: bytes, target: Path) -> Image.Image:
    if not raw:
        raise ValueError("Empty image upload")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds worker size limit")
    image = Image.open(BytesIO(raw)).convert("RGB")
    image.save(target, format="PNG")
    return image


def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
        pipeline.cuda()
    return pipeline


def update(task_id: str, **values):
    TASKS[task_id].update(values)


def reconstruct(task_id: str, images: list[Image.Image], public_url: str, views: list[str] | None = None):
    update(task_id, status="PROCESSING", stage="RECONSTRUCTING_GEOMETRY", progress=25, views=views or [])
    with GPU_LOCK:
        model = get_pipeline()
        if len(images) >= 3:
            outputs = model.run_multi_image(
                images,
                seed=42,
                formats=["mesh", "gaussian"],
                mode="multidiffusion",
                sparse_structure_sampler_params={"steps": 16, "cfg_strength": 7.5},
                slat_sampler_params={"steps": 16, "cfg_strength": 3.0},
            )
            method = "TRELLIS_MULTIDIFFUSION"
        else:
            outputs = model.run(
                images[0],
                seed=42,
                formats=["mesh", "gaussian"],
                sparse_structure_sampler_params={"steps": 12, "cfg_strength": 7.5},
                slat_sampler_params={"steps": 12, "cfg_strength": 3.0},
            )
            method = "TRELLIS_SINGLE_IMAGE"

        update(task_id, stage="BAKING_TEXTURE", progress=78)
        glb = postprocessing_utils.to_glb(
            outputs["gaussian"][0],
            outputs["mesh"][0],
            simplify=0.70,
            texture_size=2048,
        )
        output = ROOT / task_id / "model.glb"
        glb.export(output)
        torch.cuda.empty_cache()

    model_url = f"{public_url}/v1/files/{task_id}/model.glb"
    update(task_id, status="COMPLETED", stage=method, progress=100, model_url=model_url)


def generate_from_urls(task_id: str, payload: GenerationRequest, public_url: str):
    task_dir = ROOT / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    try:
        update(task_id, status="PROCESSING", stage="DOWNLOADING_IMAGES", progress=8)
        urls = (payload.view_urls or [])[:4]
        if len(urls) < 3:
            urls = [payload.image_url]
        images = [download_image(url, task_dir / f"view_{index}.png") for index, url in enumerate(urls)]
        reconstruct(task_id, images, public_url, urls)
    except Exception as exc:
        update(task_id, status="FAILED", stage="FAILED", error=str(exc)[:500])


def generate_from_upload(task_id: str, raw: bytes, public_url: str):
    task_dir = ROOT / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    try:
        update(task_id, status="PROCESSING", stage="READING_IMAGE", progress=8)
        image = open_uploaded_image(raw, task_dir / "input.png")
        reconstruct(task_id, [image], public_url, [])
    except Exception as exc:
        update(task_id, status="FAILED", stage="FAILED", error=str(exc)[:500])


def create_task() -> str:
    task_id = uuid.uuid4().hex
    TASKS[task_id] = {
        "task_id": task_id,
        "status": "QUEUED",
        "stage": "QUEUED",
        "progress": 0,
        "views": [],
    }
    return task_id


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
    task_id = create_task()
    threading.Thread(
        target=generate_from_urls,
        args=(task_id, payload, request_public_url(request)),
        daemon=True,
    ).start()
    return TASKS[task_id]


@app.post("/v1/product-to-3d-file", status_code=202)
async def start_generation_from_file(
    request: Request,
    authorization: str | None = Header(default=None),
    x_product_name: str | None = Header(default=None),
):
    """Accept one product image directly from the Ashes API.

    This avoids requiring a temporary public image URL. The worker keeps the upload
    only for the lifetime of the generation task; the finished GLB is downloaded by
    Ashes and then persisted to S3/R2 by the main API.
    """
    authorize(authorization)
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("image/") and content_type != "application/octet-stream":
        raise HTTPException(415, "Body must be an image")
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Empty image upload")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds worker size limit")

    task_id = create_task()
    if x_product_name:
        TASKS[task_id]["product_name"] = x_product_name[:200]
    threading.Thread(
        target=generate_from_upload,
        args=(task_id, raw, request_public_url(request)),
        daemon=True,
    ).start()
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
