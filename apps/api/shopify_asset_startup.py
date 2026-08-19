from __future__ import annotations

import threading

from apps.api.mongo_main import app
from apps.api.shopify_asset_reconcile import reconcile_completed_shopify_assets


def _run() -> None:
    try:
        reconcile_completed_shopify_assets(limit=5)
    except Exception:
        # Never make API startup depend on a legacy migration.
        pass


@app.on_event("startup")
def reconcile_shopify_assets_on_startup() -> None:
    threading.Thread(target=_run, daemon=True, name="ashes-shopify-asset-reconcile").start()
