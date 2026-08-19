from __future__ import annotations

import os
import threading

from apps.api.mongo_main import app
from apps.api.shopify_asset_reconcile import reconcile_completed_shopify_assets


def _run() -> None:
    try:
        result = reconcile_completed_shopify_assets(limit=5)
        provider = os.getenv("ASHES_STORAGE_PROVIDER", "local").strip().lower()
        print(f"ASHES_SHOPIFY_RECONCILE provider={provider} migrated={result.get('migrated', 0)} errors={result.get('errors', [])}", flush=True)
    except Exception as exc:
        # Never make API startup depend on a legacy migration.
        print(f"ASHES_SHOPIFY_RECONCILE_FAILED {str(exc)[:500]}", flush=True)


@app.on_event("startup")
def reconcile_shopify_assets_on_startup() -> None:
    threading.Thread(target=_run, daemon=True, name="ashes-shopify-asset-reconcile").start()
