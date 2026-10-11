from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common.status import (
    ApprovalDecision,
    ApprovalGate,
    EventType,
    WorkflowStage,
)
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
from app.modules.orchestrator.policy import (
    STAGE_OWNERS,
    TRANSITIONS,
    get_transition,
    is_legal_transition,
)
from app.modules.orchestrator.router import get_orchestrator_repository
from app.schemas.approval import Approval
from app.schemas.workflow import WorkflowEvent


INITIAL_TIME = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)


APPROVAL_TRANSITION_CASES = [
    (
        ApprovalGate.H1,
        WorkflowStage.H1_WAITING_APPROVAL,
        WorkflowStage.DESIGN_IN_PROGRESS,
        "Project Management and Design Agent",
    ),
    (
        ApprovalGate.H2,
        WorkflowStage.H2_WAITING_APPROVAL,
        WorkflowStage.TEST_PLANNING_IN_PROGRESS,
        "Testing, Validation and Security Agent",
    ),
    (
        ApprovalGate.H3,
        WorkflowStage.H3_WAITING_APPROVAL,
        WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
        "Implementation and Git Automation Agent",
    ),
    (
        ApprovalGate.H4,
        WorkflowStage.H4_WAITING_APPROVAL,
        WorkflowStage.VALIDATION_IN_PROGRESS,
        "Testing, Validation and Security Agent",
    ),
    (
        ApprovalGate.H5,
        WorkflowStage.H5_WAITING_APPROVAL,
        WorkflowStage.COMPLETED,
        "Central SDLC Orchestrator / completed workflow",
    ),
]


def project_document(stage: WorkflowStage) -> dict[str, Any]:
    return {
        "project_id": "PRJ-001",
        "owner_user_id": "USR-001",
        "name": "Book Management System",
        "domain": "Library / Education",
        "description": "A controlled sample project",
        "current_stage": stage.value,
        "status": "IN_PROGRESS",
        "created_by": "foundation_user",
        "created_at": INITIAL_TIME,
        "updated_at": INITIAL_TIME,
    }


def approval_record(
    approval_id: str,
    gate: ApprovalGate,
    decision: ApprovalDecision,
    next_stage: WorkflowStage,
    *,
    project_id: str = "PRJ-001",
    offset_seconds: int = 0,
) -> Approval:
    return Approval(
        approval_id=approval_id,
        project_id=project_id,
        gate_id=gate,
        reviewer_role="Supervisor",
        decision=decision,
        comment="Reviewed.",
        timestamp=INITIAL_TIME + timedelta(seconds=offset_seconds),
        artifact_version=1,
        next_stage=next_stage,
    )


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
        self.approvals: list[Approval] = []
        self.client_inputs = (
            [{"project_id": "PRJ-001", "content": "Build a library app"}]
            if has_input
            else []
        )
        self.accessed_collections: set[str] = set()
        self.fail_get = False
        self.fail_event_insert = False

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        self.accessed_collections.add(PROJECTS)
        if self.fail_get:
            raise OrchestratorRepositoryError("private database detail")
        document = self.projects.get(project_id)
        return deepcopy(document) if document is not None else None

    def next_event_sequence(self) -> int:
        self.accessed_collections.add(WORKFLOW_EVENTS)
        return len(self.events) + 1

    def has_client_input(self, project_id: str) -> bool:
        self.accessed_collections.add(CLIENT_INPUTS)
        return any(
            item["project_id"] == project_id for item in self.client_inputs
        )

    def list_workflow_events(self, project_id: str) -> list[dict[str, Any]]:
        self.accessed_collections.add(WORKFLOW_EVENTS)
        return [
            event.model_dump(mode="python")
            for event in self.events
            if event.project_id == project_id
        ]

    def get_effective_approval(
        self,
        project_id: str,
        gate_id: ApprovalGate,
    ) -> dict[str, Any] | None:
        self.accessed_collections.add(APPROVALS)
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

    def persist_stage_change(
        self,
        project_id: str,
        owner_user_id: str,
        stage_before: WorkflowStage,
        stage_after: WorkflowStage,
        updated_at: datetime,
        event: WorkflowEvent,
    ) -> dict[str, Any] | None:
        self.accessed_collections.update({PROJECTS, WORKFLOW_EVENTS})
        document = self.projects.get(project_id)
        if (
            document is None
            or document.get("owner_user_id") != owner_user_id
            or document["current_stage"] != stage_before.value
        ):
            return None

        document["current_stage"] = stage_after.value
        document["updated_at"] = updated_at
        if self.fail_event_insert:
            raise OrchestratorRepositoryError("private event insert detail")

        self.events.append(event)
        return deepcopy(document)


