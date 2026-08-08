from apps.api.subscriptions import PLANS, public_plans


def test_plan_catalog_has_expected_tiers():
    assert [plan["key"] for plan in public_plans()] == ["free", "starter", "pro"]


def test_plan_limits_increase_by_tier():
    assert PLANS["free"]["product_limit"] < PLANS["starter"]["product_limit"] < PLANS["pro"]["product_limit"]
    assert PLANS["free"]["ai_generations_monthly"] < PLANS["starter"]["ai_generations_monthly"] < PLANS["pro"]["ai_generations_monthly"]
    assert PLANS["free"]["menu_imports_monthly"] < PLANS["starter"]["menu_imports_monthly"] < PLANS["pro"]["menu_imports_monthly"]


def test_free_plan_is_zero_price():
    assert PLANS["free"]["price_monthly_usd"] == 0
