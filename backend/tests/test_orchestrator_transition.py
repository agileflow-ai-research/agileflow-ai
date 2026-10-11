from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common.status import EventType, WorkflowStage
from app.database.collections import (
    APPROVALS,
    CLIENT_INPUTS,
    PROJECTS,
    REQUIREMENTS,
    WORKFLOW_EVENTS,
)
from app.main import app
from app.modules.orchestrator.repository import (
    OrchestratorRepository,
    OrchestratorRepositoryError,
)
from app.modules.orchestrator.router import get_orchestrator_repository
from app.schemas.workflow import WorkflowEvent


INITIAL_TIME = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)


def project_document(stage: WorkflowStage) -> dict[str, Any]:
    return {
        "project_id": "PRJ-001",
        "name": "Book Management System",
        "domain": "Library / Education",
        "description": "A controlled sample project",
        "current_stage": stage.value,
        "status": "IN_PROGRESS",
        "created_by": "foundation_user",
        "created_at": INITIAL_TIME,
        "updated_at": INITIAL_TIME,
    }


class FakeOrchestratorRepository:
    def __init__(
        self,
        stage: WorkflowStage | None = WorkflowStage.PROJECT_CREATED,
        has_input: bool = True,
    ):
        self.projects = (
            {"PRJ-001": project_document(stage)} if stage is not None else {}
        )
        self.events: list[WorkflowEvent] = []
        self.client_inputs = (
            [{"project_id": "PRJ-001", "content": "Build a library app"}]
            if has_input
            else []
        )
        self.accessed_collections = {PROJECTS, CLIENT_INPUTS, WORKFLOW_EVENTS}
        self.fail_get = False
        self.fail_event_insert = False

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        if self.fail_get:
            raise OrchestratorRepositoryError("private database detail")
        document = self.projects.get(project_id)
        return deepcopy(document) if document is not None else None

    def next_event_sequence(self) -> int:
        return len(self.events) + 1

    def has_client_input(self, project_id: str) -> bool:
        return any(
            item["project_id"] == project_id for item in self.client_inputs
        )

    def persist_stage_change(
        self,
        project_id: str,
        stage_before: WorkflowStage,
        stage_after: WorkflowStage,
        updated_at: datetime,
        event: WorkflowEvent,
    ) -> dict[str, Any] | None:
        document = self.projects.get(project_id)
        if document is None or document["current_stage"] != stage_before.value:
            return None

        document["current_stage"] = stage_after.value
        document["updated_at"] = updated_at
        if self.fail_event_insert:
            raise OrchestratorRepositoryError("private event insert detail")

        self.events.append(event)
        return deepcopy(document)


@pytest.fixture
def orchestrator_client():
    repository = FakeOrchestratorRepository()
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        yield TestClient(app), repository
    finally:
        app.dependency_overrides.clear()


def test_valid_first_transition_updates_project_and_creates_event(
    orchestrator_client,
) -> None:
    client, repository = orchestrator_client

    response = client.post(
        "/api/v1/projects/PRJ-001/orchestrator/next-step"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "project_id": "PRJ-001",
        "stage_before": "PROJECT_CREATED",
        "stage_after": "REQUIREMENTS_IN_PROGRESS",
    }
    assert payload["workflow_stage"] == "REQUIREMENTS_IN_PROGRESS"
    assert payload["next_action"] is None
    assert repository.projects["PRJ-001"]["current_stage"] == (
        "REQUIREMENTS_IN_PROGRESS"
    )
    assert repository.projects["PRJ-001"]["created_at"] == INITIAL_TIME
    assert repository.projects["PRJ-001"]["status"] == "IN_PROGRESS"
    assert repository.projects["PRJ-001"]["updated_at"] > INITIAL_TIME

    assert len(repository.events) == 1
    event = repository.events[0]
    assert event.event_id == "EVT-001"
    assert event.event_type is EventType.STAGE_CHANGED
    assert event.stage_before is WorkflowStage.PROJECT_CREATED
    assert event.stage_after is WorkflowStage.REQUIREMENTS_IN_PROGRESS
    assert event.source_component == "Central SDLC Orchestrator"
    assert event.target_component == "Requirement Gathering and Analysis Agent"
    assert event.metadata == {}


