from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common.status import (
    ApprovalDecision,
    ApprovalGate,
    EventType,
    WorkflowStage,
)
from app.database.collections import APPROVALS, PROJECTS, WORKFLOW_EVENTS
from app.main import app
from app.modules.approvals.repository import (
    ApprovalRepository,
    ApprovalRepositoryError,
)
from app.modules.approvals.router import get_approval_repository
from app.modules.orchestrator.policy import TRANSITIONS
from app.modules.orchestrator.router import get_orchestrator_repository
from app.schemas.approval import Approval
from app.schemas.workflow import WorkflowEvent


INITIAL_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


GATE_CASES = [
    (
        "h1",
        ApprovalGate.H1,
        WorkflowStage.H1_WAITING_APPROVAL,
        WorkflowStage.DESIGN_IN_PROGRESS,
    ),
    (
        "h2",
        ApprovalGate.H2,
        WorkflowStage.H2_WAITING_APPROVAL,
        WorkflowStage.TEST_PLANNING_IN_PROGRESS,
    ),
    (
        "h3",
        ApprovalGate.H3,
        WorkflowStage.H3_WAITING_APPROVAL,
        WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
    ),
    (
        "h4",
        ApprovalGate.H4,
        WorkflowStage.H4_WAITING_APPROVAL,
        WorkflowStage.VALIDATION_IN_PROGRESS,
    ),
    (
        "h5",
        ApprovalGate.H5,
        WorkflowStage.H5_WAITING_APPROVAL,
        WorkflowStage.COMPLETED,
    ),
]


def project_document(
    project_id: str = "PRJ-001",
    owner_user_id: str = "USR-001",
    stage: WorkflowStage = WorkflowStage.H1_WAITING_APPROVAL,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "owner_user_id": owner_user_id,
        "name": "Approval Test Project",
        "domain": "Testing",
        "description": "Project used for O2 tests",
        "current_stage": stage.value,
        "status": "IN_PROGRESS",
        "created_by": "test_user",
        "created_at": INITIAL_TIME,
        "updated_at": INITIAL_TIME,
    }


class FakeApprovalRepository:
    def __init__(
        self,
        stage: WorkflowStage = WorkflowStage.H1_WAITING_APPROVAL,
    ) -> None:
        self.projects = {"PRJ-001": project_document(stage=stage)}
        self.approvals: list[Approval] = []
        self.events: list[WorkflowEvent] = []
        self.fail_persist = False

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        document = self.projects.get(project_id)
        return deepcopy(document) if document is not None else None

    def next_approval_sequence(self) -> int:
        sequences = [
            int(approval.approval_id.rsplit("-", 1)[1])
            for approval in self.approvals
        ]
        return max(sequences, default=0) + 1

    def next_event_sequence(self) -> int:
        sequences = [
            int(event.event_id.rsplit("-", 1)[1]) for event in self.events
        ]
        return max(sequences, default=0) + 1

    def create_approval_with_event(
        self,
        approval: Approval,
        event: WorkflowEvent,
    ) -> dict[str, Any]:
        if self.fail_persist:
            raise ApprovalRepositoryError("private database detail")
        self.approvals.append(approval)
        self.events.append(event)
        document = approval.model_dump(mode="python")
        document["_id"] = "internal-only"
        return {key: value for key, value in document.items() if key != "_id"}

    def get_effective_approval(
        self,
        project_id: str,
        gate_id: ApprovalGate,
    ) -> dict[str, Any] | None:
        matches = [
            approval
            for approval in self.approvals
            if approval.project_id == project_id and approval.gate_id is gate_id
        ]
        if not matches:
            return None
        latest = max(
            matches,
            key=lambda approval: (approval.timestamp, approval.approval_id),
        )
        return latest.model_dump(mode="python")

    def list_workflow_events(self, project_id: str) -> list[dict[str, Any]]:
        return [
            event.model_dump(mode="python")
            for event in self.events
            if event.project_id == project_id
        ]

    def has_client_input(self, project_id: str) -> bool:
        del project_id
        return False


@pytest.fixture
def approval_context(authentication_context):
    repository = FakeApprovalRepository()
    app.dependency_overrides[get_approval_repository] = lambda: repository
    try:
        yield authentication_context.client(), repository
    finally:
        app.dependency_overrides.pop(get_approval_repository, None)


