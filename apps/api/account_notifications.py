from __future__ import annotations

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from apps.api.auth import hash_password
from apps.api.mongo_main import app, auth_user
from apps.api.mongo_db import collection, get_user_by_email
from apps.api.notification_service import (
    consume_account_token,
    list_notifications,
    mark_notification_read,
    send_password_reset_email,
    send_verification_email,
)


class EmailPayload(BaseModel):
    email: str


class TokenPayload(BaseModel):
    token: str


class ResetPasswordPayload(BaseModel):
    token: str
    password: str


@app.post("/api/auth/resend-verification")
def resend_verification(payload: EmailPayload):
    user = get_user_by_email(payload.email.strip().lower())
    if user and not user.get("email_verified"):
        send_verification_email(user)
    return {"ok": True, "message": "If the account exists and needs verification, a link has been sent."}


@app.post("/api/auth/verify-email")
def verify_email(payload: TokenPayload):
    token = consume_account_token(payload.token, "verify_email")
    if not token:
        raise HTTPException(400, "Verification link is invalid or expired")
    collection("users").update_one({"id": token["user_id"]}, {"$set": {"email_verified": True}})
    return {"ok": True, "message": "Email verified successfully."}


@app.post("/api/auth/request-password-reset")
def request_password_reset(payload: EmailPayload):
    user = get_user_by_email(payload.email.strip().lower())
    if user:
        send_password_reset_email(user)
    return {"ok": True, "message": "If that email exists, a reset link has been sent."}


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordPayload):
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    token = consume_account_token(payload.token, "password_reset")
    if not token:
        raise HTTPException(400, "Reset link is invalid or expired")
    collection("users").update_one({"id": token["user_id"]}, {"$set": {"password_hash": hash_password(payload.password)}})
    return {"ok": True, "message": "Password updated. You can sign in now."}


@app.get("/api/notifications")
def notifications(user: dict = Depends(auth_user)):
    items = list_notifications(user["id"])
    return {"items": items, "unread": sum(1 for item in items if not item.get("read_at"))}


@app.patch("/api/notifications/{notification_id}/read")
def notification_read(notification_id: str, user: dict = Depends(auth_user)):
    item = mark_notification_read(user["id"], notification_id)
    if not item:
        raise HTTPException(404, "Notification not found")
    return item
