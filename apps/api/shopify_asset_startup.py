from __future__ import annotations

import os
import threading
import time

from apps.api.mongo_main import app
from apps.api.shopify_asset_reconcile import reconcile_completed_shopify_assets
from apps.api.shopify_legacy_recovery import recover_first_legacy_shopify_asset


def _run() -> None:
    try:
        result = reconcile_completed_shopify_assets(limit=5)
        provider = os.getenv("ASHES_STORAGE_PROVIDER", "local").strip().lower()
        print(f"ASHES_SHOPIFY_RECONCILE provider={provider} migrated={result.get('migrated', 0)} errors={result.get('errors', [])}", flush=True)
    except Exception as exc:
        print(f"ASHES_SHOPIFY_RECONCILE_FAILED {str(exc)[:500]}", flush=True)

    for attempt in range(1, 7):
        try:
            recovered = recover_first_legacy_shopify_asset()
            print(f"ASHES_SHOPIFY_LEGACY_RECOVERY attempt={attempt} result={recovered}", flush=True)
            if recovered.get("recovered") or recovered.get("reason") in {"assets already exist", "usage already recorded"}:
                return
        except Exception as exc:
            print(f"ASHES_SHOPIFY_LEGACY_RECOVERY_FAILED attempt={attempt} error={str(exc)[:400]}", flush=True)
        time.sleep(20)


@app.on_event("startup")
def reconcile_shopify_assets_on_startup() -> None:
    threading.Thread(target=_run, daemon=True, name="ashes-shopify-asset-reconcile").start()