def approval_body(**overrides: Any) -> dict[str, Any]:
    body = {
        "reviewer_name": "Human Reviewer",
        "decision": "APPROVE",
        "comment": "Reviewed.",
        "artifact_version": 1,
    }
    body.update(overrides)
    return body


@pytest.mark.parametrize(
    "reviewer_fields",
    [
        {"reviewer_name": "Reviewer"},
        {"reviewer_name": None, "reviewer_role": "Supervisor"},
        {"reviewer_name": "Reviewer", "reviewer_role": "Supervisor"},
    ],
)
def test_reviewer_identity_variants_are_accepted(
    reviewer_fields: dict[str, Any],
    approval_context,
) -> None:
    client, repository = approval_context

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(**reviewer_fields),
    )

    assert response.status_code == 201
    assert len(repository.approvals) == 1


@pytest.mark.parametrize(
    ("body", "field"),
    [
        (
            {
                "decision": "APPROVE",
                "comment": "Reviewed.",
                "artifact_version": 1,
            },
            "request",
        ),
        (
            {
                "reviewer_name": "Reviewer",
                "comment": "Reviewed.",
                "artifact_version": 1,
            },
            "decision",
        ),
        (approval_body(decision="APPROVED"), "decision"),
        (
            {
                "reviewer_name": "Reviewer",
                "decision": "APPROVE",
                "artifact_version": 1,
            },
            "comment",
        ),
        (
            {
                "reviewer_name": "Reviewer",
                "decision": "APPROVE",
                "comment": "Reviewed.",
            },
            "artifact_version",
        ),
        (approval_body(artifact_version=0), "artifact_version"),
        (approval_body(artifact_version=-1), "artifact_version"),
    ],
)
def test_invalid_approval_request_is_rejected(
    body: dict[str, Any],
    field: str,
    approval_context,
) -> None:
    client, repository = approval_context

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=body,
    )

    assert response.status_code == 422
    assert any(error["field"] == field for error in response.json()["errors"])
    assert repository.approvals == []
    assert repository.events == []


@pytest.mark.parametrize(
    "field",
    [
        "approval_id",
        "project_id",
        "gate_id",
        "timestamp",
        "next_stage",
        "artifact_type",
        "reviewer_user_id",
    ],
)
def test_server_or_unapproved_request_fields_are_rejected(
    field: str,
    approval_context,
) -> None:
    client, repository = approval_context
    values = {
        "approval_id": "APP-999",
        "project_id": "PRJ-999",
        "gate_id": "H5",
        "timestamp": "2026-01-01T00:00:00Z",
        "next_stage": "COMPLETED",
        "artifact_type": "REQUIREMENTS",
        "reviewer_user_id": "USR-001",
    }

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(**{field: values[field]}),
    )

    assert response.status_code == 422
    assert repository.approvals == []


def test_approval_requires_authentication(authentication_context) -> None:
    response = authentication_context.anonymous_client().post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(),
    )

    assert response.status_code == 401


def test_missing_and_foreign_projects_share_safe_not_found(
    approval_context,
    authentication_context,
) -> None:
    owner_client, repository = approval_context

    missing = owner_client.post(
        "/api/v1/projects/PRJ-999/approvals/h1",
        json=approval_body(),
    )
    foreign = authentication_context.client("USR-002").post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(),
    )

    assert missing.status_code == 404
    assert foreign.status_code == 404
    assert missing.json() == foreign.json()
    assert repository.approvals == []


@pytest.mark.parametrize("path,gate,waiting_stage,approved_next", GATE_CASES)
def test_each_gate_requires_its_waiting_stage_and_derives_approve_next_stage(
    path: str,
    gate: ApprovalGate,
    waiting_stage: WorkflowStage,
    approved_next: WorkflowStage,
    authentication_context,
) -> None:
    repository = FakeApprovalRepository(stage=waiting_stage)
    app.dependency_overrides[get_approval_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            f"/api/v1/projects/PRJ-001/approvals/{path}",
            json=approval_body(),
        )
    finally:
        app.dependency_overrides.pop(get_approval_repository, None)

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["gate_id"] == gate.value
    assert data["next_stage"] == approved_next.value
    assert repository.projects["PRJ-001"]["current_stage"] == waiting_stage.value


