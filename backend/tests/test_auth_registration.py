from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common.id_generator import generate_id
from app.database.collections import USERS
from app.main import app
from app.modules.auth.repository import UserRepository, UserRepositoryError
from app.modules.auth.router import get_user_repository
from app.modules.auth.schemas import UserPublicResponse
from app.modules.auth.security import verify_password
from app.schemas.user import User


NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
REGISTER_REQUEST = {
    "name": "Dilshan Karunarathna",
    "email": " Dilshan@Example.COM ",
    "password": "prototype password",
}


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: list[dict[str, Any]] = []
        self.accessed_collections = {USERS}
        self.fail = False

    def _check_available(self) -> None:
        if self.fail:
            raise UserRepositoryError("private database detail")

    @staticmethod
    def _without_mongodb_id(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        self._check_available()
        for document in self.users:
            if document["email"] == email:
                return self._without_mongodb_id(deepcopy(document))
        return None

    def find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        self._check_available()
        for document in self.users:
            if document["user_id"] == user_id:
                return self._without_mongodb_id(deepcopy(document))
        return None

    def next_user_sequence(self) -> int:
        self._check_available()
        return len(self.users) + 1

    def create_user(self, user: User) -> dict[str, Any]:
        self._check_available()
        document = user.model_dump(mode="python")
        document["_id"] = f"internal-{len(self.users) + 1}"
        self.users.append(document)
        return self._without_mongodb_id(deepcopy(document))


@pytest.fixture
def auth_client():
    repository = FakeUserRepository()
    app.dependency_overrides[get_user_repository] = lambda: repository
    try:
        yield TestClient(app), repository
    finally:
        app.dependency_overrides.clear()


def test_valid_registration_returns_safe_public_user(auth_client) -> None:
    client, repository = auth_client

    response = client.post("/api/v1/auth/register", json=REGISTER_REQUEST)

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "User registered successfully"
    assert payload["errors"] == []
    assert payload["data"] == {
        "user_id": "USR-001",
        "name": "Dilshan Karunarathna",
        "email": "dilshan@example.com",
        "is_active": True,
        "created_at": payload["data"]["created_at"],
        "updated_at": payload["data"]["updated_at"],
    }
    assert payload["data"]["created_at"] is not None
    assert payload["data"]["updated_at"] is not None
    assert "_id" not in payload["data"]
    assert "password" not in payload["data"]
    assert "password_hash" not in payload["data"]

    stored = repository.users[0]
    assert stored["user_id"] == "USR-001"
    assert stored["email"] == "dilshan@example.com"
    assert stored["is_active"] is True
    assert stored["password_hash"] != REGISTER_REQUEST["password"]
    assert stored["password_hash"].startswith("$argon2")
    assert "password" not in stored


def test_registration_generates_sequential_user_ids(auth_client) -> None:
    client, _ = auth_client

    first = client.post("/api/v1/auth/register", json=REGISTER_REQUEST)
    second = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_REQUEST, "email": "second@example.com"},
    )

    assert first.json()["data"]["user_id"] == "USR-001"
    assert second.json()["data"]["user_id"] == "USR-002"


@pytest.mark.parametrize("missing_field", ["name", "email", "password"])
def test_registration_requires_approved_fields(
    auth_client,
    missing_field: str,
) -> None:
    client, repository = auth_client
    request = {
        key: value
        for key, value in REGISTER_REQUEST.items()
        if key != missing_field
    }

    response = client.post("/api/v1/auth/register", json=request)

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert repository.users == []


def test_registration_rejects_whitespace_only_email(auth_client) -> None:
    client, repository = auth_client

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_REQUEST, "email": "   "},
    )

    assert response.status_code == 422
    assert repository.users == []


@pytest.mark.parametrize(
    "duplicate_email",
    ["dilshan@example.com", "  DILSHAN@EXAMPLE.COM  "],
)
def test_duplicate_normalized_email_returns_conflict(
    auth_client,
    duplicate_email: str,
) -> None:
    client, repository = auth_client
    first = client.post("/api/v1/auth/register", json=REGISTER_REQUEST)

    duplicate = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_REQUEST, "email": duplicate_email},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["success"] is False
    assert duplicate.json()["errors"] == [
        {"field": "email", "message": "Email is already registered"}
    ]
    assert len(repository.users) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", "USR-999"),
        ("password_hash", "not-client-controlled"),
        ("is_active", False),
        ("created_at", NOW.isoformat()),
        ("updated_at", NOW.isoformat()),
    ],
)
def test_registration_rejects_server_or_internal_fields(
    auth_client,
    field: str,
    value: Any,
) -> None:
    client, repository = auth_client

    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert repository.users == []


