from pathlib import Path

from apps.api import storage_main


def test_storage_generation_persists_glb_and_marks_ready(monkeypatch, tmp_path):
    image_path = tmp_path / "input.jpg"
    image_path.write_bytes(b"image")
    model_path = tmp_path / "product.glb"
    model_path.write_bytes(b"glb")

    updates = []

    monkeypatch.setattr(storage_main, "generate_3d", lambda product_id, path: model_path)
    monkeypatch.setattr(
        storage_main,
        "store_media",
        lambda api_base, source, key, content_type=None: f"stored/{key}",
    )
    monkeypatch.setattr(
        storage_main,
        "mongo_get_product",
        lambda product_id: {"id": product_id, "business_id": "biz-1", "model_path": None},
    )
    monkeypatch.setattr(
        storage_main,
        "mongo_update_product",
        lambda product_id, business_id, values: updates.append(values) or {"id": product_id, **values},
    )
    monkeypatch.setattr(storage_main, "delete_media", lambda *args, **kwargs: None)

    storage_main._run_storage_generation_job("product-1", "biz-1", image_path)

    assert updates[0]["status"] == "processing"
    assert updates[-1]["status"] == "ready"
    assert updates[-1]["model_path"] == "stored/models/biz-1/product-1.glb"
    assert not image_path.exists()


def test_storage_generation_marks_failed_and_cleans_temp(monkeypatch, tmp_path):
    image_path = tmp_path / "input.jpg"
    image_path.write_bytes(b"image")
    updates = []

    def fail(*args, **kwargs):
        raise RuntimeError("generator exploded")

    monkeypatch.setattr(storage_main, "generate_3d", fail)
    monkeypatch.setattr(
        storage_main,
        "mongo_update_product",
        lambda product_id, business_id, values: updates.append(values) or {"id": product_id, **values},
    )

    storage_main._run_storage_generation_job("product-2", "biz-1", image_path)

    assert updates[0]["status"] == "processing"
    assert updates[-1]["status"] == "failed"
    assert "generator exploded" in updates[-1]["error_message"]
    assert not image_path.exists()
