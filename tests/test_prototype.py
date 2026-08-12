from fastapi import HTTPException

from apps.api import prototype


def test_scan_returns_clean_read_only_catalog(monkeypatch):
    monkeypatch.setattr(prototype, "_safe_public_url", lambda url: "https://www.example.com/store")
    monkeypatch.setattr(
        prototype,
        "_crawl",
        lambda url, pages: [{
            "name": "  Studio Chair  ",
            "description": "A product description",
            "image_url": "https://cdn.example.com/chair.jpg",
            "price": 249,
            "currency": "USD",
            "source_url": "https://example.com/chair",
        }],
    )

    result = prototype.scan_prototype_catalog(
        prototype.PrototypeScanPayload(url="https://example.com/store", max_pages=3)
    )

    assert result["mode"] == "live"
    assert result["merchant"] == "example.com"
    assert result["found"] == 1
    assert result["products"][0]["name"] == "Studio Chair"
    assert result["products"][0]["readiness"] == "image-ready"
    assert "saved" in result["notice"].lower()


def test_scan_rejects_empty_catalog(monkeypatch):
    monkeypatch.setattr(prototype, "_safe_public_url", lambda url: "https://example.com")
    monkeypatch.setattr(prototype, "_crawl", lambda url, pages: [])

    try:
        prototype.scan_prototype_catalog(
            prototype.PrototypeScanPayload(url="https://example.com")
        )
    except HTTPException as error:
        assert error.status_code == 422
    else:
        raise AssertionError("An empty catalog should be rejected")


def test_qr_endpoint_returns_svg():
    response = prototype.create_prototype_qr(
        prototype.PrototypeQrPayload(url="https://ashes.example/prototype?preview=1")
    )

    assert response.media_type == "image/svg+xml"
    assert b"<svg" in response.body
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_qr_endpoint_rejects_non_web_destination():
    try:
        prototype.create_prototype_qr(
            prototype.PrototypeQrPayload(url="javascript:alert(1)")
        )
    except HTTPException as error:
        assert error.status_code == 422
    else:
        raise AssertionError("A non-http QR destination should be rejected")
