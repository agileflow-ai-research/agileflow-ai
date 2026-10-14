from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.common.id_generator import generate_id, validate_id
from app.main import app
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.repository import (
    AgentProjectRepository,
    AgentRunRepository,
)
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from app.modules.standalone.schemas import (
    AgentProject,
    AgentProjectCreateRequest,
    AgentProjectStatus,
    AgentProjectUpdateRequest,
    AgentRun,
    AgentRunMessage,
    AgentRunMode,
    AgentRunStatus,
    AgentType,
)
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    AgentRunNotFoundError,
    AgentRunTransitionError,
    ArchivedAgentProjectError,
    InvalidAgentRunModeError,
    StandaloneService,
)


NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
CREATE_PAYLOAD = {
    "agent_type": "REQUIREMENTS",
    "name": "BookEase Requirements",
    "domain": "Library",
    "description": "Standalone requirements workspace",
}


class FakeAgentProjectRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    def next_project_sequence(self) -> int:
        sequences = []
        for project_id in self.documents:
            try:
                validate_id(project_id, "AGP")
            except ValueError:
                continue
            sequences.append(int(project_id.rsplit("-", 1)[1]))
        return max(sequences, default=0) + 1

    def create_project(self, project: AgentProject) -> dict[str, Any]:
        document = project.model_dump(mode="python")
        self.documents[project.agent_project_id] = {
            **deepcopy(document),
            "_id": f"mongo-{project.agent_project_id}",
        }
        return deepcopy(document)

    def list_projects(
        self,
        owner_user_id: str,
        *,
        agent_type: AgentType | None = None,
        status: AgentProjectStatus | None = None,
    ) -> list[dict[str, Any]]:
        documents = [
            document
            for document in self.documents.values()
            if document.get("owner_user_id") == owner_user_id
            and (
                agent_type is None
                or document.get("agent_type") == agent_type
            )
            and (status is None or document.get("status") == status)
        ]
        documents.sort(
            key=lambda item: (item["created_at"], item["agent_project_id"]),
            reverse=True,
        )
        return [self._public(document) for document in documents]

    def get_project(
        self,
        agent_project_id: str,
        owner_user_id: str,
    ) -> dict[str, Any] | None:
        document = self.documents.get(agent_project_id)
        if document is None or document.get("owner_user_id") != owner_user_id:
            return None
        return self._public(document)

    def update_project(
        self,
        agent_project_id: str,
        owner_user_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        document = self.documents.get(agent_project_id)
        if document is None or document.get("owner_user_id") != owner_user_id:
            return None
        document.update(deepcopy(updates))
        return self._public(document)

    @staticmethod
    def _public(document: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(
            {key: value for key, value in document.items() if key != "_id"}
        )


class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    def next_run_sequence(self) -> int:
        sequences = []
        for run_id in self.documents:
            try:
                validate_id(run_id, "RUN")
            except ValueError:
                continue
            sequences.append(int(run_id.rsplit("-", 1)[1]))
        return max(sequences, default=0) + 1

    def create_run(self, run: AgentRun) -> dict[str, Any]:
        document = run.model_dump(mode="python")
        self.documents[run.run_id] = {
            **deepcopy(document),
            "_id": f"mongo-{run.run_id}",
        }
        return deepcopy(document)

    def list_runs(
        self,
        owner_user_id: str,
        agent_project_id: str,
    ) -> list[dict[str, Any]]:
        documents = [
            document
            for document in self.documents.values()
            if document.get("owner_user_id") == owner_user_id
            and document.get("agent_project_id") == agent_project_id
        ]
        documents.sort(
            key=lambda item: (item["created_at"], item["run_id"]),
            reverse=True,
        )
        return [self._public(document) for document in documents]

    def get_run(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
    ) -> dict[str, Any] | None:
        document = self.documents.get(run_id)
        if (
            document is None
            or document.get("owner_user_id") != owner_user_id
            or document.get("agent_project_id") != agent_project_id
        ):
            return None
        return self._public(document)

    def update_run_state(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
        expected_status: AgentRunStatus,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        document = self.documents.get(run_id)
        if (
            document is None
            or document.get("owner_user_id") != owner_user_id
            or document.get("agent_project_id") != agent_project_id
            or document.get("status") != expected_status
        ):
            return None
        document.update(deepcopy(updates))
        return self._public(document)

    @staticmethod
    def _public(document: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(
            {key: value for key, value in document.items() if key != "_id"}
        )


class TickingClock:
    def __init__(self, value: datetime = NOW) -> None:
        self.value = value

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def user(user_id: str = "USR-001") -> UserPublicResponse:
    return UserPublicResponse(
        user_id=user_id,
        name=f"User {user_id}",
        email=f"{user_id.lower()}@example.com",
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def standalone_repositories():
    return FakeAgentProjectRepository(), FakeAgentRunRepository()


@pytest.fixture
def standalone_service(standalone_repositories) -> StandaloneService:
    project_repository, run_repository = standalone_repositories
    return StandaloneService(
        project_repository,
        run_repository,
        clock=TickingClock(),
    )


@pytest.fixture
def standalone_client(authentication_context, standalone_repositories):
    project_repository, run_repository = standalone_repositories
    app.dependency_overrides[get_agent_project_repository] = (
        lambda: project_repository
    )
    app.dependency_overrides[get_agent_run_repository] = lambda: run_repository
    try:
        yield authentication_context.client(), project_repository, run_repository
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)


def create_request(
    agent_type: AgentType = AgentType.REQUIREMENTS,
    name: str = "Standalone project",
) -> AgentProjectCreateRequest:
    return AgentProjectCreateRequest(
        agent_type=agent_type,
        name=name,
        domain="Education",
    )


def create_project(
    service: StandaloneService,
    agent_type: AgentType = AgentType.REQUIREMENTS,
    owner: str = "USR-001",
) -> AgentProject:
    return service.create_project(create_request(agent_type), user(owner))


def create_run(
    service: StandaloneService,
    project: AgentProject,
    run_mode: AgentRunMode = AgentRunMode.DEFAULT,
) -> AgentRun:
    return service.create_run(
        project.owner_user_id,
        project.agent_project_id,
        run_mode,
        ["SAMPLE_OUTPUT"],
        {"requirement": "The system shall work."},
    )


def test_standalone_enum_values_are_exact() -> None:
    assert [item.value for item in AgentType] == [
        "REQUIREMENTS",
        "DESIGN_PLANNING",
        "IMPLEMENTATION",
        "TESTING_VALIDATION",
    ]
    assert [item.value for item in AgentProjectStatus] == [
        "ACTIVE",
        "ARCHIVED",
    ]
    assert [item.value for item in AgentRunStatus] == [
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
    ]
    assert [item.value for item in AgentRunMode] == [
        "DEFAULT",
        "TEST_GENERATION",
        "VALIDATION",
    ]


def test_agp_and_run_are_canonical_id_prefixes() -> None:
    assert generate_id("AGP", 1) == "AGP-001"
    assert generate_id("AGP", 2) == "AGP-002"
    assert generate_id("RUN", 1) == "RUN-001"
    assert generate_id("RUN", 2) == "RUN-002"


@pytest.mark.parametrize("agent_type", list(AgentType))
def test_create_each_agent_project_type(
    standalone_service: StandaloneService,
    agent_type: AgentType,
) -> None:
    project = create_project(standalone_service, agent_type)

    assert project.agent_type is agent_type
    assert project.owner_user_id == "USR-001"
    assert project.status is AgentProjectStatus.ACTIVE
    assert project.description == ""
    assert project.created_at == project.updated_at


def test_project_allocation_ignores_unrelated_identifiers(
    standalone_service: StandaloneService,
    standalone_repositories,
) -> None:
    projects, _ = standalone_repositories
    projects.documents["PRJ-999"] = {"agent_project_id": "PRJ-999"}

    first = create_project(standalone_service)
    second = create_project(standalone_service)

    assert first.agent_project_id == "AGP-001"
    assert second.agent_project_id == "AGP-002"


@pytest.mark.parametrize("field", ["name", "domain"])
def test_project_request_rejects_blank_required_fields(field: str) -> None:
    payload = deepcopy(CREATE_PAYLOAD)
    payload[field] = "   "
    with pytest.raises(ValidationError, match="must not be blank"):
        AgentProjectCreateRequest.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    [
        "agent_project_id",
        "owner_user_id",
        "status",
        "created_at",
        "updated_at",
    ],
)
def test_create_api_rejects_protected_fields(
    standalone_client,
    field: str,
) -> None:
    client, projects, _ = standalone_client
    response = client.post(
        "/api/v1/agent-projects",
        json={**CREATE_PAYLOAD, field: "protected"},
    )

    assert response.status_code == 422
    assert projects.documents == {}


def test_create_get_and_list_projects_are_owner_scoped(
    standalone_client,
    authentication_context,
) -> None:
    owner_client, _, _ = standalone_client
    foreign_client = authentication_context.client("USR-002")

    first = owner_client.post(
        "/api/v1/agent-projects", json=CREATE_PAYLOAD
    )
    second = foreign_client.post(
        "/api/v1/agent-projects",
        json={**CREATE_PAYLOAD, "name": "Foreign"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["owner_user_id"] == "USR-001"
    assert second.json()["data"]["owner_user_id"] == "USR-002"
    assert [
        item["agent_project_id"]
        for item in owner_client.get("/api/v1/agent-projects").json()["data"]
    ] == ["AGP-001"]
    missing = foreign_client.get("/api/v1/agent-projects/AGP-999")
    foreign = foreign_client.get("/api/v1/agent-projects/AGP-001")
    assert foreign.status_code == 404
    assert foreign.json() == missing.json()


def test_project_list_is_newest_first_and_supports_simple_filters(
    standalone_client,
) -> None:
    client, _, _ = standalone_client
    client.post("/api/v1/agent-projects", json=CREATE_PAYLOAD)
    client.post(
        "/api/v1/agent-projects",
        json={
            **CREATE_PAYLOAD,
            "agent_type": "IMPLEMENTATION",
            "name": "Implementation",
        },
    )
    client.patch(
        "/api/v1/agent-projects/AGP-001",
        json={"status": "ARCHIVED"},
    )

    all_ids = [
        item["agent_project_id"]
        for item in client.get("/api/v1/agent-projects").json()["data"]
    ]
    type_ids = [
        item["agent_project_id"]
        for item in client.get(
            "/api/v1/agent-projects?agent_type=IMPLEMENTATION"
        ).json()["data"]
    ]
    status_ids = [
        item["agent_project_id"]
        for item in client.get(
            "/api/v1/agent-projects?status=ARCHIVED"
        ).json()["data"]
    ]

    assert all_ids == ["AGP-002", "AGP-001"]
    assert type_ids == ["AGP-002"]
    assert status_ids == ["AGP-001"]


def test_patch_updates_only_mutable_fields_and_timestamp(
    standalone_service: StandaloneService,
) -> None:
    project = create_project(standalone_service)
    updated = standalone_service.update_project(
        project.agent_project_id,
        AgentProjectUpdateRequest(
            name="Updated",
            description="Updated description",
            domain="Updated domain",
        ),
        user(),
    )

    assert updated.name == "Updated"
    assert updated.description == "Updated description"
    assert updated.domain == "Updated domain"
    assert updated.agent_type is project.agent_type
    assert updated.owner_user_id == project.owner_user_id
    assert updated.created_at == project.created_at
    assert updated.updated_at > project.updated_at


@pytest.mark.parametrize(
    "field,value",
    [
        ("agent_project_id", "AGP-999"),
        ("owner_user_id", "USR-002"),
        ("agent_type", "IMPLEMENTATION"),
        ("created_at", "2026-10-14T09:00:00Z"),
        ("updated_at", "2026-10-14T09:00:00Z"),
    ],
)
def test_patch_api_rejects_immutable_fields(
    standalone_client,
    field: str,
    value: str,
) -> None:
    client, _, _ = standalone_client
    client.post("/api/v1/agent-projects", json=CREATE_PAYLOAD)

    response = client.patch(
        "/api/v1/agent-projects/AGP-001",
        json={field: value},
    )

    assert response.status_code == 422


def test_archive_read_reactivate_and_active_guard(
    standalone_service: StandaloneService,
) -> None:
    project = create_project(standalone_service)
    archived = standalone_service.update_project(
        project.agent_project_id,
        AgentProjectUpdateRequest(status=AgentProjectStatus.ARCHIVED),
        user(),
    )

    assert archived.status is AgentProjectStatus.ARCHIVED
    assert standalone_service.get_project(project.agent_project_id, user())
    with pytest.raises(ArchivedAgentProjectError):
        standalone_service.require_active_project(
            "USR-001", project.agent_project_id
        )

    active = standalone_service.update_project(
        project.agent_project_id,
        AgentProjectUpdateRequest(status=AgentProjectStatus.ACTIVE),
        user(),
    )
    assert active.status is AgentProjectStatus.ACTIVE
    assert standalone_service.require_active_project(
        "USR-001", project.agent_project_id
    )


@pytest.mark.parametrize(
    "agent_type,run_mode",
    [
        (AgentType.REQUIREMENTS, AgentRunMode.DEFAULT),
        (AgentType.DESIGN_PLANNING, AgentRunMode.DEFAULT),
        (AgentType.IMPLEMENTATION, AgentRunMode.DEFAULT),
        (AgentType.TESTING_VALIDATION, AgentRunMode.TEST_GENERATION),
        (AgentType.TESTING_VALIDATION, AgentRunMode.VALIDATION),
    ],
)
def test_internal_run_creation_accepts_compatible_modes(
    standalone_service: StandaloneService,
    agent_type: AgentType,
    run_mode: AgentRunMode,
) -> None:
    project = create_project(standalone_service, agent_type)
    snapshot = {"nested": {"value": 1}}
    run = standalone_service.create_run(
        "USR-001",
        project.agent_project_id,
        run_mode,
        ["OUTPUT"],
        snapshot,
    )

    snapshot["nested"]["value"] = 99
    assert run.run_id.startswith("RUN-")
    assert run.agent_type is agent_type
    assert run.owner_user_id == project.owner_user_id
    assert run.status is AgentRunStatus.QUEUED
    assert run.input_snapshot == {"nested": {"value": 1}}
    assert run.output_manifest == {}
    assert run.started_at is None
    assert run.completed_at is None


@pytest.mark.parametrize(
    "agent_type,run_mode",
    [
        (AgentType.REQUIREMENTS, AgentRunMode.TEST_GENERATION),
        (AgentType.DESIGN_PLANNING, AgentRunMode.VALIDATION),
        (AgentType.IMPLEMENTATION, AgentRunMode.TEST_GENERATION),
        (AgentType.TESTING_VALIDATION, AgentRunMode.DEFAULT),
    ],
)
def test_internal_run_creation_rejects_incompatible_modes(
    standalone_service: StandaloneService,
    agent_type: AgentType,
    run_mode: AgentRunMode,
) -> None:
    project = create_project(standalone_service, agent_type)
    with pytest.raises(InvalidAgentRunModeError):
        standalone_service.create_run(
            "USR-001",
            project.agent_project_id,
            run_mode,
            ["OUTPUT"],
            {},
        )


def test_run_creation_requires_output_active_project_and_owner(
    standalone_service: StandaloneService,
) -> None:
    project = create_project(standalone_service)
    with pytest.raises(ValueError, match="selected_outputs"):
        standalone_service.create_run(
            "USR-001", project.agent_project_id, AgentRunMode.DEFAULT, [], {}
        )
    with pytest.raises(AgentProjectNotFoundError):
        standalone_service.create_run(
            "USR-002",
            project.agent_project_id,
            AgentRunMode.DEFAULT,
            ["OUTPUT"],
            {},
        )

    standalone_service.update_project(
        project.agent_project_id,
        AgentProjectUpdateRequest(status=AgentProjectStatus.ARCHIVED),
        user(),
    )
    with pytest.raises(ArchivedAgentProjectError):
        create_run(standalone_service, project)


def test_run_allocation_uses_only_run_collection(
    standalone_service: StandaloneService,
    standalone_repositories,
) -> None:
    projects, runs = standalone_repositories
    projects.documents["AGP-777"] = {"agent_project_id": "AGP-777"}
    runs.documents["EVT-999"] = {"run_id": "EVT-999"}
    project = create_project(standalone_service)

    first = create_run(standalone_service, project)
    second = create_run(standalone_service, project)

    assert first.run_id == "RUN-001"
    assert second.run_id == "RUN-002"


def test_queued_running_completed_lifecycle_preserves_immutable_fields(
    standalone_service: StandaloneService,
) -> None:
    project = create_project(standalone_service)
    queued = create_run(standalone_service, project)
    immutable = queued.model_dump(
        include={
            "run_id",
            "agent_project_id",
            "owner_user_id",
            "agent_type",
            "run_mode",
            "selected_outputs",
            "input_snapshot",
            "created_at",
        },
        mode="python",
    )

    running = standalone_service.mark_run_running(
        "USR-001", project.agent_project_id, queued.run_id
    )
    completed = standalone_service.complete_run(
        "USR-001",
        project.agent_project_id,
        queued.run_id,
        {"SRS": {"reference": "artifact-1"}},
        [AgentRunMessage(code="LIMITATION", message="One warning")],
    )

    assert running.status is AgentRunStatus.RUNNING
    assert running.started_at is not None
    assert running.completed_at is None
    assert completed.status is AgentRunStatus.COMPLETED
    assert completed.started_at == running.started_at
    assert completed.completed_at is not None
    assert completed.output_manifest["SRS"]["reference"] == "artifact-1"
    assert completed.errors == []
    assert completed.model_dump(include=set(immutable), mode="python") == immutable


def test_queued_running_failed_lifecycle_persists_errors_and_partial_evidence(
    standalone_service: StandaloneService,
) -> None:
    project = create_project(standalone_service)
    queued = create_run(standalone_service, project)
    running = standalone_service.mark_run_running(
        "USR-001", project.agent_project_id, queued.run_id
    )
    failed = standalone_service.fail_run(
        "USR-001",
        project.agent_project_id,
        queued.run_id,
        [
            AgentRunMessage(
                code="INTERNAL_ERROR",
                message="Execution failed safely",
                details={"correlation_id": "test-1"},
            )
        ],
        output_manifest={"partial": True},
        warnings=[
            AgentRunMessage(code="LIMITATION", message="Partial output")
        ],
    )

    assert failed.status is AgentRunStatus.FAILED
    assert failed.started_at == running.started_at
    assert failed.completed_at is not None
    assert failed.errors[0].code == "INTERNAL_ERROR"
    assert failed.output_manifest == {"partial": True}
    assert failed.input_snapshot == queued.input_snapshot


def test_fail_run_requires_error_and_illegal_transitions_are_rejected(
    standalone_service: StandaloneService,
) -> None:
    project = create_project(standalone_service)
    queued = create_run(standalone_service, project)

    with pytest.raises(ValueError, match="at least one error"):
        standalone_service.fail_run(
            "USR-001", project.agent_project_id, queued.run_id, []
        )
    with pytest.raises(AgentRunTransitionError):
        standalone_service.complete_run(
            "USR-001", project.agent_project_id, queued.run_id, {}
        )

    standalone_service.mark_run_running(
        "USR-001", project.agent_project_id, queued.run_id
    )
    standalone_service.complete_run(
        "USR-001", project.agent_project_id, queued.run_id, {}
    )
    with pytest.raises(AgentRunTransitionError):
        standalone_service.mark_run_running(
            "USR-001", project.agent_project_id, queued.run_id
        )
    with pytest.raises(AgentRunTransitionError):
        standalone_service.fail_run(
            "USR-001",
            project.agent_project_id,
            queued.run_id,
            [AgentRunMessage(code="ERROR", message="Too late")],
        )


def test_agent_run_schema_enforces_timestamp_consistency() -> None:
    base = {
        "run_id": "RUN-001",
        "agent_project_id": "AGP-001",
        "owner_user_id": "USR-001",
        "agent_type": "REQUIREMENTS",
        "run_mode": "DEFAULT",
        "selected_outputs": ["SRS"],
        "input_snapshot": {},
        "created_at": NOW,
    }
    with pytest.raises(ValidationError, match="QUEUED"):
        AgentRun(**base, status="QUEUED", started_at=NOW)
    with pytest.raises(ValidationError, match="RUNNING"):
        AgentRun(**base, status="RUNNING")
    with pytest.raises(ValidationError, match="terminal"):
        AgentRun(**base, status="COMPLETED", started_at=NOW)
    with pytest.raises(ValidationError, match="at least one error"):
        AgentRun(
            **base,
            status="FAILED",
            started_at=NOW,
            completed_at=NOW,
        )

    with pytest.raises(ValidationError, match="not valid"):
        AgentRun(
            **{**base, "agent_type": "TESTING_VALIDATION"},
            status="QUEUED",
        )


def test_agent_run_message_is_structured_and_serializable() -> None:
    message = AgentRunMessage(
        code="TOOL_EXECUTION_FAILED",
        message="Tool could not run",
        details={"attempt": 1, "retryable": False},
    )
    assert message.details == {"attempt": 1, "retryable": False}
    with pytest.raises(ValidationError):
        AgentRunMessage(code=" ", message="message")
    with pytest.raises(ValidationError):
        AgentRunMessage(code="ERROR", message=" ")
    with pytest.raises(ValidationError):
        AgentRunMessage(
            code="ERROR",
            message="message",
            details={"unsupported": object()},
        )


def test_run_history_is_newest_first_and_project_user_isolated(
    standalone_service: StandaloneService,
) -> None:
    first_project = create_project(standalone_service)
    second_project = create_project(standalone_service)
    foreign_project = create_project(
        standalone_service,
        owner="USR-002",
    )
    first_run = create_run(standalone_service, first_project)
    second_run = create_run(standalone_service, first_project)
    create_run(standalone_service, second_project)
    create_run(standalone_service, foreign_project)

    history = standalone_service.list_runs(first_project.agent_project_id, user())

    assert [run.run_id for run in history] == [
        second_run.run_id,
        first_run.run_id,
    ]
    assert {run.agent_project_id for run in history} == {
        first_project.agent_project_id
    }
    assert {run.owner_user_id for run in history} == {"USR-001"}


def test_get_run_requires_owner_project_and_run_identity(
    standalone_service: StandaloneService,
) -> None:
    first_project = create_project(standalone_service)
    second_project = create_project(standalone_service)
    run = create_run(standalone_service, first_project)

    assert (
        standalone_service.get_run(
            first_project.agent_project_id, run.run_id, user()
        ).run_id
        == run.run_id
    )
    with pytest.raises(AgentRunNotFoundError):
        standalone_service.get_run(
            second_project.agent_project_id, run.run_id, user()
        )
    with pytest.raises(AgentProjectNotFoundError):
        standalone_service.get_run(
            first_project.agent_project_id, run.run_id, user("USR-002")
        )


def test_public_run_history_and_get_strip_mongodb_id(
    standalone_client,
) -> None:
    client, projects, runs = standalone_client
    created = client.post(
        "/api/v1/agent-projects", json=CREATE_PAYLOAD
    ).json()["data"]
    service = StandaloneService(projects, runs)
    run = service.create_run(
        "USR-001",
        created["agent_project_id"],
        AgentRunMode.DEFAULT,
        ["SRS"],
        {"text": "requirements"},
    )

    history = client.get(
        f"/api/v1/agent-projects/{created['agent_project_id']}/runs"
    )
    detail = client.get(
        f"/api/v1/agent-projects/{created['agent_project_id']}/runs/{run.run_id}"
    )

    assert history.status_code == 200
    assert detail.status_code == 200
    assert "_id" not in history.json()["data"][0]
    assert "_id" not in detail.json()["data"]


def test_get_run_reports_the_invalid_path_field(standalone_client) -> None:
    client, _, _ = standalone_client

    invalid_project = client.get(
        "/api/v1/agent-projects/not-an-agp/runs/RUN-001"
    )
    invalid_run = client.get(
        "/api/v1/agent-projects/AGP-001/runs/not-a-run"
    )

    assert invalid_project.status_code == 422
    assert invalid_project.json()["errors"][0]["field"] == "agent_project_id"
    assert invalid_run.status_code == 422
    assert invalid_run.json()["errors"][0]["field"] == "run_id"


def test_standalone_public_routes_require_authentication(
    authentication_context,
) -> None:
    client = authentication_context.anonymous_client()
    assert client.post("/api/v1/agent-projects", json=CREATE_PAYLOAD).status_code == 401
    assert client.get("/api/v1/agent-projects").status_code == 401
    assert client.get("/api/v1/agent-projects/AGP-001").status_code == 401
    assert client.patch(
        "/api/v1/agent-projects/AGP-001", json={"status": "ARCHIVED"}
    ).status_code == 401
    assert client.get(
        "/api/v1/agent-projects/AGP-001/runs"
    ).status_code == 401
    assert client.get(
        "/api/v1/agent-projects/AGP-001/runs/RUN-001"
    ).status_code == 401


def test_only_six_common_standalone_operations_are_public() -> None:
    paths = app.openapi()["paths"]
    standalone_operations = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith("/api/v1/agent-projects")
        for method in operations
    }
    assert standalone_operations == {
        ("POST", "/api/v1/agent-projects"),
        ("GET", "/api/v1/agent-projects"),
        ("GET", "/api/v1/agent-projects/{agent_project_id}"),
        ("PATCH", "/api/v1/agent-projects/{agent_project_id}"),
        ("GET", "/api/v1/agent-projects/{agent_project_id}/runs"),
        (
            "GET",
            "/api/v1/agent-projects/{agent_project_id}/runs/{run_id}",
        ),
    }


def test_openapi_create_and_update_hide_protected_fields() -> None:
    schemas = app.openapi()["components"]["schemas"]
    create_properties = schemas["AgentProjectCreateRequest"]["properties"]
    update_properties = schemas["AgentProjectUpdateRequest"]["properties"]

    assert set(create_properties) == {
        "agent_type",
        "name",
        "domain",
        "description",
    }
    assert set(update_properties) == {"name", "description", "domain", "status"}
    for protected in (
        "agent_project_id",
        "owner_user_id",
        "agent_type",
        "created_at",
        "updated_at",
    ):
        assert protected not in update_properties


def test_repository_classes_use_only_standalone_collections() -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.requested: list[str] = []

        def __getitem__(self, name: str):
            self.requested.append(name)
            return object()

    database = FakeDatabase()
    AgentProjectRepository(database)
    AgentRunRepository(database)

    assert database.requested == ["agent_projects", "agent_runs"]


def test_standalone_models_contain_no_integrated_workflow_fields() -> None:
    prohibited = {
        "project_id",
        "workflow_stage",
        "approval_gate",
        "next_stage",
        "handoff_ready",
    }
    assert not prohibited.intersection(AgentProject.model_fields)
    assert not prohibited.intersection(AgentRun.model_fields)
