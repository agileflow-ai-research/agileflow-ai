from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common.status import WorkflowStage
from app.database.collections import (
    APPROVALS,
    CLIENT_INPUTS,
    PROJECTS,
    REQUIREMENTS,
)
from app.main import app
from app.modules.requirements.repository import (
    ClientInputRepository,
    ClientInputRepositoryError,
)
from app.modules.requirements.router import get_client_input_repository
from app.modules.requirements.schemas import ClientInputResponse, ClientInputType


INITIAL_TIME = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
TEXT_INPUT = {
    "input_type": "TEXT",
    "content": "The system must manage books and borrowers.",
}


def project_document(
    project_id: str,
    owner_user_id: str = "USR-001",
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "owner_user_id": owner_user_id,
        "name": f"Project {project_id}",
        "domain": "Education",
        "description": "Client input test project",
        "current_stage": WorkflowStage.PROJECT_CREATED.value,
        "status": "IN_PROGRESS",
        "created_by": "foundation_user",
        "created_at": INITIAL_TIME,
        "updated_at": INITIAL_TIME,
    }


class FakeClientInputRepository:
    def __init__(self) -> None:
        self.projects = {
            "PRJ-001": project_document("PRJ-001"),
            "PRJ-002": project_document("PRJ-002"),
        }
        self.client_inputs: list[dict[str, Any]] = []
        self.accessed_collections = {PROJECTS, CLIENT_INPUTS}
        self.fail = False

    def _check_available(self) -> None:
        if self.fail:
            raise ClientInputRepositoryError("private database detail")

    @staticmethod
    def _public(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        self._check_available()
        document = self.projects.get(project_id)
        return self._public(deepcopy(document)) if document is not None else None

    def create_client_input(
        self,
        client_input: ClientInputResponse,
    ) -> dict[str, Any]:
        self._check_available()
        document = client_input.model_dump(mode="python")
        document["_id"] = f"internal-{len(self.client_inputs) + 1}"
        self.client_inputs.append(document)
        return self._public(deepcopy(document))

    def list_client_inputs(self, project_id: str) -> list[dict[str, Any]]:
        self._check_available()
        return [
            self._public(deepcopy(document))
            for document in self.client_inputs
            if document["project_id"] == project_id
        ]

    def has_client_input(self, project_id: str) -> bool:
        self._check_available()
        return any(
            document["project_id"] == project_id
            for document in self.client_inputs
        )


@pytest.fixture
def client_input_client(authentication_context):
    repository = FakeClientInputRepository()
    app.dependency_overrides[get_client_input_repository] = lambda: repository
    try:
        yield authentication_context.client(), repository
    finally:
        app.dependency_overrides.pop(get_client_input_repository, None)


def test_create_text_client_input_successfully(client_input_client) -> None:
    client, repository = client_input_client

    response = client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json=TEXT_INPUT,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["project_id"] == "PRJ-001"
    assert payload["data"]["input_type"] == "TEXT"
    assert payload["data"]["content"] == TEXT_INPUT["content"]
    assert payload["data"]["created_at"] is not None
    assert "_id" not in payload["data"]
    assert len(repository.client_inputs) == 1
    assert repository.client_inputs[0]["project_id"] == "PRJ-001"


@pytest.mark.parametrize("missing_field", ["input_type", "content"])
def test_create_requires_approved_fields(
    client_input_client,
    missing_field: str,
) -> None:
    client, repository = client_input_client
    request = {key: value for key, value in TEXT_INPUT.items() if key != missing_field}

    response = client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json=request,
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == missing_field
    assert repository.client_inputs == []


def test_create_rejects_unsupported_input_type(client_input_client) -> None:
    client, repository = client_input_client

    response = client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json={**TEXT_INPUT, "input_type": "CHAT"},
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "input_type"
    assert repository.client_inputs == []


def test_create_accepts_optional_fields(client_input_client) -> None:
    client, _ = client_input_client

    response = client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json={
            "input_type": "DOCUMENT",
            "content": "prototype://documents/brief.txt",
            "original_filename": "brief.txt",
            "mime_type": "text/plain",
            "metadata": {"source": "client", "pages": 2},
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["original_filename"] == "brief.txt"
    assert data["mime_type"] == "text/plain"
    assert data["metadata"] == {"source": "client", "pages": 2}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "PRJ-002"),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("_id", "internal-id"),
    ],
)
def test_create_rejects_server_or_internal_fields(
    client_input_client,
    field: str,
    value: str,
) -> None:
    client, repository = client_input_client

    response = client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json={**TEXT_INPUT, field: value},
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field
    assert repository.client_inputs == []