def test_wrong_stage_returns_conflict_without_writes(approval_context) -> None:
    client, repository = approval_context

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h2",
        json=approval_body(),
    )

    assert response.status_code == 409
    assert response.json()["workflow_stage"] == "H1_WAITING_APPROVAL"
    assert repository.approvals == []
    assert repository.events == []


@pytest.mark.parametrize(
    "decision",
    ["REJECT", "REQUEST_CHANGES", "HOLD"],
)
@pytest.mark.parametrize(
    ("path", "waiting_stage"),
    [(path, waiting_stage) for path, _, waiting_stage, _ in GATE_CASES],
)
def test_non_approve_decisions_remain_at_waiting_stage(
    path: str,
    waiting_stage: WorkflowStage,
    decision: str,
    authentication_context,
) -> None:
    repository = FakeApprovalRepository(stage=waiting_stage)
    app.dependency_overrides[get_approval_repository] = lambda: repository
    original_project = deepcopy(repository.projects["PRJ-001"])
    try:
        response = authentication_context.client().post(
            f"/api/v1/projects/PRJ-001/approvals/{path}",
            json=approval_body(decision=decision),
        )
    finally:
        app.dependency_overrides.pop(get_approval_repository, None)

    assert response.status_code == 201
    assert response.json()["data"]["next_stage"] == waiting_stage.value
    assert repository.projects["PRJ-001"] == original_project


def test_success_persists_safe_approval_and_exactly_one_audit_event(
    approval_context,
) -> None:
    client, repository = approval_context
    original_project = deepcopy(repository.projects["PRJ-001"])

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(
            reviewer_role="Supervisor",
            comment="Sensitive review detail",
            artifact_version=3,
        ),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["workflow_stage"] is None
    assert payload["data"]["approval_id"] == "APP-001"
    assert "_id" not in payload["data"]
    assert repository.projects["PRJ-001"] == original_project
    assert len(repository.approvals) == 1
    assert len(repository.events) == 1

    event = repository.events[0]
    assert event.event_id == "EVT-001"
    assert event.event_type is EventType.APPROVAL_DECISION
    assert event.source_component == "Human Stakeholder / Reviewer"
    assert event.target_component == "Central SDLC Orchestrator"
    assert event.stage_before is WorkflowStage.H1_WAITING_APPROVAL
    assert event.stage_after is WorkflowStage.H1_WAITING_APPROVAL
    assert event.metadata == {
        "approval_id": "APP-001",
        "gate_id": "H1",
        "decision": "APPROVE",
        "artifact_version": 3,
    }
    assert "Sensitive review detail" not in event.message
    assert EventType.STAGE_CHANGED not in [item.event_type for item in repository.events]


@pytest.mark.parametrize("initial_decision", ["REQUEST_CHANGES", "HOLD"])
def test_append_only_history_and_effective_decision(
    initial_decision: str,
    approval_context,
) -> None:
    client, repository = approval_context

    first = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(decision=initial_decision),
    )
    first_record = repository.approvals[0].model_copy(deep=True)
    second = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(decision="APPROVE", artifact_version=2),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert len(repository.approvals) == 2
    assert repository.approvals[0] == first_record
    assert [item.approval_id for item in repository.approvals] == [
        "APP-001",
        "APP-002",
    ]
    effective = repository.get_effective_approval("PRJ-001", ApprovalGate.H1)
    assert effective is not None
    assert effective["approval_id"] == "APP-002"
    assert effective["decision"] is ApprovalDecision.APPROVE


def test_allocation_increments_existing_maximum(approval_context) -> None:
    client, repository = approval_context
    repository.approvals.append(
        Approval(
            approval_id="APP-012",
            project_id="PRJ-001",
            gate_id=ApprovalGate.H1,
            reviewer_role="Supervisor",
            decision=ApprovalDecision.HOLD,
            comment="Paused.",
            timestamp=INITIAL_TIME,
            artifact_version=1,
            next_stage=WorkflowStage.H1_WAITING_APPROVAL,
        )
    )

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(),
    )

    assert response.status_code == 201
    assert response.json()["data"]["approval_id"] == "APP-013"


def test_repository_failure_returns_safe_503(approval_context) -> None:
    client, repository = approval_context
    repository.fail_persist = True

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(),
    )

    assert response.status_code == 503
    assert "private database detail" not in response.text


