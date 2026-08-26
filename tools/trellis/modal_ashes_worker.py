import ipaddress
import os
import shutil
import socket
import subprocess
import sys
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import modal

APP_NAME = "ashes-trellis-worker"
TRELLIS_COMMIT = "442aa1e1afb9014e80681d3bf604e8d728a86ee7"
TRELLIS_ROOT = "/opt/TRELLIS"
MODEL_ROOT = "/models"
CACHE_ROOT = "/cache"
MAX_IMAGE_BYTES = 12_000_000
DEFAULT_STEPS = 16


def _install_trellis_with_gpu() -> None:
    """Build TRELLIS and its CUDA extensions inside a GPU-aware Modal image."""
    import os
    import subprocess

    env = os.environ.copy()
    env["TORCH_CUDA_ARCH_LIST"] = "7.5"
    env["FORCE_CUDA"] = "1"
    env["MAX_JOBS"] = "4"
    env["CC"] = "gcc"
    env["CXX"] = "g++"

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euxo pipefail; "
                "export CC=gcc CXX=g++; command -v gcc; command -v g++; "
                "rm -rf /opt/TRELLIS /tmp/extensions; "
                "git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git /opt/TRELLIS; "
                f"cd /opt/TRELLIS; git checkout {TRELLIS_COMMIT}; "
                "git submodule update --init --recursive; "
                "source setup.sh --basic --spconv; "
                "python -m pip install --no-cache-dir xformers==0.0.27.post2 --index-url https://download.pytorch.org/whl/cu121; "
                "python -m pip install --no-cache-dir kaolin==0.16.0 -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.4.0_cu121.html; "
                "mkdir -p /tmp/extensions; "
                "git clone https://github.com/NVlabs/nvdiffrast.git /tmp/extensions/nvdiffrast; "
                "python -m pip install --no-cache-dir --no-build-isolation /tmp/extensions/nvdiffrast; "
                "git clone --recurse-submodules https://github.com/JeffreyXiang/diffoctreerast.git /tmp/extensions/diffoctreerast; "
                "python -m pip install --no-cache-dir --no-build-isolation /tmp/extensions/diffoctreerast; "
                "git clone --recurse-submodules https://github.com/autonomousvision/mip-splatting.git /tmp/extensions/mip-splatting; "
                "python -m pip install --no-cache-dir --no-build-isolation /tmp/extensions/mip-splatting/submodules/diff-gaussian-rasterization; "
                "python -c 'import kaolin, xformers, nvdiffrast.torch, diffoctreerast, diff_gaussian_rasterization; print(\"TRELLIS native deps ready\", kaolin.__version__, xformers.__version__)'"
            ),
        ],
        check=True,
        env=env,
    )


base_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-devel-ubuntu22.04",
        add_python="3.10",
    )
    .entrypoint([])
    .apt_install(
        "git",
        "build-essential",
        "cmake",
        "ninja-build",
        "ffmpeg",
        "libgl1",
        "libglib2.0-0",
        "libegl1",
        "libx11-6",
        "libxext6",
        "libsm6",
    )
    .run_commands(
        "python -m pip install --upgrade pip setuptools wheel",
        "python -m pip install torch==2.4.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu121",
    )
)

trellis_image = (
    base_image
    .run_function(_install_trellis_with_gpu, gpu="T4", timeout=60 * 60)
    .run_commands(
        "python -m pip install --no-cache-dir --force-reinstall numpy==1.26.4 pillow==10.4.0 opencv-python-headless==4.10.0.84",
        "python -m pip install --no-cache-dir rembg==2.0.60 onnxruntime==1.20.1 trimesh==4.5.3 xatlas==0.0.9 pygltflib scipy rtree requests fastapi[standard] huggingface_hub hf_transfer",
    )
    .env(
        {
            "PYTHONPATH": TRELLIS_ROOT,
            "ATTN_BACKEND": "xformers",
            "SPARSE_ATTN": "xformers",
            "SPCONV_ALGO": "native",
            "MPLBACKEND": "Agg",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            "HF_HOME": f"{CACHE_ROOT}/huggingface",
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "TORCH_HOME": f"{CACHE_ROOT}/torch",
        }
    )
)