def test_next_step_rejects_invalid_project_id(orchestrator_client) -> None:
    client, repository = orchestrator_client

    response = client.post(
        "/api/v1/projects/REQ-001/orchestrator/next-step"
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "project_id"
    assert repository.events == []


def test_next_step_returns_not_found_for_missing_project() -> None:
    repository = FakeOrchestratorRepository(stage=None)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = TestClient(app).post(
            "/api/v1/projects/PRJ-999/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["errors"] == [
        {"field": "project_id", "message": "Project not found"}
    ]


def test_project_created_without_client_input_cannot_advance() -> None:
    repository = FakeOrchestratorRepository(has_input=False)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = TestClient(app).post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    payload = response.json()
    assert payload["success"] is False
    assert payload["workflow_stage"] == "PROJECT_CREATED"
    assert payload["errors"][0]["field"] == "client_input"
    assert repository.projects["PRJ-001"]["current_stage"] == "PROJECT_CREATED"
    assert repository.events == []


@pytest.mark.parametrize(
    "stage",
    [
        WorkflowStage.REQUIREMENTS_IN_PROGRESS,
        WorkflowStage.H1_WAITING_APPROVAL,
        WorkflowStage.COMPLETED,
    ],
)
def test_unsupported_stage_does_not_advance(stage: WorkflowStage) -> None:
    repository = FakeOrchestratorRepository(stage=stage)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = TestClient(app).post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    payload = response.json()
    assert payload["success"] is False
    assert payload["workflow_stage"] == stage.value
    assert payload["errors"][0]["field"] == "current_stage"
    assert repository.projects["PRJ-001"]["current_stage"] == stage.value
    assert repository.events == []


def test_transition_does_not_create_approvals_or_requirements(
    orchestrator_client,
) -> None:
    client, repository = orchestrator_client

    response = client.post(
        "/api/v1/projects/PRJ-001/orchestrator/next-step"
    )

    assert response.status_code == 200
    assert repository.accessed_collections == {
        PROJECTS,
        CLIENT_INPUTS,
        WORKFLOW_EVENTS,
    }
    assert APPROVALS not in repository.accessed_collections
    assert REQUIREMENTS not in repository.accessed_collections
    assert response.json()["data"]["stage_after"] != "H1_WAITING_APPROVAL"


def test_repository_failure_is_safe(orchestrator_client) -> None:
    client, repository = orchestrator_client
    repository.fail_get = True

    response = client.post(
        "/api/v1/projects/PRJ-001/orchestrator/next-step"
    )

    assert response.status_code == 503
    assert "private database detail" not in response.text
    assert response.json()["errors"][0]["field"] == "database"


def test_event_failure_is_reported_after_stage_update(orchestrator_client) -> None:
    client, repository = orchestrator_client
    repository.fail_event_insert = True

    response = client.post(
        "/api/v1/projects/PRJ-001/orchestrator/next-step"
    )

    assert response.status_code == 503
    assert "private event insert detail" not in response.text
    assert repository.projects["PRJ-001"]["current_stage"] == (
        "REQUIREMENTS_IN_PROGRESS"
    )
    assert repository.events == []


def test_repository_selects_only_canonical_transition_collections() -> None:
    class FakeCollection:
        pass

    class FakeDatabase:
        def __init__(self) -> None:
            self.requested_collections: list[str] = []

        def __getitem__(self, collection_name: str) -> FakeCollection:
            self.requested_collections.append(collection_name)
            return FakeCollection()

    database = FakeDatabase()

    OrchestratorRepository(database)

    assert database.requested_collections == [
        PROJECTS,
        CLIENT_INPUTS,
        WORKFLOW_EVENTS,
    ]


def test_exact_orchestrator_route_and_existing_project_routes() -> None:
    paths = app.openapi()["paths"]
    orchestrator_operations = {
        (method.upper(), path)
        for path, operations in paths.items()
        if "/orchestrator/" in path
        for method in operations
    }
    project_operations = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path
        in {
            "/api/v1/projects",
            "/api/v1/projects/{project_id}",
        }
        for method in operations
    }

    assert orchestrator_operations == {
        ("POST", "/api/v1/projects/{project_id}/orchestrator/next-step")
    }
    assert project_operations == {
        ("POST", "/api/v1/projects"),
        ("GET", "/api/v1/projects"),
        ("GET", "/api/v1/projects/{project_id}"),
        ("PATCH", "/api/v1/projects/{project_id}"),
    }


def test_health_swagger_and_openapi_remain_available(orchestrator_client) -> None:
    client, _ = orchestrator_client

    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
