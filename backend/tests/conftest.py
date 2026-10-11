from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.modules.auth.dependencies import get_user_repository
from app.modules.auth.security import create_access_token


TEST_JWT_SECRET = "test-only-jwt-secret-that-is-longer-than-32-bytes"
TEST_TIME = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _user_document(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "name": f"Test User {user_id}",
        "email": f"{user_id.lower()}@example.com",
        "password_hash": "$argon2id$test-only-hash",
        "is_active": True,
        "created_at": TEST_TIME,
        "updated_at": TEST_TIME,
    }


class FakeCurrentUserRepository:
    def __init__(self) -> None:
        self.users = {
            "USR-001": _user_document("USR-001"),
            "USR-002": _user_document("USR-002"),
        }

    def find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.users.get(user_id)


@dataclass
class AuthenticationTestContext:
    repository: FakeCurrentUserRepository

    def client(self, user_id: str = "USR-001") -> TestClient:
        token = create_access_token(user_id, secret_key=TEST_JWT_SECRET)
        return TestClient(
            app,
            headers={"Authorization": f"Bearer {token}"},
        )

    @staticmethod
    def anonymous_client() -> TestClient:
        return TestClient(app)


@pytest.fixture
def authentication_context(monkeypatch) -> AuthenticationTestContext:
    repository = FakeCurrentUserRepository()
    monkeypatch.setattr(settings, "jwt_secret_key", TEST_JWT_SECRET)
    app.dependency_overrides[get_user_repository] = lambda: repository
    try:
        yield AuthenticationTestContext(repository)
    finally:
        app.dependency_overrides.pop(get_user_repository, None)
