from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from apps.api.mongo_db import clean_doc, clean_docs, collection

PUBLIC_BASE_URL = os.getenv("ASHES_PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
MAIL_PROVIDER = os.getenv("ASHES_MAIL_PROVIDER", "console").strip().lower()
MAIL_FROM = os.getenv("ASHES_MAIL_FROM", "Ashes AI <no-reply@ashes.ai>")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_account_token(user_id: str, purpose: str, ttl_minutes: int) -> str:
    raw = secrets.token_urlsafe(32)
    collection("account_tokens").insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "purpose": purpose,
        "token_hash": _hash_token(raw),
        "created_at": _now_iso(),
        "expires_at": (_now() + timedelta(minutes=ttl_minutes)).isoformat(),
        "used_at": None,
    })
    return raw


def consume_account_token(raw_token: str, purpose: str) -> Optional[dict]:
    token_hash = _hash_token(raw_token)
    doc = collection("account_tokens").find_one({"token_hash": token_hash, "purpose": purpose, "used_at": None})
    if not doc:
        return None
    try:
        expires = datetime.fromisoformat(str(doc.get("expires_at")))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < _now():
            return None
    except Exception:
        return None
    collection("account_tokens").update_one({"_id": doc["_id"]}, {"$set": {"used_at": _now_iso()}})
    return clean_doc(doc)


def create_notification(user_id: str, title: str, body: str, kind: str = "info", business_id: str | None = None, action_url: str | None = None) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "business_id": business_id,
        "kind": kind,
        "title": title,
        "body": body,
        "action_url": action_url,
        "read_at": None,
        "created_at": _now_iso(),
    }
    collection("notifications").insert_one(doc)
    return clean_doc(doc)


def list_notifications(user_id: str, limit: int = 50) -> list[dict]:
    return clean_docs(collection("notifications").find({"user_id": user_id}).sort("created_at", -1).limit(limit))


def mark_notification_read(user_id: str, notification_id: str) -> Optional[dict]:
    collection("notifications").update_one({"id": notification_id, "user_id": user_id}, {"$set": {"read_at": _now_iso()}})
    return clean_doc(collection("notifications").find_one({"id": notification_id, "user_id": user_id}))


def _smtp_send(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    host = os.getenv("ASHES_SMTP_HOST", "")
    port = int(os.getenv("ASHES_SMTP_PORT", "587"))
    username = os.getenv("ASHES_SMTP_USERNAME", "")
    password = os.getenv("ASHES_SMTP_PASSWORD", "")
    use_tls = os.getenv("ASHES_SMTP_TLS", "true").lower() not in {"0", "false", "no"}
    if not host:
        raise RuntimeError("ASHES_SMTP_HOST is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = MAIL_FROM
    message["To"] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        if use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    status = "sent"
    error = None
    if MAIL_PROVIDER == "smtp":
        try:
            _smtp_send(to_email, subject, text_body, html_body)
        except Exception as exc:
            status = "failed"
            error = str(exc)[:500]
    else:
        status = "console"
        print(f"[ASHES MAIL] To={to_email} Subject={subject}\n{text_body}\n")

    record = {
        "id": str(uuid.uuid4()),
        "to": to_email,
        "subject": subject,
        "provider": MAIL_PROVIDER,
        "status": status,
        "error": error,
        "created_at": _now_iso(),
    }
    collection("mail_events").insert_one(record)
    return clean_doc(record)


def send_verification_email(user: dict) -> None:
    token = create_account_token(user["id"], "verify_email", 60 * 24)
    url = f"{PUBLIC_BASE_URL}/?verify_email={token}"
    send_email(
        user["email"],
        "Verify your Ashes AI email",
        f"Welcome to Ashes AI. Verify your email within 24 hours:\n\n{url}\n\nIf you did not create this account, ignore this email.",
        f"<h2>Welcome to Ashes AI</h2><p>Verify your email within 24 hours.</p><p><a href=\"{url}\">Verify email</a></p>",
    )
    create_notification(user["id"], "Verify your email", "Confirm your email address to secure your Ashes account.", "account", action_url=url)


def send_password_reset_email(user: dict) -> None:
    token = create_account_token(user["id"], "password_reset", 30)
    url = f"{PUBLIC_BASE_URL}/?reset_password={token}"
    send_email(
        user["email"],
        "Reset your Ashes AI password",
        f"Use this link to reset your Ashes password. It expires in 30 minutes:\n\n{url}\n\nIf you did not request this, ignore this email.",
        f"<h2>Reset your Ashes password</h2><p>This link expires in 30 minutes.</p><p><a href=\"{url}\">Reset password</a></p>",
    )
