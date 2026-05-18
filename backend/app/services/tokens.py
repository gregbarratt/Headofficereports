from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings


class TokenError(ValueError):
    pass


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _json_b64(value: dict[str, Any]) -> str:
    return _b64_encode(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _sign(message: str) -> str:
    if not settings.jwt_secret_key:
        raise TokenError("JWT_SECRET_KEY is not configured.")
    digest = hmac.new(settings.jwt_secret_key.encode("utf-8"), message.encode("ascii"), hashlib.sha256).digest()
    return _b64_encode(digest)


def create_access_token(subject: str, email: str, is_super_admin: bool) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload = {
        "sub": subject,
        "email": email,
        "is_super_admin": is_super_admin,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    signing_input = f"{_json_b64(header)}.{_json_b64(payload)}"
    return f"{signing_input}.{_sign(signing_input)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_raw, payload_raw, signature = token.split(".", 2)
    except ValueError as exc:
        raise TokenError("Token format is invalid.") from exc

    signing_input = f"{header_raw}.{payload_raw}"
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenError("Token signature is invalid.")

    try:
        header = json.loads(_b64_decode(header_raw))
        payload = json.loads(_b64_decode(payload_raw))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Token content is invalid.") from exc

    if header.get("alg") != settings.jwt_algorithm:
        raise TokenError("Token algorithm is invalid.")

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        raise TokenError("Token expiry is invalid.")

    if datetime.now(UTC).timestamp() > expires_at:
        raise TokenError("Token has expired.")

    return payload
