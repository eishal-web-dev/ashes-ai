from pathlib import Path

from apps.api import storage_main
from apps.api.services import three_d


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


class _FakeResponse:
    def __init__(self, payload=None, chunks=None):
        self._payload = payload or {}
        self._chunks = chunks or []

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload

    def iter_content(self, _chunk_size):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_remote_trellis_worker_downloads_completed_glb(monkeypatch, tmp_path):
    image_path = tmp_path / "chair.jpg"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setattr(three_d, "MODEL_DIR", tmp_path)
    monkeypatch.setenv("ASHES_TRELLIS_WORKER_URL", "https://gpu.example")
    monkeypatch.setenv("ASHES_TRELLIS_WORKER_TOKEN", "secret")
    monkeypatch.setenv("ASHES_3D_POLL_SECONDS", "1")
    monkeypatch.setattr(three_d.time, "sleep", lambda *_: None)

    posted = {}
    statuses = iter([
        {"task_id": "job-1", "status": "QUEUED"},
        {"task_id": "job-1", "status": "COMPLETED", "model_url": "https://gpu.example/v1/files/job-1/model.glb"},
    ])

    def fake_post(url, data, headers, timeout):
        posted["url"] = url
        posted["headers"] = headers
        posted["body"] = data.read()
        return _FakeResponse({"task_id": "job-1", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None, stream=False):
        if url.endswith("model.glb"):
            return _FakeResponse(chunks=[b"gl", b"b-data"])
        return _FakeResponse(next(statuses))

    monkeypatch.setattr(three_d.requests, "post", fake_post)
    monkeypatch.setattr(three_d.requests, "get", fake_get)

    result = three_d.generate_3d("chair-1", image_path)

    assert result == tmp_path / "chair-1.glb"
    assert result.read_bytes() == b"glb-data"
    assert posted["url"] == "https://gpu.example/v1/product-to-3d-file"
    assert posted["headers"]["Authorization"] == "Bearer secret"
    assert posted["body"] == b"fake-image"
