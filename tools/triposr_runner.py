from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(product_id: str, image_path: Path, output_glb: Path) -> None:
    """Generate a mesh with a local TripoSR checkout, then convert it to GLB.

    Expected environment:
      - TRIPOSR_HOME points to a cloned VAST-AI-Research/TripoSR repository
      - that environment can run TripoSR's run.py
      - trimesh is installed for GLB conversion

    Ashes intentionally keeps this as an external runner so CUDA/PyTorch/model
    dependencies stay isolated from the FastAPI process.
    """
    import os

    triposr_home = Path(os.getenv("TRIPOSR_HOME", "")).expanduser()
    if not triposr_home.exists():
        raise RuntimeError(
            "TRIPOSR_HOME is not configured. Clone TripoSR and set TRIPOSR_HOME to its folder."
        )

    run_script = triposr_home / "run.py"
    if not run_script.exists():
        raise RuntimeError(f"Could not find TripoSR run.py at {run_script}")

    image_path = image_path.resolve()
    output_glb = output_glb.resolve()
    output_glb.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"ashes-{product_id[:8]}-") as temp_dir:
        temp = Path(temp_dir)

        cmd = [
            sys.executable,
            str(run_script),
            str(image_path),
            "--output-dir",
            str(temp),
            "--bake-texture",
        ]
        subprocess.run(cmd, cwd=triposr_home, check=True)

        candidates = list(temp.rglob("*.obj")) + list(temp.rglob("*.glb")) + list(temp.rglob("*.ply"))
        if not candidates:
            raise RuntimeError("TripoSR completed but no mesh file was found in its output directory.")

        source = candidates[0]
        if source.suffix.lower() == ".glb":
            shutil.copy2(source, output_glb)
            return

        try:
            import trimesh
        except ImportError as exc:
            raise RuntimeError("Install trimesh to convert TripoSR output to GLB: pip install trimesh") from exc

        mesh = trimesh.load(source, force="scene")
        exported = mesh.export(file_type="glb")
        output_glb.write_bytes(exported)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ashes AI TripoSR image-to-GLB runner")
    parser.add_argument("product_id")
    parser.add_argument("image_path", type=Path)
    parser.add_argument("output_glb", type=Path)
    args = parser.parse_args()
    run(args.product_id, args.image_path, args.output_glb)


if __name__ == "__main__":
    main()
