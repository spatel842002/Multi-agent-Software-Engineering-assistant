"""Password hashing (Argon2id) and JWT access/refresh token issuance.

Refresh tokens are opaque, randomly generated strings; only their SHA-256
hash is stored (`RefreshToken.token_hash`), the same pattern as an API-key
store, so a database read never discloses a usable credential.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_settings = get_settings()
_hasher = PasswordHasher()


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH_OPAQUE = "refresh_opaque"


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(user_id: uuid.UUID, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=_settings.access_token_ttl_minutes))
    payload = {
        "sub": str(user_id),
        "type": TokenType.ACCESS.value,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _settings.jwt_secret_key.get_secret_value(), algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    payload = jwt.decode(
        token,
        _settings.jwt_secret_key.get_secret_value(),
        algorithms=[_settings.jwt_algorithm],
    )
    if payload.get("type") != TokenType.ACCESS.value:
        raise jwt.InvalidTokenError("not an access token")
    return payload


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Returns (opaque_token, token_hash, expires_at)."""
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=_settings.refresh_token_ttl_days)
    return token, token_hash, expires_at


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
