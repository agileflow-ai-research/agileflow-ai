from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jwt import InvalidTokenError

from app.common.id_generator import validate_id
from app.core.config import settings


_password_hasher = PasswordHasher()
_UNUSABLE_SECRET_KEYS = {"change-me-for-local-development"}


class TokenConfigurationError(RuntimeError):
    """Raised when JWT settings cannot safely sign or validate tokens."""


class AccessTokenError(ValueError):
    """Raised when an access token is invalid without exposing why."""


def hash_password(password: str) -> str:
    """Return an Argon2 hash for a plaintext registration password."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing Argon2 verification errors."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _jwt_secret(secret_key: str | None) -> str:
    configured_secret = (
        settings.jwt_secret_key if secret_key is None else secret_key
    )
    if (
        configured_secret is None
        or not configured_secret.strip()
        or configured_secret in _UNUSABLE_SECRET_KEYS
        or len(configured_secret.encode("utf-8")) < 32
    ):
        raise TokenConfigurationError(
            "JWT_SECRET_KEY must be a non-placeholder value of at least 32 bytes"
        )
    return configured_secret


def create_access_token(
    subject: str,
    *,
    secret_key: str | None = None,
    algorithm: str | None = None,
    expire_minutes: int | None = None,
    now: datetime | None = None,
) -> str:
    """Create a signed JWT containing only the approved identity claims."""
    validate_id(subject, "USR")
    signing_key = _jwt_secret(secret_key)
    configured_algorithm = algorithm or settings.jwt_algorithm
    configured_expiry = (
        settings.jwt_access_token_expire_minutes
        if expire_minutes is None
        else expire_minutes
    )
    if not configured_algorithm or configured_expiry < 1:
        raise TokenConfigurationError("JWT algorithm and expiry must be valid")

    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        raise TokenConfigurationError("JWT timestamps must be timezone-aware")
    expires_at = issued_at + timedelta(minutes=configured_expiry)
    return jwt.encode(
        {
            "sub": subject,
            "iat": issued_at,
            "exp": expires_at,
        },
        signing_key,
        algorithm=configured_algorithm,
    )


def decode_access_token(
    token: str,
    *,
    secret_key: str | None = None,
    algorithm: str | None = None,
) -> dict[str, Any]:
    """Validate a signed access token and its canonical User subject."""
    signing_key = _jwt_secret(secret_key)
    configured_algorithm = algorithm or settings.jwt_algorithm
    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[configured_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise AccessTokenError("Invalid access token")
        validate_id(subject, "USR")
        return payload
    except AccessTokenError:
        raise
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise AccessTokenError("Invalid access token") from exc