@pytest.fixture
def orchestrator_client(authentication_context):
    repository = FakeOrchestratorRepository()
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        yield authentication_context.client(), repository
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)


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


def test_next_step_returns_not_found_for_missing_project(
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(stage=None)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-999/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 404
    assert response.json()["errors"] == [
        {"field": "project_id", "message": "Project not found"}
    ]


def test_project_created_without_client_input_cannot_advance(
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(has_input=False)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

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
        WorkflowStage.DESIGN_IN_PROGRESS,
        WorkflowStage.COMPLETED,
    ],
)
def test_unsupported_stage_does_not_advance(
    stage: WorkflowStage,
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(stage=stage)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 409
    payload = response.json()
    assert payload["success"] is False
    assert payload["workflow_stage"] == stage.value
    assert payload["errors"][0]["field"] == "current_stage"
    assert repository.projects["PRJ-001"]["current_stage"] == stage.value
    assert repository.events == []


@pytest.mark.parametrize(
    "gate,waiting_stage,target_stage,target_component",
    APPROVAL_TRANSITION_CASES,
)
def test_waiting_stage_without_effective_approval_is_blocked(
    gate: ApprovalGate,
    waiting_stage: WorkflowStage,
    target_stage: WorkflowStage,
    target_component: str,
    authentication_context,
) -> None:
    del gate, target_stage, target_component
    repository = FakeOrchestratorRepository(stage=waiting_stage)
    original = deepcopy(repository.projects["PRJ-001"])
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 409
    assert response.json()["errors"][0]["field"] == "approval"
    assert repository.projects["PRJ-001"] == original
    assert repository.events == []


@pytest.mark.parametrize(
    "gate,waiting_stage,target_stage,target_component",
    APPROVAL_TRANSITION_CASES,
)
def test_effective_approve_advances_and_creates_one_stage_event(
    gate: ApprovalGate,
    waiting_stage: WorkflowStage,
    target_stage: WorkflowStage,
    target_component: str,
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(stage=waiting_stage)
    approval = approval_record("APP-001", gate, ApprovalDecision.APPROVE, target_stage)
    repository.approvals.append(approval)
    original_approval = approval.model_copy(deep=True)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 200
    assert response.json()["data"] == {
        "project_id": "PRJ-001",
        "stage_before": waiting_stage.value,
        "stage_after": target_stage.value,
    }
    project = repository.projects["PRJ-001"]
    assert project["current_stage"] == target_stage.value
    assert project["updated_at"] > INITIAL_TIME
    assert project["status"] == "IN_PROGRESS"
    assert repository.approvals == [original_approval]
    assert len(repository.events) == 1

    event = repository.events[0]
    assert event.event_type is EventType.STAGE_CHANGED
    assert event.stage_before is waiting_stage
    assert event.stage_after is target_stage
    assert event.source_component == "Central SDLC Orchestrator"
    assert event.target_component == target_component
    assert event.metadata == {
        "approval_id": "APP-001",
        "gate_id": gate.value,
    }
    assert "Agent 1" not in event.target_component
    assert EventType.APPROVAL_DECISION not in [item.event_type for item in repository.events]


@pytest.mark.parametrize(
    "decision",
    [
        ApprovalDecision.REJECT,
        ApprovalDecision.REQUEST_CHANGES,
        ApprovalDecision.HOLD,
    ],
)
def test_effective_non_approve_blocks_without_mutation_or_event(
    decision: ApprovalDecision,
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(
        stage=WorkflowStage.H1_WAITING_APPROVAL
    )
    repository.approvals.append(
        approval_record(
            "APP-001",
            ApprovalGate.H1,
            decision,
            WorkflowStage.H1_WAITING_APPROVAL,
        )
    )
    original_project = deepcopy(repository.projects["PRJ-001"])
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 409
    assert repository.projects["PRJ-001"] == original_project
    assert repository.events == []


@pytest.mark.parametrize(
    ("older_decision", "newer_decision", "may_advance"),
    [
        (ApprovalDecision.REQUEST_CHANGES, ApprovalDecision.APPROVE, True),
        (ApprovalDecision.APPROVE, ApprovalDecision.REQUEST_CHANGES, False),
        (ApprovalDecision.APPROVE, ApprovalDecision.REJECT, False),
        (ApprovalDecision.APPROVE, ApprovalDecision.HOLD, False),
    ],
)
def test_only_latest_approval_controls_progression(
    older_decision: ApprovalDecision,
    newer_decision: ApprovalDecision,
    may_advance: bool,
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(
        stage=WorkflowStage.H1_WAITING_APPROVAL
    )
    repository.approvals.extend(
        [
            approval_record(
                "APP-001",
                ApprovalGate.H1,
                older_decision,
                (
                    WorkflowStage.DESIGN_IN_PROGRESS
                    if older_decision is ApprovalDecision.APPROVE
                    else WorkflowStage.H1_WAITING_APPROVAL
                ),
            ),
            approval_record(
                "APP-002",
                ApprovalGate.H1,
                newer_decision,
                (
                    WorkflowStage.DESIGN_IN_PROGRESS
                    if newer_decision is ApprovalDecision.APPROVE
                    else WorkflowStage.H1_WAITING_APPROVAL
                ),
                offset_seconds=1,
            ),
        ]
    )
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == (200 if may_advance else 409)
    assert repository.projects["PRJ-001"]["current_stage"] == (
        "DESIGN_IN_PROGRESS" if may_advance else "H1_WAITING_APPROVAL"
    )
    assert len(repository.events) == (1 if may_advance else 0)


def test_approve_with_noncanonical_next_stage_is_blocked(
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(
        stage=WorkflowStage.H1_WAITING_APPROVAL
    )
    repository.approvals.append(
        approval_record(
            "APP-001",
            ApprovalGate.H1,
            ApprovalDecision.APPROVE,
            WorkflowStage.COMPLETED,
        )
    )
    original = deepcopy(repository.projects["PRJ-001"])
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 409
    assert repository.projects["PRJ-001"] == original
    assert repository.events == []


@pytest.mark.parametrize(
    "gate,waiting_stage,target_stage,target_component",
    APPROVAL_TRANSITION_CASES,
)
@pytest.mark.parametrize(
    "decision,available",
    [
        (None, False),
        (ApprovalDecision.APPROVE, True),
        (ApprovalDecision.REJECT, False),
        (ApprovalDecision.REQUEST_CHANGES, False),
        (ApprovalDecision.HOLD, False),
    ],
)
def test_snapshot_reports_effective_approval_availability_without_writes(
    gate: ApprovalGate,
    waiting_stage: WorkflowStage,
    target_stage: WorkflowStage,
    target_component: str,
    decision: ApprovalDecision | None,
    available: bool,
    authentication_context,
) -> None:
    del target_component
    repository = FakeOrchestratorRepository(stage=waiting_stage)
    if decision is not None:
        repository.approvals.append(
            approval_record(
                "APP-001",
                gate,
                decision,
                (
                    target_stage
                    if decision is ApprovalDecision.APPROVE
                    else waiting_stage
                ),
            )
        )
    original_project = deepcopy(repository.projects["PRJ-001"])
    original_approvals = deepcopy(repository.approvals)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().get(
            "/api/v1/projects/PRJ-001/workflow"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["current_stage"] == waiting_stage.value
    assert data["next_stage"] == target_stage.value
    assert data["next_transition_available"] is available
    assert repository.projects["PRJ-001"] == original_project
    assert repository.approvals == original_approvals
    assert repository.events == []


def test_other_project_approval_cannot_enable_transition(
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(
        stage=WorkflowStage.H1_WAITING_APPROVAL
    )
    repository.approvals.append(
        approval_record(
            "APP-001",
            ApprovalGate.H1,
            ApprovalDecision.APPROVE,
            WorkflowStage.DESIGN_IN_PROGRESS,
            project_id="PRJ-002",
        )
    )
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().post(
            "/api/v1/projects/PRJ-001/orchestrator/next-step"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 409
    assert repository.projects["PRJ-001"]["current_stage"] == (
        "H1_WAITING_APPROVAL"
    )
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


def test_next_step_requires_authentication(authentication_context) -> None:
    response = authentication_context.anonymous_client().post(
        "/api/v1/projects/PRJ-001/orchestrator/next-step"
    )

    assert response.status_code == 401


def test_foreign_user_cannot_advance_project(
    orchestrator_client,
    authentication_context,
) -> None:
    _, repository = orchestrator_client
    original_project = deepcopy(repository.projects["PRJ-001"])

    response = authentication_context.client("USR-002").post(
        "/api/v1/projects/PRJ-001/orchestrator/next-step"
    )

    assert response.status_code == 404
    assert repository.projects["PRJ-001"] == original_project
    assert repository.events == []


def test_transition_does_not_change_another_project(
    orchestrator_client,
) -> None:
    client, repository = orchestrator_client
    second_project = project_document(WorkflowStage.PROJECT_CREATED)
    second_project["project_id"] = "PRJ-002"
    repository.projects["PRJ-002"] = second_project

    response = client.post(
        "/api/v1/projects/PRJ-001/orchestrator/next-step"
    )

    assert response.status_code == 200
    assert repository.projects["PRJ-001"]["current_stage"] == (
        "REQUIREMENTS_IN_PROGRESS"
    )
    assert repository.projects["PRJ-002"]["current_stage"] == "PROJECT_CREATED"


def test_transition_policy_contains_the_canonical_forward_sequence() -> None:
    stages = list(WorkflowStage)

    assert set(STAGE_OWNERS) == set(stages)
    assert [transition.source_stage for transition in TRANSITIONS] == stages[:-1]
    assert [transition.target_stage for transition in TRANSITIONS] == stages[1:]
    assert all(
        is_legal_transition(source, target)
        for source, target in zip(stages, stages[1:])
    )


def test_stage_ownership_uses_only_official_component_names() -> None:
    assert STAGE_OWNERS[WorkflowStage.PROJECT_CREATED] == (
        "Central SDLC Orchestrator / shared foundation"
    )
    assert STAGE_OWNERS[WorkflowStage.REQUIREMENTS_IN_PROGRESS] == (
        "Requirement Gathering and Analysis Agent"
    )
    assert STAGE_OWNERS[WorkflowStage.DESIGN_IN_PROGRESS] == (
        "Project Management and Design Agent"
    )
    assert STAGE_OWNERS[WorkflowStage.TEST_PLANNING_IN_PROGRESS] == (
        "Testing, Validation and Security Agent"
    )
    assert STAGE_OWNERS[WorkflowStage.IMPLEMENTATION_IN_PROGRESS] == (
        "Implementation and Git Automation Agent"
    )
    assert STAGE_OWNERS[WorkflowStage.VALIDATION_IN_PROGRESS] == (
        "Testing, Validation and Security Agent"
    )
    assert all(
        "Human approval managed by Central SDLC Orchestrator"
        == STAGE_OWNERS[stage]
        for stage in (
            WorkflowStage.H1_WAITING_APPROVAL,
            WorkflowStage.H2_WAITING_APPROVAL,
            WorkflowStage.H3_WAITING_APPROVAL,
            WorkflowStage.H4_WAITING_APPROVAL,
            WorkflowStage.H5_WAITING_APPROVAL,
        )
    )
    assert not any(
        forbidden in owner
        for owner in STAGE_OWNERS.values()
        for forbidden in (
            "Agent 1",
            "Agent 2",
            "Agent 3",
            "Agent 4",
            "Pre-Code Test Planning Agent",
        )
    )


def test_o1_and_approval_driven_transitions_are_executable() -> None:
    executable = [transition for transition in TRANSITIONS if transition.executable]

    assert [
        (transition.source_stage, transition.target_stage)
        for transition in executable
    ] == [
        (
            WorkflowStage.PROJECT_CREATED,
            WorkflowStage.REQUIREMENTS_IN_PROGRESS,
        ),
        (
            WorkflowStage.H1_WAITING_APPROVAL,
            WorkflowStage.DESIGN_IN_PROGRESS,
        ),
        (
            WorkflowStage.H2_WAITING_APPROVAL,
            WorkflowStage.TEST_PLANNING_IN_PROGRESS,
        ),
        (
            WorkflowStage.H3_WAITING_APPROVAL,
            WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
        ),
        (
            WorkflowStage.H4_WAITING_APPROVAL,
            WorkflowStage.VALIDATION_IN_PROGRESS,
        ),
        (
            WorkflowStage.H5_WAITING_APPROVAL,
            WorkflowStage.COMPLETED,
        ),
    ]
    for stage in (
        WorkflowStage.REQUIREMENTS_IN_PROGRESS,
        WorkflowStage.DESIGN_IN_PROGRESS,
        WorkflowStage.TEST_PLANNING_IN_PROGRESS,
        WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
        WorkflowStage.VALIDATION_IN_PROGRESS,
    ):
        transition = get_transition(stage)
        assert transition is not None
        assert transition.executable is False


def test_workflow_snapshot_reports_available_first_transition(
    orchestrator_client,
) -> None:
    client, repository = orchestrator_client
    original_project = deepcopy(repository.projects["PRJ-001"])

    response = client.get("/api/v1/projects/PRJ-001/workflow")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "project_id": "PRJ-001",
        "current_stage": "PROJECT_CREATED",
        "current_stage_owner": (
            "Central SDLC Orchestrator / shared foundation"
        ),
        "next_stage": "REQUIREMENTS_IN_PROGRESS",
        "next_stage_owner": "Requirement Gathering and Analysis Agent",
        "next_transition_available": True,
        "approval_gate": None,
    }
    assert repository.projects["PRJ-001"] == original_project
    assert repository.events == []


def test_workflow_snapshot_reports_unsatisfied_client_input(
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(has_input=False)
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().get(
            "/api/v1/projects/PRJ-001/workflow"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 200
    assert response.json()["data"]["next_stage"] == "REQUIREMENTS_IN_PROGRESS"
    assert response.json()["data"]["next_transition_available"] is False


def test_workflow_snapshot_shows_structural_but_unavailable_later_transition(
    authentication_context,
) -> None:
    repository = FakeOrchestratorRepository(
        stage=WorkflowStage.REQUIREMENTS_IN_PROGRESS
    )
    app.dependency_overrides[get_orchestrator_repository] = lambda: repository
    try:
        response = authentication_context.client().get(
            "/api/v1/projects/PRJ-001/workflow"
        )
    finally:
        app.dependency_overrides.pop(get_orchestrator_repository, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["next_stage"] == "H1_WAITING_APPROVAL"
    assert data["next_stage_owner"] == (
        "Human approval managed by Central SDLC Orchestrator"
    )
    assert data["approval_gate"] == "H1"
    assert data["next_transition_available"] is False


def test_workflow_snapshot_requires_owner_authentication(
    orchestrator_client,
    authentication_context,
) -> None:
    anonymous = authentication_context.anonymous_client().get(
        "/api/v1/projects/PRJ-001/workflow"
    )
    foreign = authentication_context.client("USR-002").get(
        "/api/v1/projects/PRJ-001/workflow"
    )
    missing = orchestrator_client[0].get(
        "/api/v1/projects/PRJ-999/workflow"
    )

    assert anonymous.status_code == 401
    assert foreign.status_code == 404
    assert missing.status_code == 404
    assert foreign.json() == missing.json()


def test_workflow_snapshot_is_project_specific(orchestrator_client) -> None:
    client, repository = orchestrator_client
    second = project_document(WorkflowStage.REQUIREMENTS_IN_PROGRESS)
    second["project_id"] = "PRJ-002"
    repository.projects["PRJ-002"] = second

    first_snapshot = client.get("/api/v1/projects/PRJ-001/workflow").json()[
        "data"
    ]
    second_snapshot = client.get("/api/v1/projects/PRJ-002/workflow").json()[
        "data"
    ]

    assert first_snapshot["current_stage"] == "PROJECT_CREATED"
    assert second_snapshot["current_stage"] == "REQUIREMENTS_IN_PROGRESS"


def _event(
    event_id: str,
    project_id: str,
    created_at: datetime,
) -> WorkflowEvent:
    return WorkflowEvent(
        event_id=event_id,
        project_id=project_id,
        event_type=EventType.STAGE_CHANGED,
        source_component="Central SDLC Orchestrator",
        target_component="Requirement Gathering and Analysis Agent",
        stage_before=WorkflowStage.PROJECT_CREATED,
        stage_after=WorkflowStage.REQUIREMENTS_IN_PROGRESS,
        message="Test transition",
        created_at=created_at,
    )


def test_event_history_is_scoped_ordered_and_public(orchestrator_client) -> None:
    client, repository = orchestrator_client
    repository.events.extend(
        [
            _event("EVT-003", "PRJ-001", datetime(2026, 1, 3, tzinfo=timezone.utc)),
            _event("EVT-001", "PRJ-001", datetime(2026, 1, 1, tzinfo=timezone.utc)),
            _event("EVT-002", "PRJ-002", datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ]
    )

    response = client.get("/api/v1/projects/PRJ-001/events")

    assert response.status_code == 200
    assert [item["event_id"] for item in response.json()["data"]] == [
        "EVT-001",
        "EVT-003",
    ]
    assert all("_id" not in item for item in response.json()["data"])


def test_event_history_empty_and_requires_owner_authentication(
    orchestrator_client,
    authentication_context,
) -> None:
    client, _ = orchestrator_client

    empty = client.get("/api/v1/projects/PRJ-001/events")
    anonymous = authentication_context.anonymous_client().get(
        "/api/v1/projects/PRJ-001/events"
    )
    foreign = authentication_context.client("USR-002").get(
        "/api/v1/projects/PRJ-001/events"
    )

    assert empty.status_code == 200
    assert empty.json()["data"] == []
    assert anonymous.status_code == 401
    assert foreign.status_code == 404


def test_event_history_missing_project_matches_foreign_not_found(
    orchestrator_client,
    authentication_context,
) -> None:
    owner_client, _ = orchestrator_client

    missing = owner_client.get("/api/v1/projects/PRJ-999/events")
    foreign = authentication_context.client("USR-002").get(
        "/api/v1/projects/PRJ-001/events"
    )

    assert missing.status_code == 404
    assert foreign.status_code == 404
    assert missing.json() == foreign.json()


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
        APPROVALS,
    ]


def test_exact_orchestrator_route_and_existing_project_routes() -> None:
    paths = app.openapi()["paths"]
    orchestrator_operations = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path
        in {
            "/api/v1/projects/{project_id}/workflow",
            "/api/v1/projects/{project_id}/orchestrator/next-step",
            "/api/v1/projects/{project_id}/events",
        }
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
        ("GET", "/api/v1/projects/{project_id}/workflow"),
        ("POST", "/api/v1/projects/{project_id}/orchestrator/next-step"),
        ("GET", "/api/v1/projects/{project_id}/events"),
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
