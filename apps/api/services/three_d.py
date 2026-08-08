from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

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


def generate_3d(product_id: str, image_path: Path) -> Optional[Path]:
    """Generate a GLB for one product image.

    The worker is provider-agnostic. Set ASHES_3D_COMMAND to a local executable or
    wrapper script that accepts three arguments: product_id, input_image, output_glb.

    Example:
      ASHES_3D_COMMAND="python tools/triposr_runner.py"

    Ashes will run:
      python tools/triposr_runner.py <product_id> <image_path> <output_path>

    The runner can use TripoSR, Stable Fast 3D, Hunyuan3D, or another licensed
    generator. Keeping the model runtime outside the web API prevents GPU-specific
    dependencies from making the core API fragile.
    """
    copied = _copy_existing_glb(image_path, product_id)
    if copied:
        return copied

    command = os.getenv("ASHES_3D_COMMAND", "").strip()
    if not command:
        return None

    output_path = MODEL_DIR / f"{product_id}.glb"
    args = command.split() + [product_id, str(image_path), str(output_path)]
    subprocess.run(args, check=True, timeout=int(os.getenv("ASHES_3D_TIMEOUT", "900")))

    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path
    return None
