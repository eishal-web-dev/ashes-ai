from __future__ import annotations

from contextvars import ContextVar

_current_shop: ContextVar[str | None] = ContextVar("ashes_shopify_current_shop", default=None)
_current_id_token: ContextVar[str | None] = ContextVar("ashes_shopify_current_id_token", default=None)


def normalize_shop(value: str | None) -> str | None:
    shop = (value or "").strip().lower()
    if shop.startswith("https://"):
        shop = shop[8:]
    elif shop.startswith("http://"):
        shop = shop[7:]
    shop = shop.split("/", 1)[0]
    if not shop.endswith(".myshopify.com"):
        return None
    label = shop[: -len(".myshopify.com")]
    if not label or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in label):
        return None
    return shop


def set_shop(shop: str | None):
    return _current_shop.set(normalize_shop(shop))


def reset_shop(token) -> None:
    _current_shop.reset(token)


def current_shop() -> str | None:
    return _current_shop.get()


def set_id_token(token: str | None):
    return _current_id_token.set(token or None)


def reset_id_token(token) -> None:
    _current_id_token.reset(token)


def current_id_token() -> str | None:
    return _current_id_token.get()