def test_create_for_missing_project_returns_not_found(client_input_client) -> None:
    client, repository = client_input_client

    response = client.post(
        "/api/v1/projects/PRJ-999/inputs",
        json=TEXT_INPUT,
    )

    assert response.status_code == 404
    assert repository.client_inputs == []


def test_client_input_routes_reject_invalid_project_id(client_input_client) -> None:
    client, repository = client_input_client

    create_response = client.post(
        "/api/v1/projects/REQ-001/inputs",
        json=TEXT_INPUT,
    )
    list_response = client.get("/api/v1/projects/REQ-001/inputs")

    assert create_response.status_code == 422
    assert list_response.status_code == 422
    assert repository.client_inputs == []


def test_list_returns_only_project_inputs(client_input_client) -> None:
    client, _ = client_input_client
    client.post("/api/v1/projects/PRJ-001/inputs", json=TEXT_INPUT)
    client.post(
        "/api/v1/projects/PRJ-002/inputs",
        json={**TEXT_INPUT, "content": "Other project input"},
    )

    response = client.get("/api/v1/projects/PRJ-001/inputs")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["project_id"] == "PRJ-001"
    assert "_id" not in response.json()["data"][0]


def test_list_returns_empty_list_for_project_without_inputs(
    client_input_client,
) -> None:
    client, _ = client_input_client

    response = client.get("/api/v1/projects/PRJ-001/inputs")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_create_has_no_workflow_or_requirement_side_effects(
    client_input_client,
) -> None:
    client, repository = client_input_client
    initial_project = deepcopy(repository.projects["PRJ-001"])

    response = client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json=TEXT_INPUT,
    )

    assert response.status_code == 201
    assert repository.projects["PRJ-001"] == initial_project
    assert repository.accessed_collections == {PROJECTS, CLIENT_INPUTS}
    assert REQUIREMENTS not in repository.accessed_collections
    assert APPROVALS not in repository.accessed_collections


def test_client_input_repository_failure_is_safe(client_input_client) -> None:
    client, repository = client_input_client
    repository.fail = True

    response = client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json=TEXT_INPUT,
    )

    assert response.status_code == 503
    assert "private database detail" not in response.text


def test_client_input_routes_require_authentication(authentication_context) -> None:
    client = authentication_context.anonymous_client()

    assert client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json=TEXT_INPUT,
    ).status_code == 401
    assert client.get("/api/v1/projects/PRJ-001/inputs").status_code == 401


def test_foreign_user_cannot_create_or_list_project_inputs(
    client_input_client,
    authentication_context,
) -> None:
    _, repository = client_input_client
    foreign_client = authentication_context.client("USR-002")

    create_response = foreign_client.post(
        "/api/v1/projects/PRJ-001/inputs",
        json=TEXT_INPUT,
    )
    list_response = foreign_client.get("/api/v1/projects/PRJ-001/inputs")

    assert create_response.status_code == 404
    assert list_response.status_code == 404
    assert repository.client_inputs == []


def test_client_input_type_values_are_exact() -> None:
    assert [value.value for value in ClientInputType] == [
        "TEXT",
        "DOCUMENT",
        "AUDIO",
        "VIDEO",
        "LIVE_INTERVIEW",
    ]


def test_client_input_response_has_no_public_identifier() -> None:
    assert set(ClientInputResponse.model_fields) == {
        "project_id",
        "input_type",
        "content",
        "original_filename",
        "mime_type",
        "metadata",
        "created_at",
    }


def test_repository_selects_only_project_and_client_input_collections() -> None:
    class FakeCollection:
        pass

    class FakeDatabase:
        def __init__(self) -> None:
            self.requested_collections: list[str] = []

        def __getitem__(self, collection_name: str) -> FakeCollection:
            self.requested_collections.append(collection_name)
            return FakeCollection()

    database = FakeDatabase()

    ClientInputRepository(database)

    assert database.requested_collections == [PROJECTS, CLIENT_INPUTS]


def test_exact_client_input_routes_are_registered() -> None:
    operations = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        if path.endswith("/inputs")
        for method in methods
    }

    assert operations == {
        ("POST", "/api/v1/projects/{project_id}/inputs"),
        ("GET", "/api/v1/projects/{project_id}/inputs"),
    }
