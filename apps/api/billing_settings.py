from __future__ import annotations

from typing import Any

from apps.api.mongo_db import clean_doc, collection
from apps.api.subscriptions import PLANS

DEFAULT_CURRENCY = "pkr"
DEFAULT_MONTHLY_PRICE = 1400.0


def _defaults() -> dict[str, Any]:
    return {
        "currency": DEFAULT_CURRENCY,
        "plans": {
            "free": {"enabled": True, "price_monthly": 0},
            "starter": {"enabled": True, "price_monthly": DEFAULT_MONTHLY_PRICE},
            "pro": {"enabled": False, "price_monthly": DEFAULT_MONTHLY_PRICE},
        },
    }


def get_billing_settings() -> dict[str, Any]:
    doc = clean_doc(collection("billing_settings").find_one({"key": "global"}))
    base = _defaults()
    if not doc: return base
    base["currency"] = str(doc.get("currency") or DEFAULT_CURRENCY).lower()
    saved_plans = doc.get("plans") or {}
    for key in ("free", "starter", "pro"):
        if key in saved_plans: base["plans"][key].update(saved_plans[key])
    return base


def update_billing_settings(currency: str, plans: dict[str, Any]) -> dict[str, Any]:
    currency_key = (currency or DEFAULT_CURRENCY).strip().lower()
    if len(currency_key) != 3 or not currency_key.isalpha(): raise ValueError("Currency must be a 3-letter ISO currency code")
    current = get_billing_settings(); normalized = current["plans"]
    for key in ("starter", "pro"):
        incoming = plans.get(key) or {}
        if "price_monthly" in incoming:
            value = float(incoming["price_monthly"])
            if value < 0: raise ValueError("Plan price cannot be negative")
            normalized[key]["price_monthly"] = round(value, 2)
        if "enabled" in incoming: normalized[key]["enabled"] = bool(incoming["enabled"])
    # Ashes has one public paid membership. Legacy pro is intentionally hidden.
    normalized["pro"]["enabled"] = False
    collection("billing_settings").update_one({"key": "global"},{"$set": {"key": "global", "currency": currency_key, "plans": normalized}},upsert=True)
    return get_billing_settings()


def public_plan_catalog() -> list[dict[str, Any]]:
    settings = get_billing_settings(); rows: list[dict[str, Any]] = []
    for key in ("free", "starter"):
        base = dict(PLANS[key]); configured = settings["plans"][key]
        base["enabled"] = bool(configured.get("enabled", True)); base["currency"] = settings["currency"]
        base["price_monthly"] = float(configured.get("price_monthly", 0)); rows.append(base)
    return rows


def checkout_price(plan_key: str) -> tuple[str, int]:
    key = "starter" if plan_key in {"starter", "pro"} else plan_key
    settings = get_billing_settings(); plan = settings["plans"].get(key)
    if not plan or not plan.get("enabled", True): raise ValueError("This plan is not available")
    amount_minor = int(round(float(plan.get("price_monthly", 0)) * 100))
    if amount_minor <= 0: raise ValueError("Paid plan price must be greater than zero")
    return settings["currency"], amount_minor
