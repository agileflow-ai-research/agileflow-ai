from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.database.collections import PROJECTS
from app.main import app
from app.modules.projects.repository import (
    ProjectRepository,
    ProjectRepositoryError,
)
from app.modules.projects.router import get_project_repository
from app.schemas.project import Project


CREATE_PAYLOAD = {
    "name": "Book Management System",
    "domain": "Library / Education",
    "description": "A controlled sample project",
    "created_by": "foundation_user",
}


class FakeProjectRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.fail = False

    def _check_available(self) -> None:
        if self.fail:
            raise ProjectRepositoryError("private database detail")

    @staticmethod
    def _public(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def next_project_sequence(self) -> int:
        self._check_available()
        sequences = [
            int(project_id.rsplit("-", maxsplit=1)[1])
            for project_id in self.documents
        ]
        return max(sequences, default=0) + 1

    def create_project(self, project: Project) -> dict[str, Any]:
        self._check_available()
        document = project.model_dump(mode="python")
        document["_id"] = f"internal-{project.project_id}"
        self.documents[project.project_id] = document
        return self._public(deepcopy(document))

    def list_projects(self) -> list[dict[str, Any]]:
        self._check_available()
        return [self._public(deepcopy(document)) for document in self.documents.values()]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        self._check_available()
        document = self.documents.get(project_id)
        return self._public(deepcopy(document)) if document is not None else None

    def update_project(
        self,
        project_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        self._check_available()
        document = self.documents.get(project_id)
        if document is None:
            return None
        document.update(updates)
        return self._public(deepcopy(document))


@pytest.fixture
def project_client() -> tuple[TestClient, FakeProjectRepository]:
    repository = FakeProjectRepository()
    app.dependency_overrides[get_project_repository] = lambda: repository
    try:
        yield TestClient(app), repository
    finally:
        app.dependency_overrides.clear()


def create_project(client: TestClient, payload: dict[str, str] | None = None):
    return client.post("/api/v1/projects", json=payload or CREATE_PAYLOAD)


def assert_canonical_envelope(payload: dict[str, Any]) -> None:
    assert set(payload) == {
        "success",
        "message",
        "data",
        "errors",
        "workflow_stage",
        "next_action",
    }


def test_create_project_successfully(project_client) -> None:
    client, repository = project_client

    response = create_project(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["project_id"] == "PRJ-001"
    assert payload["data"]["current_stage"] == "PROJECT_CREATED"
    assert payload["workflow_stage"] == "PROJECT_CREATED"
    assert payload["data"]["status"] == "IN_PROGRESS"
    assert payload["data"]["created_at"] == payload["data"]["updated_at"]
    assert "PRJ-001" in repository.documents


def test_generated_project_ids_follow_sequence(project_client) -> None:
    client, _ = project_client

    first = create_project(client)
    second = create_project(client, {**CREATE_PAYLOAD, "name": "Second project"})

    assert first.json()["data"]["project_id"] == "PRJ-001"
    assert second.json()["data"]["project_id"] == "PRJ-002"


def test_list_projects(project_client) -> None:
    client, _ = project_client
    create_project(client)
    create_project(client, {**CREATE_PAYLOAD, "name": "Second project"})

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    assert [item["project_id"] for item in response.json()["data"]] == [
        "PRJ-001",
        "PRJ-002",
    ]


def test_list_projects_returns_empty_list(project_client) -> None:
    client, _ = project_client

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_get_existing_project(project_client) -> None:
    client, _ = project_client
    create_project(client)

    response = client.get("/api/v1/projects/PRJ-001")

    assert response.status_code == 200
    assert response.json()["data"]["name"] == CREATE_PAYLOAD["name"]


def test_get_missing_project(project_client) -> None:
    client, _ = project_client

    response = client.get("/api/v1/projects/PRJ-999")

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["errors"] == [
        {"field": "project_id", "message": "Project not found"}
    ]


def test_get_rejects_invalid_project_id(project_client) -> None:
    client, _ = project_client

    response = client.get("/api/v1/projects/REQ-001")

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "project_id"


def test_update_allowed_metadata(project_client) -> None:
    client, _ = project_client
    created = create_project(client).json()["data"]

    response = client.patch(
        "/api/v1/projects/PRJ-001",
        json={"name": "Updated project", "description": "Updated description"},
    )

    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["name"] == "Updated project"
    assert updated["description"] == "Updated description"
    assert updated["domain"] == created["domain"]
    assert updated["created_at"] == created["created_at"]
    assert datetime.fromisoformat(updated["updated_at"]) >= datetime.fromisoformat(
        created["updated_at"]
    )


def test_update_missing_project(project_client) -> None:
    client, _ = project_client

    response = client.patch(
        "/api/v1/projects/PRJ-999",
        json={"description": "Updated"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "PRJ-999"),
        ("current_stage", "COMPLETED"),
        ("created_at", "2026-01-01T00:00:00Z"),
    ],
)
def test_update_rejects_protected_fields(project_client, field, value) -> None:
    client, _ = project_client
    create_project(client)

    response = client.patch(
        "/api/v1/projects/PRJ-001",
        json={field: value},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["errors"][0]["field"] == field


def test_mongodb_internal_id_is_not_exposed(project_client) -> None:
    client, repository = project_client
    create_project(client)
    assert "_id" in repository.documents["PRJ-001"]

    create_payload = client.get("/api/v1/projects/PRJ-001").json()
    list_payload = client.get("/api/v1/projects").json()

    assert "_id" not in create_payload["data"]
    assert all("_id" not in project for project in list_payload["data"])


def test_project_responses_use_canonical_envelope(project_client) -> None:
    client, _ = project_client

    create_response = create_project(client).json()
    list_response = client.get("/api/v1/projects").json()
    get_response = client.get("/api/v1/projects/PRJ-001").json()
    update_response = client.patch(
        "/api/v1/projects/PRJ-001",
        json={"domain": "Education"},
    ).json()

    for payload in (create_response, list_response, get_response, update_response):
        assert_canonical_envelope(payload)


def test_validation_error_uses_canonical_envelope(project_client) -> None:
    client, _ = project_client

    response = client.post("/api/v1/projects", json={"name": "Incomplete"})

    assert response.status_code == 422
    assert_canonical_envelope(response.json())
    assert response.json()["success"] is False


def test_database_failure_does_not_expose_exception(project_client) -> None:
    client, repository = project_client
    repository.fail = True

    response = client.get("/api/v1/projects")

    assert response.status_code == 503
    assert "private database detail" not in response.text
    assert response.json()["errors"][0]["field"] == "database"


def test_project_repository_uses_projects_collection_and_strips_mongodb_id() -> None:
    now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    document = {
        "_id": "mongo-internal-id",
        "project_id": "PRJ-001",
        "name": "Book Management System",
        "domain": "Library / Education",
        "description": "A controlled sample project",
        "current_stage": "PROJECT_CREATED",
        "status": "IN_PROGRESS",
        "created_by": "foundation_user",
        "created_at": now,
        "updated_at": now,
    }

    class FakeCollection:
        def find(self, query, projection):
            return [deepcopy(document)]

    class FakeDatabase:
        def __init__(self) -> None:
            self.requested_collection = None

        def __getitem__(self, collection_name):
            self.requested_collection = collection_name
            return FakeCollection()

    database = FakeDatabase()
    repository = ProjectRepository(database)

    projects = repository.list_projects()

    assert database.requested_collection == PROJECTS
    assert projects[0]["project_id"] == "PRJ-001"
    assert "_id" not in projects[0]


def test_only_canonical_project_routes_are_registered() -> None:
    openapi_paths = app.openapi()["paths"]
    project_routes = {
        (method.upper(), path)
        for path, operations in openapi_paths.items()
        if path.startswith("/api")
        for method in operations
    }

    assert project_routes == {
        ("POST", "/api/v1/projects"),
        ("GET", "/api/v1/projects"),
        ("GET", "/api/v1/projects/{project_id}"),
        ("PATCH", "/api/v1/projects/{project_id}"),
    }


def test_swagger_and_openapi_remain_available(project_client) -> None:
    client, _ = project_client

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
