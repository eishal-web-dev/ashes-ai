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


def _remote_trellis_generate(product_id: str, image_path: Path) -> Path:
    """Generate through an Ashes TRELLIS HTTP worker and download the resulting GLB.

    The worker is intentionally treated as disposable compute: the API uploads one
    image, polls the task, downloads the generated GLB, and the normal Ashes storage
    layer persists that file to S3/R2 afterwards. This keeps the storefront fully
    independent from the GPU worker once generation is complete.
    """
    worker_url = os.environ["ASHES_TRELLIS_WORKER_URL"].rstrip("/")
    timeout_seconds = int(os.getenv("ASHES_3D_TIMEOUT", "900"))
    poll_seconds = max(1.0, float(os.getenv("ASHES_3D_POLL_SECONDS", "2")))
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


def generate_3d(product_id: str, image_path: Path) -> Optional[Path]:
    """Generate one commerce-ready GLB from a product image.

    Provider order:
      1. Existing development GLB beside the upload.
      2. Remote Ashes TRELLIS worker when ASHES_TRELLIS_WORKER_URL is configured.
      3. Local ASHES_3D_COMMAND fallback for development.

    The returned local GLB is persisted by the API/storage layer. Storefront viewers
    never contact the GPU worker; they load the permanently stored asset instead.
    """
    copied = _copy_existing_glb(image_path, product_id)
    if copied:
        return copied

    if os.getenv("ASHES_TRELLIS_WORKER_URL", "").strip():
        return _remote_trellis_generate(product_id, image_path)

    return _local_generate(product_id, image_path)
