from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path
from typing import Any

import requests

import apps.api.shopify_generation as generation


_original_persist = generation._persist_modal_glb


def _glb_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) < 20 or raw[:4] != b"glTF":
        raise RuntimeError("Generated file is not a valid GLB.")
    version, declared = struct.unpack_from("<II", raw, 4)
    if version != 2 or declared != len(raw):
        raise RuntimeError("Generated GLB header is invalid.")
    offset = 12
    while offset + 8 <= len(raw):
        chunk_len, chunk_type = struct.unpack_from("<II", raw, offset)
        offset += 8
        chunk = raw[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            return json.loads(chunk.decode("utf-8").rstrip("\x00 \t\r\n"))
    raise RuntimeError("Generated GLB has no JSON scene chunk.")


def _material_has_texture(material: dict[str, Any]) -> bool:
    pbr = material.get("pbrMetallicRoughness") or {}
    return any(
        isinstance(slot, dict) and "index" in slot
        for slot in (
            pbr.get("baseColorTexture"),
            pbr.get("metallicRoughnessTexture"),
            material.get("normalTexture"),
            material.get("occlusionTexture"),
            material.get("emissiveTexture"),
        )
    )


def validate_textured_glb(path: Path) -> dict[str, int]:
    scene = _glb_json(path)
    meshes = scene.get("meshes") or []
    materials = scene.get("materials") or []
    textures = scene.get("textures") or []
    images = scene.get("images") or []
    if not meshes:
        raise RuntimeError("Generated GLB has no mesh geometry.")
    textured_materials = sum(1 for material in materials if _material_has_texture(material))
    if not materials or not textures or not images or textured_materials < 1:
        raise RuntimeError(
            "Generated GLB has geometry but no baked color texture. Ashes rejected it so this generation is not charged."
        )
    return {
        "material_count": len(materials),
        "texture_count": len(textures),
        "image_count": len(images),
        "textured_material_count": textured_materials,
    }


def _validated_persist(task_id: str, model_url: str):
    job = generation.collection("shopify_generation_jobs").find_one(
        {"task_id": task_id, "shop": generation._shop()}
    ) or {}
    product_id = str(job.get("product_id") or "").strip()

    with tempfile.NamedTemporaryFile(prefix="ashes-quality-", suffix=".glb", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        try:
            with requests.get(
                model_url,
                headers=generation._headers(False),
                timeout=120,
                stream=True,
            ) as response:
                response.raise_for_status()
                size = 0
                with temp_path.open("wb") as output:
                    for chunk in response.iter_content(1024 * 512):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > 150 * 1024 * 1024:
                            raise RuntimeError("Generated GLB exceeds the Ashes quality-check limit.")
                        output.write(chunk)
        except requests.RequestException as exc:
            raise RuntimeError(f"Ashes could not quality-check the generated GLB: {str(exc)[:180]}") from exc

        quality = validate_textured_glb(temp_path)

        # Current persistence API only accepts task_id + model_url and derives
        # Shopify product identity from the saved generation job.
        stored = _original_persist(task_id, model_url)

        if product_id:
            try:
                generation.collection("shopify_3d_assets").update_one(
                    {"shop": generation._shop(), "product_id": product_id},
                    {"$set": {"quality": quality, "quality_status": "TEXTURED_VERIFIED"}},
                )
            except Exception:
                pass
        return stored
    finally:
        temp_path.unlink(missing_ok=True)


generation._persist_modal_glb = _validated_persist