web_image = modal.Image.debian_slim(python_version="3.10").pip_install(
    "fastapi[standard]",
    "pydantic",
)

app = modal.App(APP_NAME)
model_volume = modal.Volume.from_name("ashes-trellis-models", create_if_missing=True)
cache_volume = modal.Volume.from_name("ashes-trellis-cache", create_if_missing=True)

_deploy_worker_token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
web_secrets = (
    [modal.Secret.from_dict({"ASHES_TRELLIS_WORKER_TOKEN": _deploy_worker_token})]
    if _deploy_worker_token
    else []
)

_PIPELINE = None


def _public_https(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only public HTTPS product images are accepted")
    for info in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("Private-network image URLs are not accepted")
    return value


def _download_image(url: str, target: Path):
    import requests
    from PIL import Image

    safe_url = _public_https(url)
    with requests.get(safe_url, timeout=30, stream=True, headers={"User-Agent": "Ashes-TRELLIS-Modal/1.0"}) as response:
        response.raise_for_status()
        ctype = response.headers.get("content-type", "")
        if not ctype.startswith("image/"):
            raise ValueError("Product URL did not return an image")
        size = 0
        with target.open("wb") as output:
            for chunk in response.iter_content(1024 * 256):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise ValueError("Product image exceeds the 12 MB worker limit")
                output.write(chunk)
    return Image.open(target).convert("RGB")


def _open_uploaded_image(raw: bytes, target: Path):
    from PIL import Image

    if not raw:
        raise ValueError("Empty product image")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Product image exceeds the 12 MB worker limit")
    image = Image.open(BytesIO(raw)).convert("RGB")
    image.save(target, format="PNG")
    return image


def _get_pipeline():
    global _PIPELINE
    if _PIPELINE is None:
        sys.path.insert(0, TRELLIS_ROOT)
        from trellis.pipelines import TrellisImageTo3DPipeline

        _PIPELINE = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
        _PIPELINE.cuda()
        try:
            cache_volume.commit()
        except Exception:
            pass
    return _PIPELINE


def _validate_glb(output_path: Path) -> dict:
    """Reject corrupt or empty GLBs before they are exposed as completed jobs."""
    import numpy as np
    import trimesh

    raw = output_path.read_bytes()
    if len(raw) < 20:
        raise RuntimeError("TRELLIS exported a truncated GLB")
    if raw[:4] != b"glTF":
        raise RuntimeError("TRELLIS export is not a GLB binary")

    version = int.from_bytes(raw[4:8], "little")
    declared_length = int.from_bytes(raw[8:12], "little")
    if version != 2:
        raise RuntimeError(f"Unsupported GLB version {version}")
    if declared_length != len(raw):
        raise RuntimeError(f"GLB length mismatch: header={declared_length}, file={len(raw)}")

    try:
        loaded = trimesh.load(output_path, file_type="glb", force="scene", process=False)
    except Exception as exc:
        raise RuntimeError(f"GLB validation failed to reopen export: {exc}") from exc

    geometries = list(getattr(loaded, "geometry", {}).values())
    if not geometries:
        raise RuntimeError("TRELLIS GLB contains no mesh geometry")

    vertex_count = sum(len(getattr(mesh, "vertices", [])) for mesh in geometries)
    face_count = sum(len(getattr(mesh, "faces", [])) for mesh in geometries)
    if vertex_count < 100 or face_count < 50:
        raise RuntimeError(f"TRELLIS GLB geometry is too small: {vertex_count} vertices, {face_count} faces")

    bounds = getattr(loaded, "bounds", None)
    if bounds is None or np.asarray(bounds).shape != (2, 3) or not np.isfinite(bounds).all():
        raise RuntimeError("TRELLIS GLB has invalid scene bounds")
    extents = np.asarray(bounds[1]) - np.asarray(bounds[0])
    if np.max(extents) <= 1e-6:
        raise RuntimeError("TRELLIS GLB geometry has zero-sized bounds")

    return {
        "size_bytes": len(raw),
        "mesh_count": len(geometries),
        "vertex_count": int(vertex_count),
        "face_count": int(face_count),
    }


def _run_reconstruction(images: list, output_path: Path) -> dict:
    import torch
    from trellis.utils import postprocessing_utils

    pipeline = _get_pipeline()
    steps = max(12, min(32, int(os.getenv("ASHES_TRELLIS_STEPS", str(DEFAULT_STEPS)))))
    if len(images) >= 3:
        outputs = pipeline.run_multi_image(
            images[:3], seed=42, formats=["mesh", "gaussian"], mode="multidiffusion",
            sparse_structure_sampler_params={"steps": steps, "cfg_strength": 7.5},
            slat_sampler_params={"steps": steps, "cfg_strength": 3.0},
        )
        mode = "TRELLIS_MULTIDIFFUSION"
    else:
        outputs = pipeline.run(
            images[0], seed=42, formats=["mesh", "gaussian"],
            sparse_structure_sampler_params={"steps": steps, "cfg_strength": 7.5},
            slat_sampler_params={"steps": steps, "cfg_strength": 3.0},
        )
        mode = "TRELLIS_SINGLE_IMAGE"

    torch.cuda.empty_cache()
    glb_scene = postprocessing_utils.to_glb(
        outputs["gaussian"][0],
        outputs["mesh"][0],
        simplify=0.70,
        texture_size=1024 if len(images) >= 3 else 2048,
    )
    binary = glb_scene.export(file_type="glb")
    if not isinstance(binary, (bytes, bytearray)):
        raise RuntimeError("TRELLIS did not return binary GLB bytes")
    output_path.write_bytes(bytes(binary))

    validation = _validate_glb(output_path)
    torch.cuda.empty_cache()
    return {"mode": mode, "views": len(images), "steps": steps, **validation}


@app.function(
    image=trellis_image,
    gpu="T4",
    volumes={MODEL_ROOT: model_volume, CACHE_ROOT: cache_volume},
    timeout=60 * 60,
    memory=32768,
    min_containers=0,
    max_containers=1,
    scaledown_window=120,
)
def generate_task(payload: dict, raw_image: bytes | None = None) -> dict:
    work = Path("/tmp/ashes") / uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=True)
    model_id = uuid.uuid4().hex
    output_path = Path(MODEL_ROOT) / f"{model_id}.glb"
    try:
        if raw_image is not None:
            images = [_open_uploaded_image(raw_image, work / "input.png")]
        else:
            image_url = str(payload.get("image_url") or "").strip()
            view_urls = [str(x).strip() for x in (payload.get("view_urls") or []) if str(x).strip()]
            urls = list(dict.fromkeys(view_urls))[:4]
            if len(urls) < 3:
                if not image_url:
                    raise ValueError("image_url is required when fewer than three views are supplied")
                urls = [image_url]
            images = [_download_image(url, work / f"view_{index}.img") for index, url in enumerate(urls, start=1)]

        result = _run_reconstruction(images, output_path)
        model_volume.commit()
        return {
            "model_id": model_id,
            "product_name": str(payload.get("product_name") or "Product")[:200],
            **result,
        }
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.function(
    image=web_image,
    volumes={MODEL_ROOT: model_volume},
    secrets=web_secrets,
    timeout=300,
    min_containers=0,
    max_containers=1,
    scaledown_window=60,
)
@modal.asgi_app()
def web():
    import re
    import fastapi
    from fastapi import Header, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from pydantic import BaseModel

    api = fastapi.FastAPI(title="Ashes Modal TRELLIS Worker", version="1.1")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Length", "Content-Range", "Accept-Ranges"],
    )

    class GenerationRequest(BaseModel):
        image_url: str
        product_name: str = "Product"
        view_urls: list[str] | None = None
        generate_views: dict | None = None
        reconstruction: dict | None = None

    def authorize(authorization: str | None) -> None:
        token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
        if token and authorization != f"Bearer {token}":
            raise HTTPException(401, "Invalid worker token")

    def base_url(request: Request) -> str:
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
        return str(request.base_url).rstrip("/")

    @api.get("/health")
    def health():
        return {
            "status": "ok",
            "provider": "modal",
            "gpu": "T4",
            "generation": "scale-to-zero",
            "trellis_commit": TRELLIS_COMMIT,
            "glb_validation": "enabled",
        }

    @api.post("/v1/product-to-3d", status_code=202)
    def start_from_urls(payload: GenerationRequest, authorization: str | None = Header(default=None)):
        authorize(authorization)
        call = generate_task.spawn(payload.model_dump(), None)
        return {"task_id": call.object_id, "status": "QUEUED", "stage": "QUEUED", "progress": 0}

    @api.post("/v1/product-to-3d-file", status_code=202)
    async def start_from_file(request: Request, authorization: str | None = Header(default=None), x_product_name: str | None = Header(default=None)):
        authorize(authorization)
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("image/") and content_type != "application/octet-stream":
            raise HTTPException(415, "Body must be an image")
        raw = await request.body()
        if not raw:
            raise HTTPException(400, "Empty image upload")
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image exceeds the 12 MB worker limit")
        call = generate_task.spawn({"product_name": (x_product_name or "Product")[:200]}, raw)
        return {"task_id": call.object_id, "status": "QUEUED", "stage": "QUEUED", "progress": 0}

    @api.get("/v1/product-to-3d/{task_id}")
    def generation_status(task_id: str, request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        try:
            call = modal.FunctionCall.from_id(task_id)
            try:
                result = call.get(timeout=0)
            except TimeoutError:
                return {"task_id": task_id, "status": "PROCESSING", "stage": "RECONSTRUCTING_3D", "progress": 50}
        except Exception as exc:
            return {"task_id": task_id, "status": "FAILED", "stage": "FAILED", "progress": 100, "error": str(exc)[:500]}

        return {
            "task_id": task_id,
            "status": "COMPLETED",
            "stage": result.get("mode", "TRELLIS"),
            "progress": 100,
            "views": result.get("views", 1),
            "steps": result.get("steps"),
            "size_bytes": result.get("size_bytes"),
            "mesh_count": result.get("mesh_count"),
            "vertex_count": result.get("vertex_count"),
            "face_count": result.get("face_count"),
            "model_url": f"{base_url(request)}/v1/files/{result['model_id']}/model.glb",
        }

    @api.get("/v1/files/{model_id}/model.glb")
    def model_file(model_id: str, authorization: str | None = Header(default=None)):
        authorize(authorization)
        if not re.fullmatch(r"[0-9a-f]{32}", model_id):
            raise HTTPException(404, "Model not found")
        model_volume.reload()
        path = Path(MODEL_ROOT) / f"{model_id}.glb"
        if not path.is_file():
            raise HTTPException(404, "Model not found")

        raw = path.read_bytes()
        if len(raw) < 20 or raw[:4] != b"glTF" or int.from_bytes(raw[8:12], "little") != len(raw):
            raise HTTPException(500, "Stored GLB failed integrity validation")

        return FileResponse(
            path,
            media_type="model/gltf-binary",
            headers={
                "Content-Disposition": f'inline; filename="ashes-{model_id}.glb"',
                "Cache-Control": "public, max-age=31536000, immutable",
                "Access-Control-Allow-Origin": "*",
            },
        )

    return api
