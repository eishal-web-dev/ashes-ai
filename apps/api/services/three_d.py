from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = DATA_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def _copy_existing_glb(source: Path, product_id: str) -> Optional[Path]:
    """Development escape hatch.

    If a matching GLB is dropped beside the upload as <product_id>.glb, copy it into
    the managed model directory so the rest of Ashes behaves exactly as it would
    with a generated asset.
    """
    candidate = source.with_name(f"{product_id}.glb")
    if not candidate.exists():
        return None
    target = MODEL_DIR / f"{product_id}.glb"
    shutil.copy2(candidate, target)
    return target


def _worker_headers(content_type: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    token = os.getenv("ASHES_TRELLIS_WORKER_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _poll_worker_task(task_id: str, product_id: str) -> Path:
    worker_url = os.environ["ASHES_TRELLIS_WORKER_URL"].rstrip("/")
    timeout_seconds = int(os.getenv("ASHES_3D_TIMEOUT", "900"))
    poll_seconds = max(1.0, float(os.getenv("ASHES_3D_POLL_SECONDS", "2")))
    request_timeout = min(60, max(10, int(os.getenv("ASHES_3D_HTTP_TIMEOUT", "30"))))
    deadline = time.monotonic() + timeout_seconds
    status_headers = _worker_headers()

    while time.monotonic() < deadline:
        status_response = requests.get(
            f"{worker_url}/v1/product-to-3d/{task_id}",
            headers=status_headers,
            timeout=request_timeout,
        )
        status_response.raise_for_status()
        task = status_response.json()
        status = str(task.get("status", "")).upper()

        if status == "COMPLETED":
            model_url = task.get("model_url")
            if not model_url:
                raise RuntimeError("TRELLIS worker completed without a model_url")
            output_path = MODEL_DIR / f"{product_id}.glb"
            with requests.get(model_url, headers=status_headers, stream=True, timeout=60) as model_response:
                model_response.raise_for_status()
                with output_path.open("wb") as output:
                    for chunk in model_response.iter_content(1024 * 1024):
                        if chunk:
                            output.write(chunk)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("TRELLIS worker returned an empty model")
            return output_path

        if status == "FAILED":
            detail = task.get("error") or task.get("stage") or "unknown worker failure"
            raise RuntimeError(f"TRELLIS generation failed: {detail}")

        time.sleep(poll_seconds)

    raise TimeoutError(f"TRELLIS generation timed out after {timeout_seconds} seconds")


def _remote_trellis_generate_file(product_id: str, image_path: Path) -> Path:
    """Generate through the worker by uploading one local image."""
    worker_url = os.environ["ASHES_TRELLIS_WORKER_URL"].rstrip("/")
    request_timeout = min(60, max(10, int(os.getenv("ASHES_3D_HTTP_TIMEOUT", "30"))))
    content_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    headers = _worker_headers(content_type)
    headers["X-Product-Name"] = product_id

    with image_path.open("rb") as source:
        response = requests.post(
            f"{worker_url}/v1/product-to-3d-file",
            data=source,
            headers=headers,
            timeout=request_timeout,
        )
    response.raise_for_status()
    task = response.json()
    task_id = task.get("task_id")
    if not task_id:
        raise RuntimeError("TRELLIS worker did not return a task_id")
    return _poll_worker_task(task_id, product_id)


def _remote_trellis_generate_urls(product_id: str, image_urls: list[str]) -> Path:
    """Generate from public product views, using multidiffusion when 3+ views exist."""
    worker_url = os.environ["ASHES_TRELLIS_WORKER_URL"].rstrip("/")
    request_timeout = min(60, max(10, int(os.getenv("ASHES_3D_HTTP_TIMEOUT", "30"))))
    clean_urls = list(dict.fromkeys(str(x).strip() for x in image_urls if str(x).strip()))[:4]
    if not clean_urls:
        raise RuntimeError("No product image URLs were provided for 3D generation")

    response = requests.post(
        f"{worker_url}/v1/product-to-3d",
        json={
            "image_url": clean_urls[0],
            "view_urls": clean_urls,
            "product_name": product_id,
        },
        headers=_worker_headers("application/json"),
        timeout=request_timeout,
    )
    response.raise_for_status()
    task = response.json()
    task_id = task.get("task_id")
    if not task_id:
        raise RuntimeError("TRELLIS worker did not return a task_id")
    return _poll_worker_task(task_id, product_id)


def _local_generate(product_id: str, image_path: Path) -> Optional[Path]:
    command = os.getenv("ASHES_3D_COMMAND", "").strip()
    if not command:
        return None

    output_path = MODEL_DIR / f"{product_id}.glb"
    args = shlex.split(command, posix=os.name != "nt") + [product_id, str(image_path), str(output_path)]
    subprocess.run(args, check=True, timeout=int(os.getenv("ASHES_3D_TIMEOUT", "900")))

    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path
    return None


def _download_first_image(product_id: str, image_urls: list[str]) -> Optional[Path]:
    clean_urls = [str(x).strip() for x in image_urls if str(x).strip()]
    if not clean_urls:
        return None
    target = DATA_DIR / f"{product_id}-source.jpg"
    response = requests.get(clean_urls[0], timeout=40, headers={"User-Agent": "AshesCatalogBot/1.0"})
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def generate_3d(
    product_id: str,
    image_path: Optional[Path] = None,
    image_urls: Optional[list[str]] = None,
) -> Optional[Path]:
    """Generate one commerce-ready GLB from local or imported product imagery.

    Provider order:
      1. Existing development GLB beside a local upload.
      2. Remote Ashes TRELLIS worker using product view URLs when available.
      3. Remote Ashes TRELLIS worker using a direct local image upload.
      4. Local ASHES_3D_COMMAND fallback for development.

    With 3 or more view URLs, the current TRELLIS worker automatically selects its
    multi-image multidiffusion path. One or two URLs fall back to single-image mode.
    The storefront never contacts the GPU worker; it only receives the completed GLB.
    """
    if image_path:
        copied = _copy_existing_glb(image_path, product_id)
        if copied:
            return copied

    worker_configured = bool(os.getenv("ASHES_TRELLIS_WORKER_URL", "").strip())
    clean_urls = list(dict.fromkeys(str(x).strip() for x in (image_urls or []) if str(x).strip()))

    if worker_configured:
        if clean_urls:
            return _remote_trellis_generate_urls(product_id, clean_urls)
        if image_path:
            return _remote_trellis_generate_file(product_id, image_path)

    local_source = image_path
    downloaded = False
    if local_source is None and clean_urls:
        local_source = _download_first_image(product_id, clean_urls)
        downloaded = local_source is not None

    try:
        return _local_generate(product_id, local_source) if local_source else None
    finally:
        if downloaded and local_source:
            try:
                local_source.unlink(missing_ok=True)
            except OSError:
                pass
