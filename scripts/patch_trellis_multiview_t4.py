from pathlib import Path

# This script is intentionally idempotent so the CI patch can run safely more than once.
path = Path('tools/trellis/modal_ashes_worker.py')
text = path.read_text(encoding='utf-8')
original = text

text = text.replace('DEFAULT_STEPS = 24', 'DEFAULT_STEPS = 16')
text = text.replace('images[:4], seed=42, formats=["mesh", "gaussian"], mode="multidiffusion",', 'images[:3], seed=42, formats=["mesh", "gaussian"], mode="multidiffusion",')
text = text.replace('texture_size=2048,', 'texture_size=1024 if len(images) >= 3 else 2048,')

# Free GPU memory before expensive export/validation.
needle = '    glb_scene = postprocessing_utils.to_glb(\n'
if needle in text and 'torch.cuda.empty_cache()\n    glb_scene' not in text:
    text = text.replace(needle, '    torch.cuda.empty_cache()\n    glb_scene = postprocessing_utils.to_glb(\n', 1)

if text == original:
    print('No worker changes needed')
else:
    path.write_text(text, encoding='utf-8')
    print('Patched TRELLIS multi-view for T4-safe generation')
