from apps.api.subscriptions import PLANS, public_plans


def test_public_catalog_matches_current_single_membership_model():
    assert [plan["key"] for plan in public_plans()] == ["free", "starter"]
    assert PLANS["free"]["name"] == "30-Day Trial"
    assert PLANS["starter"]["name"] == "Ashes"


def test_paid_membership_expands_trial_capacity():
    assert PLANS["free"]["product_limit"] < PLANS["starter"]["product_limit"]
    assert PLANS["free"]["ai_generations_monthly"] < PLANS["starter"]["ai_generations_monthly"]
    assert PLANS["free"]["menu_imports_monthly"] < PLANS["starter"]["menu_imports_monthly"]


def test_legacy_pro_key_stays_compatible_but_is_not_public():
    assert PLANS["pro"]["price_monthly_usd"] == PLANS["starter"]["price_monthly_usd"]
    assert "pro" not in [plan["key"] for plan in public_plans()]


def test_trial_is_zero_price():
    assert PLANS["free"]["price_monthly_usd"] == 0
