from __future__ import annotations

import mimetypes
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from apps.api.admin import require_admin
from apps.api.billing_settings import public_plan_catalog
from apps.api.media_storage import media_url, store_media
from apps.api.mongo_db import clean_doc, clean_docs, collection
from apps.api.mongo_main import API_BASE_URL, app, auth_user, owned_business
from apps.api.subscriptions import set_plan


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _method_defaults() -> dict[str, Any]:
    return {
        "easypaisa": {"enabled": False, "account_title": "", "account_number": "", "instructions": "Send payment, then upload the receipt screenshot."},
        "jazzcash": {"enabled": False, "account_title": "", "account_number": "", "instructions": "Send payment, then upload the receipt screenshot."},
    }


def get_manual_payment_settings() -> dict[str, Any]:
    doc = clean_doc(collection("manual_payment_settings").find_one({"key": "global"})) or {}
    methods = _method_defaults()
    saved = doc.get("methods") or {}
    for key in methods:
        if key in saved:
            methods[key].update(saved[key])
    return {"methods": methods}


def update_manual_payment_settings(methods: dict[str, Any]) -> dict[str, Any]:
    current = get_manual_payment_settings()["methods"]
    for key in ("easypaisa", "jazzcash"):
        incoming = methods.get(key) or {}
        for field in ("account_title", "account_number", "instructions"):
            if field in incoming:
                current[key][field] = str(incoming[field] or "").strip()
        if "enabled" in incoming:
            current[key]["enabled"] = bool(incoming["enabled"])
    collection("manual_payment_settings").update_one({"key": "global"}, {"$set": {"key": "global", "methods": current}}, upsert=True)
    return get_manual_payment_settings()


def _plan_price(plan_key: str) -> tuple[str, float]:
    for plan in public_plan_catalog():
        if plan.get("key") == plan_key:
            if plan.get("enabled") is False:
                raise ValueError("This plan is not available")
            return str(plan.get("currency") or "usd").upper(), float(plan.get("price_monthly") or 0)
    raise ValueError("Unknown plan")


class ManualMethodPayload(BaseModel):
    enabled: bool | None = None
    account_title: str | None = None
    account_number: str | None = None
    instructions: str | None = None


class ManualSettingsPayload(BaseModel):
    easypaisa: ManualMethodPayload
    jazzcash: ManualMethodPayload


class ManualReviewPayload(BaseModel):
    action: str
    note: str | None = None


@app.get("/api/billing/manual-methods")
def public_manual_methods():
    settings = get_manual_payment_settings()["methods"]
    return {"methods": {key: value for key, value in settings.items() if value.get("enabled")}}


@app.post("/api/businesses/{business_slug}/billing/manual-proof")
async def submit_manual_payment_proof(
    business_slug: str,
    plan: str = Form(...),
    method: str = Form(...),
    transaction_reference: str = Form(""),
    note: str = Form(""),
    receipt: UploadFile = File(...),
    user: dict = Depends(auth_user),
):
    business = owned_business(user["id"], business_slug)
    plan_key = plan.strip().lower()
    method_key = method.strip().lower()
    if plan_key not in {"starter", "pro"}:
        raise HTTPException(status_code=400, detail="Choose Starter or Pro")

    methods = get_manual_payment_settings()["methods"]
    if method_key not in methods or not methods[method_key].get("enabled"):
        raise HTTPException(status_code=400, detail="Payment method is not available")
    if not receipt.content_type or not receipt.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Receipt must be an image screenshot")

    try:
        currency, amount = _plan_price(plan_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ext = Path(receipt.filename or "receipt.jpg").suffix.lower() or ".jpg"
    proof_id = str(uuid.uuid4())
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    temp_path = Path(handle.name)
    handle.close()
    try:
        data = await receipt.read()
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Receipt image must be 8 MB or smaller")
        temp_path.write_bytes(data)
        content_type = receipt.content_type or mimetypes.guess_type(temp_path.name)[0] or "image/jpeg"
        storage_key = store_media(API_BASE_URL, temp_path, f"payment-proofs/{business['id']}/{proof_id}{ext}", content_type)
        doc = {
            "id": proof_id,
            "business_id": business["id"],
            "business_slug": business.get("slug"),
            "business_name": business.get("name"),
            "plan": plan_key,
            "method": method_key,
            "currency": currency,
            "amount": amount,
            "transaction_reference": transaction_reference.strip(),
            "customer_note": note.strip(),
            "receipt_key": storage_key,
            "status": "pending",
            "admin_note": None,
            "reviewed_by": None,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        collection("manual_payment_proofs").insert_one(doc)
        result = clean_doc(doc)
        result["receipt_url"] = media_url(API_BASE_URL, storage_key)
        result.pop("receipt_key", None)
        return result
    finally:
        temp_path.unlink(missing_ok=True)


@app.get("/api/businesses/{business_slug}/billing/manual-proofs")
def list_business_manual_proofs(business_slug: str, user: dict = Depends(auth_user)):
    business = owned_business(user["id"], business_slug)
    rows = clean_docs(collection("manual_payment_proofs").find({"business_id": business["id"]}).sort("created_at", -1).limit(30))
    for row in rows:
        row["receipt_url"] = media_url(API_BASE_URL, row.get("receipt_key"))
        row.pop("receipt_key", None)
    return {"proofs": rows}


@app.get("/api/admin/manual-payments")
def admin_manual_payments(_: dict = Depends(require_admin)):
    rows = clean_docs(collection("manual_payment_proofs").find({}).sort("created_at", -1).limit(200))
    for row in rows:
        row["receipt_url"] = media_url(API_BASE_URL, row.get("receipt_key"))
        row.pop("receipt_key", None)
    return {"settings": get_manual_payment_settings(), "proofs": rows}


@app.patch("/api/admin/manual-payments/settings")
def admin_update_manual_payment_settings(payload: ManualSettingsPayload, _: dict = Depends(require_admin)):
    return update_manual_payment_settings({
        "easypaisa": payload.easypaisa.model_dump(exclude_none=True),
        "jazzcash": payload.jazzcash.model_dump(exclude_none=True),
    })


@app.patch("/api/admin/manual-payments/{proof_id}")
def admin_review_manual_payment(proof_id: str, payload: ManualReviewPayload, admin: dict = Depends(require_admin)):
    proof = clean_doc(collection("manual_payment_proofs").find_one({"id": proof_id}))
    if not proof:
        raise HTTPException(status_code=404, detail="Payment proof not found")
    action = payload.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Action must be approve or reject")
    if proof.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Payment proof has already been reviewed")

    status = "approved" if action == "approve" else "rejected"
    collection("manual_payment_proofs").update_one({"id": proof_id}, {"$set": {
        "status": status,
        "admin_note": (payload.note or "").strip(),
        "reviewed_by": admin.get("email"),
        "updated_at": _now_iso(),
    }})
    if action == "approve":
        set_plan(proof["business_id"], proof["plan"], status="active")
        collection("billing_events").insert_one({
            "id": str(uuid.uuid4()), "business_id": proof["business_id"], "event_type": "manual_payment.approved",
            "payload": {"proof_id": proof_id, "method": proof["method"], "plan": proof["plan"], "amount": proof["amount"], "currency": proof["currency"]},
            "created_at": _now_iso(),
        })
    updated = clean_doc(collection("manual_payment_proofs").find_one({"id": proof_id}))
    updated["receipt_url"] = media_url(API_BASE_URL, updated.get("receipt_key"))
    updated.pop("receipt_key", None)
    return updated
