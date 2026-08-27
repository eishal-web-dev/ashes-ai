from __future__ import annotations

from typing import Any

import apps.api.shopify_generation as generation


_original_finish_job = generation._finish_job


def _finish_job_with_model_url(task_id: str, data: dict[str, Any]) -> None:
    model_url = data.get("model_url") or (data.get("output") or {}).get("glb_url")
    if model_url:
        generation.collection("shopify_generation_jobs").update_one(
            {"task_id": task_id, "shop": generation._shop()},
            {"$set": {"model_url": str(model_url), "updated_at": generation.now_iso()}},
        )
    _original_finish_job(task_id, data)


generation._finish_job = _finish_job_with_model_url
