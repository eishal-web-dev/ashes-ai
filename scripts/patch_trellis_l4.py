from pathlib import Path

path = Path("tools/trellis/modal_ashes_worker.py")
text = path.read_text()
original = text

text = text.replace('env["TORCH_CUDA_ARCH_LIST"] = "7.5"', 'env["TORCH_CUDA_ARCH_LIST"] = "8.9"')
text = text.replace('.run_function(_install_trellis_with_gpu, gpu="T4", timeout=60 * 60)', '.run_function(_install_trellis_with_gpu, gpu="L4", timeout=60 * 60)')
text = text.replace('    gpu="T4",\n    volumes={MODEL_ROOT: model_volume, CACHE_ROOT: cache_volume},', '    gpu="L4",\n    volumes={MODEL_ROOT: model_volume, CACHE_ROOT: cache_volume},')
text = text.replace('            "gpu": "T4",', '            "gpu": "L4",')

if text == original:
    print("L4 worker patch already applied or no matching T4 settings remain")
else:
    path.write_text(text)
    print("Patched TRELLIS worker for Modal L4 (24 GB VRAM, CUDA arch 8.9)")