def test_multi_project_approval_isolation(approval_context) -> None:
    client, repository = approval_context
    repository.projects["PRJ-002"] = project_document("PRJ-002")

    response = client.post(
        "/api/v1/projects/PRJ-001/approvals/h1",
        json=approval_body(),
    )

    assert response.status_code == 201
    assert all(item.project_id == "PRJ-001" for item in repository.approvals)
    assert repository.get_effective_approval("PRJ-002", ApprovalGate.H1) is None
    assert repository.projects["PRJ-002"]["current_stage"] == (
        "H1_WAITING_APPROVAL"
    )


def test_o2_approval_post_does_not_transition_but_enables_o3_snapshot(
    approval_context,
) -> None:
    client, repository = approval_context
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        created = client.post(
            "/api/v1/projects/PRJ-001/approvals/h1",
            json=approval_body(),
        )
        snapshot = client.get("/api/v1/projects/PRJ-001/workflow")
        history = client.get("/api/v1/projects/PRJ-001/events")
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert created.status_code == 201
    assert snapshot.status_code == 200
    assert snapshot.json()["data"]["current_stage"] == "H1_WAITING_APPROVAL"
    assert snapshot.json()["data"]["next_transition_available"] is True
    assert history.status_code == 200
    assert history.json()["data"][0]["event_type"] == "APPROVAL_DECISION"
    assert sum(transition.executable for transition in TRANSITIONS) == 11


def test_repository_uses_only_approval_collections() -> None:
    class FakeCollection:
        pass

    class FakeDatabase:
        def __init__(self) -> None:
            self.requested_collections: list[str] = []

        def __getitem__(self, name: str) -> FakeCollection:
            self.requested_collections.append(name)
            return FakeCollection()

    database = FakeDatabase()

    ApprovalRepository(database)  # type: ignore[arg-type]

    assert database.requested_collections == [
        PROJECTS,
        APPROVALS,
        WORKFLOW_EVENTS,
    ]


def test_repository_effective_approval_uses_deterministic_latest_order() -> None:
    expected = {
        "approval_id": "APP-002",
        "project_id": "PRJ-001",
        "gate_id": "H1",
    }

    class FakeCursor:
        def __init__(self) -> None:
            self.sort_spec: list[tuple[str, int]] | None = None
            self.limit_value: int | None = None

        def sort(self, spec: list[tuple[str, int]]) -> "FakeCursor":
            self.sort_spec = spec
            return self

        def limit(self, value: int) -> "FakeCursor":
            self.limit_value = value
            return self

        def __iter__(self):
            return iter([expected])

    class FakeCollection:
        def __init__(self) -> None:
            self.cursor = FakeCursor()
            self.query: dict[str, str] | None = None

        def find(self, query, projection):
            self.query = query
            assert projection == {"_id": 0}
            return self.cursor

    class FakeDatabase:
        def __init__(self) -> None:
            self.collections = {
                PROJECTS: FakeCollection(),
                APPROVALS: FakeCollection(),
                WORKFLOW_EVENTS: FakeCollection(),
            }

        def __getitem__(self, name: str) -> FakeCollection:
            return self.collections[name]

    database = FakeDatabase()
    repository = ApprovalRepository(database)  # type: ignore[arg-type]

    result = repository.get_effective_approval("PRJ-001", ApprovalGate.H1)

    approval_collection = database.collections[APPROVALS]
    assert result == expected
    assert approval_collection.query == {
        "project_id": "PRJ-001",
        "gate_id": "H1",
    }
    assert approval_collection.cursor.sort_spec == [
        ("timestamp", -1),
        ("approval_id", -1),
    ]
    assert approval_collection.cursor.limit_value == 1


def test_exact_five_authenticated_approval_post_routes() -> None:
    paths = app.openapi()["paths"]
    approval_operations = {
        (method.upper(), path)
        for path, operations in paths.items()
        if "/approvals/" in path
        for method in operations
    }

    assert approval_operations == {
        ("POST", f"/api/v1/projects/{{project_id}}/approvals/h{gate}")
        for gate in range(1, 6)
    }
    for _, path in approval_operations:
        operation = paths[path]["post"]
        assert operation["security"] == [{"HTTPBearer": []}]
