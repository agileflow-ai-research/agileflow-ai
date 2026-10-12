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

    def list_projects(self, owner_user_id: str) -> list[dict[str, Any]]:
        self._check_available()
        return [
            self._public(deepcopy(document))
            for document in self.documents.values()
            if document.get("owner_user_id") == owner_user_id
        ]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        self._check_available()
        document = self.documents.get(project_id)
        return self._public(deepcopy(document)) if document is not None else None

    def update_project(
        self,
        project_id: str,
        owner_user_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        self._check_available()
        document = self.documents.get(project_id)
        if document is None or document.get("owner_user_id") != owner_user_id:
            return None
        document.update(updates)
        return self._public(deepcopy(document))


@pytest.fixture
def project_client(authentication_context) -> tuple[TestClient, FakeProjectRepository]:
    repository = FakeProjectRepository()
    app.dependency_overrides[get_project_repository] = lambda: repository
    try:
        yield authentication_context.client(), repository
    finally:
        app.dependency_overrides.pop(get_project_repository, None)


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
    assert payload["data"]["owner_user_id"] == "USR-001"
    assert payload["data"]["created_by"] == "USR-001"
    assert payload["data"]["current_stage"] == "PROJECT_CREATED"
    assert payload["workflow_stage"] == "PROJECT_CREATED"
    assert payload["data"]["status"] == "IN_PROGRESS"
    assert payload["data"]["created_at"] == payload["data"]["updated_at"]
    assert "PRJ-001" in repository.documents


def test_create_project_without_description_persists_empty_string(
    project_client,
) -> None:
    client, repository = project_client

    response = create_project(
        client,
        {"name": "Minimal project", "domain": "Education"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["description"] == ""
    assert repository.documents["PRJ-001"]["description"] == ""


def test_create_project_accepts_optional_description(project_client) -> None:
    client, _ = project_client

    response = create_project(client)

    assert response.status_code == 201
    assert response.json()["data"]["description"] == CREATE_PAYLOAD["description"]


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
        ("owner_user_id", "USR-002"),
        ("created_by", "USR-002"),
        ("current_stage", "COMPLETED"),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("updated_at", "2026-01-01T00:00:00Z"),
        ("status", "COMPLETED"),
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


def test_project_routes_require_authentication(authentication_context) -> None:
    client = authentication_context.anonymous_client()

    assert client.post("/api/v1/projects", json=CREATE_PAYLOAD).status_code == 401
    assert client.get("/api/v1/projects").status_code == 401
    assert client.get("/api/v1/projects/PRJ-001").status_code == 401
    assert client.patch(
        "/api/v1/projects/PRJ-001",
        json={"name": "Blocked"},
    ).status_code == 401


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("owner_user_id", "USR-002"),
        ("project_id", "PRJ-999"),
        ("current_stage", "COMPLETED"),
        ("status", "COMPLETED"),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("updated_at", "2026-01-01T00:00:00Z"),
    ],
)
def test_create_rejects_server_controlled_fields(
    project_client,
    field,
    value,
) -> None:
    client, repository = project_client

    response = create_project(
        client,
        {**CREATE_PAYLOAD, field: value},
    )

    assert response.status_code == 422
    assert repository.documents == {}


def test_create_rejects_client_controlled_creator(project_client) -> None:
    client, repository = project_client

    response = create_project(
        client,
        {**CREATE_PAYLOAD, "created_by": "USR-002"},
    )

    assert response.status_code == 422
    assert repository.documents == {}


@pytest.mark.parametrize("missing_field", ["name", "domain"])
def test_create_requires_name_and_domain(project_client, missing_field) -> None:
    client, repository = project_client
    payload = {
        "name": "Required fields project",
        "domain": "Education",
    }
    payload.pop(missing_field)

    response = create_project(client, payload)

    assert response.status_code == 422
    assert repository.documents == {}


def test_authenticated_user_cannot_impersonate_another_creator(
    project_client,
    authentication_context,
) -> None:
    _, repository = project_client
    owner_b_client = authentication_context.client("USR-002")

    rejected = create_project(
        owner_b_client,
        {**CREATE_PAYLOAD, "created_by": "USR-001"},
    )
    created = create_project(owner_b_client)

    assert rejected.status_code == 422
    assert created.status_code == 201
    project = created.json()["data"]
    assert project["created_by"] == "USR-002"
    assert project["owner_user_id"] == "USR-002"
    assert repository.documents["PRJ-001"]["created_by"] == "USR-002"


def test_project_listing_is_owner_scoped(
    project_client,
    authentication_context,
) -> None:
    owner_a_client, _ = project_client
    owner_b_client = authentication_context.client("USR-002")
    create_project(owner_a_client, {**CREATE_PAYLOAD, "name": "Owner A one"})
    create_project(owner_a_client, {**CREATE_PAYLOAD, "name": "Owner A two"})
    create_project(owner_b_client, {**CREATE_PAYLOAD, "name": "Owner B"})

    owner_a_projects = owner_a_client.get("/api/v1/projects").json()["data"]
    owner_b_projects = owner_b_client.get("/api/v1/projects").json()["data"]

    assert [item["project_id"] for item in owner_a_projects] == [
        "PRJ-001",
        "PRJ-002",
    ]
    assert [item["project_id"] for item in owner_b_projects] == ["PRJ-003"]
    assert {item["owner_user_id"] for item in owner_a_projects} == {"USR-001"}
    assert owner_b_projects[0]["owner_user_id"] == "USR-002"
    assert {item["created_by"] for item in owner_a_projects} == {"USR-001"}
    assert owner_b_projects[0]["created_by"] == "USR-002"


def test_project_get_retains_server_derived_creator(project_client) -> None:
    client, _ = project_client
    create_project(client)

    project = client.get("/api/v1/projects/PRJ-001").json()["data"]

    assert project["created_by"] == "USR-001"


def test_foreign_project_get_and_update_use_safe_not_found(
    project_client,
    authentication_context,
) -> None:
    owner_client, repository = project_client
    foreign_client = authentication_context.client("USR-002")
    create_project(owner_client)
    original = deepcopy(repository.documents["PRJ-001"])

    missing = foreign_client.get("/api/v1/projects/PRJ-999")
    foreign_get = foreign_client.get("/api/v1/projects/PRJ-001")
    foreign_patch = foreign_client.patch(
        "/api/v1/projects/PRJ-001",
        json={"name": "Foreign update"},
    )

    assert foreign_get.status_code == 404
    assert foreign_patch.status_code == 404
    assert foreign_get.json() == missing.json()
    assert repository.documents["PRJ-001"] == original


def test_legacy_ownerless_project_is_not_accessible(
    project_client,
) -> None:
    client, repository = project_client
    now = datetime.now(timezone.utc)
    repository.documents["PRJ-001"] = {
        "project_id": "PRJ-001",
        "name": "Legacy",
        "domain": "Legacy",
        "description": "No owner",
        "current_stage": "PROJECT_CREATED",
        "status": "IN_PROGRESS",
        "created_by": "legacy",
        "created_at": now,
        "updated_at": now,
    }

    assert client.get("/api/v1/projects/PRJ-001").status_code == 404


def test_project_repository_uses_projects_collection_and_strips_mongodb_id() -> None:
    now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    document = {
        "_id": "mongo-internal-id",
        "project_id": "PRJ-001",
        "owner_user_id": "USR-001",
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
            assert query == {"owner_user_id": "USR-001"}
            return [deepcopy(document)]

    class FakeDatabase:
        def __init__(self) -> None:
            self.requested_collection = None

        def __getitem__(self, collection_name):
            self.requested_collection = collection_name
            return FakeCollection()

    database = FakeDatabase()
    repository = ProjectRepository(database)

    projects = repository.list_projects("USR-001")

    assert database.requested_collection == PROJECTS
    assert projects[0]["project_id"] == "PRJ-001"
    assert "_id" not in projects[0]


def test_only_canonical_project_routes_are_registered() -> None:
    openapi_paths = app.openapi()["paths"]
    project_crud_paths = {
        "/api/v1/projects",
        "/api/v1/projects/{project_id}",
    }
    project_routes = {
        (method.upper(), path)
        for path, operations in openapi_paths.items()
        if path in project_crud_paths
        for method in operations
    }

    assert project_routes == {
        ("POST", "/api/v1/projects"),
        ("GET", "/api/v1/projects"),
        ("GET", "/api/v1/projects/{project_id}"),
        ("PATCH", "/api/v1/projects/{project_id}"),
    }


def test_all_current_project_scoped_routes_require_bearer_authentication() -> None:
    paths = app.openapi()["paths"]
    operations = {
        ("post", "/api/v1/projects"),
        ("get", "/api/v1/projects"),
        ("get", "/api/v1/projects/{project_id}"),
        ("patch", "/api/v1/projects/{project_id}"),
        ("post", "/api/v1/projects/{project_id}/inputs"),
        ("get", "/api/v1/projects/{project_id}/inputs"),
        (
            "post",
            "/api/v1/projects/{project_id}/orchestrator/next-step",
        ),
    }

    for method, path in operations:
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]


def test_project_request_schemas_protect_server_controlled_fields() -> None:
    schemas = app.openapi()["components"]["schemas"]
    create_schema = schemas["ProjectCreateRequest"]

    assert set(create_schema["properties"]) == {"name", "domain", "description"}
    assert set(create_schema["required"]) == {"name", "domain"}
    assert create_schema["properties"]["description"]["default"] == ""
    assert "owner_user_id" not in schemas["ProjectUpdateRequest"]["properties"]
    assert "created_by" not in schemas["ProjectUpdateRequest"]["properties"]


def test_swagger_and_openapi_remain_available(project_client) -> None:
    client, _ = project_client

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
