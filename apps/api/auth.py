from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

SECRET = os.getenv("ASHES_AUTH_SECRET", "dev-only-change-me")
TOKEN_TTL_HOURS = int(os.getenv("ASHES_TOKEN_TTL_HOURS", "168"))


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, expected = stored.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def issue_token(user_id: str) -> str:
    expires = int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())
    payload = f"{user_id}.{expires}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def decode_token(token: str) -> str | None:
    try:
        user_id, expires_raw, sig = token.split(".", 2)
        payload = f"{user_id}.{expires_raw}"
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(expires_raw) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return user_id
    except Exception:
        return None