def test_password_helpers_use_argon2() -> None:
    from app.modules.auth.security import hash_password

    password_hash = hash_password("correct password")

    assert password_hash.startswith("$argon2")
    assert verify_password("correct password", password_hash) is True
    assert verify_password("incorrect password", password_hash) is False


def test_repository_failure_returns_safe_error(auth_client) -> None:
    client, repository = auth_client
    repository.fail = True

    response = client.post("/api/v1/auth/register", json=REGISTER_REQUEST)

    assert response.status_code == 503
    body = response.text
    assert "private database detail" not in body
    assert "password" not in body
    assert "password_hash" not in body


def test_user_contract_and_public_response_fields() -> None:
    assert set(User.model_fields) == {
        "user_id",
        "name",
        "email",
        "password_hash",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert set(UserPublicResponse.model_fields) == {
        "user_id",
        "name",
        "email",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_usr_id_and_users_collection_are_canonical() -> None:
    assert generate_id("USR", 1) == "USR-001"
    assert USERS == "users"


def test_user_repository_uses_only_users_and_strips_mongodb_id() -> None:
    class FakeCollection:
        def __init__(self) -> None:
            self.documents = [
                {
                    "_id": "internal-1",
                    "user_id": "USR-002",
                    "email": "a@example.com",
                },
                {
                    "_id": "internal-2",
                    "user_id": "invalid",
                    "email": "b@example.com",
                },
            ]

        def find(self, query, projection):
            del query, projection
            return deepcopy(self.documents)

        def find_one(self, query, projection):
            del projection
            return next(
                (
                    deepcopy(document)
                    for document in self.documents
                    if all(
                        document.get(key) == value
                        for key, value in query.items()
                    )
                ),
                None,
            )

        def insert_one(self, document):
            self.documents.append({**deepcopy(document), "_id": "internal-3"})

    class FakeDatabase:
        def __init__(self) -> None:
            self.collection = FakeCollection()
            self.requested_collections: list[str] = []

        def __getitem__(self, collection_name: str):
            self.requested_collections.append(collection_name)
            return self.collection

    database = FakeDatabase()
    repository = UserRepository(database)

    assert database.requested_collections == [USERS]
    assert repository.next_user_sequence() == 3
    assert repository.find_user_by_email("a@example.com") == {
        "user_id": "USR-002",
        "email": "a@example.com",
    }
    assert repository.find_user_by_id("USR-002") == {
        "user_id": "USR-002",
        "email": "a@example.com",
    }

    password_hash = "$argon2id$prototype"
    created = repository.create_user(
        User(
            user_id="USR-003",
            name="New User",
            email="new@example.com",
            password_hash=password_hash,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    assert created["user_id"] == "USR-003"
    assert "_id" not in created


def test_exact_registration_route_is_registered() -> None:
    with TestClient(app) as client:
        openapi = client.get("/openapi.json").json()

    auth_routes = {
        (method.upper(), path)
        for path, operations in openapi["paths"].items()
        if path.startswith("/api/v1/auth")
        for method in operations
    }
    assert ("POST", "/api/v1/auth/register") in auth_routes

    response_schema = openapi["paths"]["/api/v1/auth/register"]["post"][
        "responses"
    ]["201"]["content"]["application/json"]["schema"]
    response_ref = response_schema["$ref"].rsplit("/", maxsplit=1)[1]
    response_properties = openapi["components"]["schemas"][response_ref][
        "properties"
    ]
    data_ref = response_properties["data"]["anyOf"][0]["$ref"].rsplit(
        "/", maxsplit=1
    )[1]
    assert "password" not in openapi["components"]["schemas"][data_ref][
        "properties"
    ]
    assert "password_hash" not in openapi["components"]["schemas"][data_ref][
        "properties"
    ]
