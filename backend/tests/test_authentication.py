from copy import deepcopy
from datetime import datetime, timedelta, timezone
import inspect
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.auth import dependencies, router
from app.modules.auth.dependencies import get_current_user, get_user_repository
from app.modules.auth.repository import UserRepositoryError
from app.modules.auth.security import (
    AccessTokenError,
    TokenConfigurationError,
    create_access_token,
    decode_access_token,
    hash_password,
)


TEST_SECRET = "test-only-jwt-secret-never-use-in-production"
USER_ID = "USR-001"
EMAIL = "user@example.com"
PASSWORD = "correct password"
NOW = datetime.now(timezone.utc)


def user_document(
    *,
    user_id: str = USER_ID,
    email: str = EMAIL,
    is_active: bool = True,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "name": "Test User",
        "email": email,
        "password_hash": hash_password(PASSWORD),
        "is_active": is_active,
        "created_at": NOW,
        "updated_at": NOW,
    }


class FakeAuthenticationRepository:
    def __init__(self) -> None:
        self.users: list[dict[str, Any]] = [user_document()]
        self.fail = False

    def _check_available(self) -> None:
        if self.fail:
            raise UserRepositoryError("private database detail")

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        self._check_available()
        return next(
            (
                deepcopy(user)
                for user in self.users
                if user["email"] == email
            ),
            None,
        )

    def find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        self._check_available()
        return next(
            (
                deepcopy(user)
                for user in self.users
                if user["user_id"] == user_id
            ),
            None,
        )

    def next_user_sequence(self) -> int:
        self._check_available()
        return len(self.users) + 1

    def create_user(self, user) -> dict[str, Any]:
        self._check_available()
        document = user.model_dump(mode="python")
        self.users.append(deepcopy(document))
        return document


@pytest.fixture
def authenticated_client(monkeypatch):
    repository = FakeAuthenticationRepository()
    monkeypatch.setattr(settings, "jwt_secret_key", TEST_SECRET)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_access_token_expire_minutes", 60)
    app.dependency_overrides[get_user_repository] = lambda: repository
    try:
        yield TestClient(app), repository
    finally:
        app.dependency_overrides.clear()


def test_valid_login_returns_bearer_token_with_approved_claims(
    authenticated_client,
) -> None:
    client, _ = authenticated_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  USER@EXAMPLE.COM ", "password": PASSWORD},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["data"]
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert "password" not in response.text
    assert "password_hash" not in response.text

    payload = decode_access_token(
        data["access_token"],
        secret_key=TEST_SECRET,
    )
    assert payload["sub"] == USER_ID
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]
    assert "password" not in payload
    assert "password_hash" not in payload


def test_unknown_email_and_wrong_password_use_same_safe_response(
    authenticated_client,
) -> None:
    client, _ = authenticated_client

    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": PASSWORD},
    )
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": "wrong password"},
    )

    assert unknown.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()
    assert unknown.json()["message"] == "Invalid credentials"
    assert unknown.headers["www-authenticate"] == "Bearer"


def test_inactive_user_cannot_login(authenticated_client) -> None:
    client, repository = authenticated_client
    repository.users[0]["is_active"] = False

    response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid credentials"


def test_login_rejects_extra_fields(authenticated_client) -> None:
    client, _ = authenticated_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD, "role": "admin"},
    )

    assert response.status_code == 422


def test_access_token_round_trip_uses_only_approved_claims() -> None:
    token = create_access_token(
        USER_ID,
        secret_key=TEST_SECRET,
        now=NOW,
    )

    payload = decode_access_token(token, secret_key=TEST_SECRET)

    assert set(payload) == {"sub", "iat", "exp"}
    assert payload["sub"] == USER_ID


def test_invalid_signature_is_rejected() -> None:
    token = create_access_token(USER_ID, secret_key=TEST_SECRET)

    with pytest.raises(AccessTokenError):
        decode_access_token(
            token,
            secret_key="different-test-secret-that-is-long-enough",
        )


def test_expired_token_is_rejected() -> None:
    token = create_access_token(
        USER_ID,
        secret_key=TEST_SECRET,
        now=NOW - timedelta(hours=2),
        expire_minutes=60,
    )

    with pytest.raises(AccessTokenError):
        decode_access_token(token, secret_key=TEST_SECRET)


@pytest.mark.parametrize("subject", [None, "not-a-user-id", "PRJ-001"])
def test_missing_or_malformed_subject_is_rejected(subject) -> None:
    payload = {
        "iat": NOW,
        "exp": NOW + timedelta(minutes=60),
    }
    if subject is not None:
        payload["sub"] = subject
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")

    with pytest.raises(AccessTokenError):
        decode_access_token(token, secret_key=TEST_SECRET)


@pytest.mark.parametrize(
    "secret_key",
    [None, "", "short-secret", "change-me-for-local-development"],
)
def test_missing_or_placeholder_secret_fails_clearly(
    monkeypatch,
    secret_key: str | None,
) -> None:
    monkeypatch.setattr(settings, "jwt_secret_key", secret_key)

    with pytest.raises(TokenConfigurationError):
        create_access_token(USER_ID)


def test_auth_me_returns_safe_public_user(authenticated_client) -> None:
    client, _ = authenticated_client
    token = create_access_token(USER_ID)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "user_id": USER_ID,
        "name": "Test User",
        "email": EMAIL,
        "is_active": True,
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
    }
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic credentials"},
        {"Authorization": "Bearer malformed-token"},
    ],
)
def test_auth_me_rejects_missing_or_invalid_bearer_token(
    authenticated_client,
    headers: dict[str, str],
) -> None:
    client, _ = authenticated_client

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication failed"
    assert response.headers["www-authenticate"] == "Bearer"


def test_auth_me_rejects_expired_token(authenticated_client) -> None:
    client, _ = authenticated_client
    token = create_access_token(
        USER_ID,
        now=NOW - timedelta(hours=2),
        expire_minutes=60,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_auth_me_rejects_nonexistent_user(authenticated_client) -> None:
    client, _ = authenticated_client
    token = create_access_token("USR-999")

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_auth_me_rejects_inactive_user(authenticated_client) -> None:
    client, repository = authenticated_client
    repository.users[0]["is_active"] = False
    token = create_access_token(USER_ID)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_auth_me_repository_failure_is_safe(authenticated_client) -> None:
    client, repository = authenticated_client
    repository.fail = True
    token = create_access_token(USER_ID)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert "private database detail" not in response.text


def test_auth_me_uses_central_get_current_user_dependency() -> None:
    router_source = inspect.getsource(router)
    dependency_source = inspect.getsource(dependencies)

    assert "Depends(get_current_user)" in router_source
    assert "decode_access_token" not in router_source
    assert "decode_access_token" in dependency_source
    assert callable(get_current_user)


def test_exact_auth_routes_are_registered(authenticated_client) -> None:
    client, _ = authenticated_client
    openapi = client.get("/openapi.json").json()

    auth_routes = {
        (method.upper(), path)
        for path, operations in openapi["paths"].items()
        if path.startswith("/api/v1/auth")
        for method in operations
    }
    assert auth_routes == {
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/login"),
        ("GET", "/api/v1/auth/me"),
    }
