from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.common.id_generator import generate_id
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.common.traceability import TraceabilityRelationType
from app.common.status import (
    ApprovalDecision,
    ApprovalGate,
    ArtifactStatus,
    EventType,
    WorkflowStage,
)
from app.schemas import (
    AcceptanceCriteria,
    Agent1ArtifactType,
    Approval,
    BaseArtifact,
    Persona,
    Project,
    QualityFinding,
    QualityFindingType,
    Requirement,
    RequirementKind,
    SrsDocument,
    TraceabilityLink,
    UserStory,
    WorkflowEvent,
)


NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def enum_values(enum_type) -> list[str]:
    return [item.value for item in enum_type]


def test_workflow_stage_values() -> None:
    assert enum_values(WorkflowStage) == [
        "PROJECT_CREATED",
        "REQUIREMENTS_IN_PROGRESS",
        "H1_WAITING_APPROVAL",
        "DESIGN_IN_PROGRESS",
        "H2_WAITING_APPROVAL",
        "TEST_PLANNING_IN_PROGRESS",
        "H3_WAITING_APPROVAL",
        "IMPLEMENTATION_IN_PROGRESS",
        "H4_WAITING_APPROVAL",
        "VALIDATION_IN_PROGRESS",
        "H5_WAITING_APPROVAL",
        "COMPLETED",
    ]


def test_artifact_status_values() -> None:
    assert enum_values(ArtifactStatus) == [
        "PENDING",
        "IN_PROGRESS",
        "WAITING_FOR_APPROVAL",
        "APPROVED",
        "REJECTED",
        "REQUEST_CHANGES",
        "FAILED",
        "RETRYING",
        "COMPLETED",
    ]


def test_approval_gate_values() -> None:
    assert enum_values(ApprovalGate) == ["H1", "H2", "H3", "H4", "H5"]


def test_approval_decision_values() -> None:
    assert enum_values(ApprovalDecision) == [
        "APPROVE",
        "REJECT",
        "REQUEST_CHANGES",
        "HOLD",
    ]


def test_event_type_values_are_limited_to_documented_types() -> None:
    assert enum_values(EventType) == [
        "AGENT_STARTED",
        "ARTIFACT_GENERATED",
        "APPROVAL_DECISION",
        "FAILURE_ROUTED",
        "RETRY_ATTEMPT",
        "STAGE_CHANGED",
    ]


def test_agent1_traceability_relation_values() -> None:
    assert enum_values(TraceabilityRelationType) == [
        "DERIVED_FROM",
        "REFINES",
        "ACCEPTANCE_CRITERION_FOR",
        "IDENTIFIES_ISSUE_IN",
        "RELATED_TO",
    ]


def test_generate_id_is_deterministic_and_zero_padded() -> None:
    assert generate_id("USR", 1) == "USR-001"
    assert generate_id("PRJ", 1) == "PRJ-001"
    assert generate_id("REQ", 12) == "REQ-012"
    assert generate_id("APP", 3) == "APP-003"
    assert generate_id("EVT", 1000) == "EVT-1000"


def test_generate_id_rejects_unapproved_prefix() -> None:
    with pytest.raises(ValueError, match="Unsupported ID prefix"):
        generate_id("UNKNOWN", 1)


def test_project_schema_accepts_documented_fields() -> None:
    project = Project(
        project_id="PRJ-001",
        owner_user_id="USR-001",
        name="Book Management System",
        domain="Library / Education",
        description="A controlled sample project",
        current_stage=WorkflowStage.PROJECT_CREATED,
        status=ArtifactStatus.IN_PROGRESS,
        created_by="foundation_user",
        created_at=NOW,
        updated_at=NOW,
    )

    assert project.project_id == "PRJ-001"
    assert project.current_stage is WorkflowStage.PROJECT_CREATED
    assert set(Project.model_fields) == {
        "project_id",
        "owner_user_id",
        "name",
        "domain",
        "description",
        "current_stage",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    }


def test_project_schema_rejects_invalid_project_id() -> None:
    with pytest.raises(ValidationError):
        Project(
            project_id="REQ-001",
            owner_user_id="USR-001",
            name="Book Management System",
            domain="Library / Education",
            description="A controlled sample project",
            current_stage=WorkflowStage.PROJECT_CREATED,
            status=ArtifactStatus.IN_PROGRESS,
            created_by="foundation_user",
            created_at=NOW,
            updated_at=NOW,
        )


def test_project_schema_rejects_invalid_owner_user_id() -> None:
    with pytest.raises(ValidationError):
        Project(
            project_id="PRJ-001",
            owner_user_id="PRJ-001",
            name="Book Management System",
            domain="Library / Education",
            description="A controlled sample project",
            current_stage=WorkflowStage.PROJECT_CREATED,
            status=ArtifactStatus.IN_PROGRESS,
            created_by="foundation_user",
            created_at=NOW,
            updated_at=NOW,
        )


def test_approval_schema_valid_case() -> None:
    approval = Approval(
        approval_id="APP-003",
        project_id="PRJ-001",
        gate_id=ApprovalGate.H1,
        reviewer_name="Reviewer",
        reviewer_role="Supervisor",
        decision=ApprovalDecision.APPROVE,
        comment="Requirements reviewed.",
        timestamp=NOW,
        artifact_version=1,
        next_stage=WorkflowStage.DESIGN_IN_PROGRESS,
    )

    assert approval.gate_id is ApprovalGate.H1
    assert approval.decision is ApprovalDecision.APPROVE


def test_approval_field_requiredness_matches_contract() -> None:
    assert Approval.model_fields["comment"].is_required()
    assert Approval.model_fields["artifact_version"].is_required()
    assert Approval.model_fields["next_stage"].is_required()
    assert not Approval.model_fields["reviewer_name"].is_required()
    assert not Approval.model_fields["reviewer_role"].is_required()

    with pytest.raises(ValidationError, match="reviewer_name or reviewer_role"):
        Approval(
            approval_id="APP-001",
            project_id="PRJ-001",
            gate_id=ApprovalGate.H1,
            reviewer_name=None,
            reviewer_role=None,
            decision=ApprovalDecision.APPROVE,
            comment="Requirements reviewed.",
            timestamp=NOW,
            artifact_version=1,
            next_stage=WorkflowStage.DESIGN_IN_PROGRESS,
        )


def test_approval_rejects_invalid_project_id() -> None:
    with pytest.raises(ValidationError):
        Approval(
            approval_id="APP-001",
            project_id="PROJECT-001",
            gate_id=ApprovalGate.H1,
            reviewer_name="Reviewer",
            reviewer_role=None,
            decision=ApprovalDecision.REJECT,
            comment="Needs clarification.",
            timestamp=NOW,
            artifact_version=1,
            next_stage=WorkflowStage.H1_WAITING_APPROVAL,
        )


def test_approval_rejects_invalid_approval_id() -> None:
    with pytest.raises(ValidationError):
        Approval(
            approval_id="EVT-001",
            project_id="PRJ-001",
            gate_id=ApprovalGate.H1,
            reviewer_name=None,
            reviewer_role="Supervisor",
            decision=ApprovalDecision.REQUEST_CHANGES,
            comment="Add missing acceptance criteria.",
            timestamp=NOW,
            artifact_version=1,
            next_stage=WorkflowStage.H1_WAITING_APPROVAL,
        )


def test_workflow_event_schema_valid_case() -> None:
    event = WorkflowEvent(
        event_id="EVT-001",
        project_id="PRJ-001",
        event_type=EventType.STAGE_CHANGED,
        source_component="Central SDLC Orchestrator",
        target_component="Project Management and Design Agent",
        stage_before=WorkflowStage.H1_WAITING_APPROVAL,
        stage_after=WorkflowStage.DESIGN_IN_PROGRESS,
        message="H1 approved; design work may begin.",
        metadata={"approval_id": "APP-001", "artifact_version": 1},
        created_at=NOW,
    )

    assert event.event_type is EventType.STAGE_CHANGED
    assert event.metadata["approval_id"] == "APP-001"


def test_workflow_event_conditional_fields_are_optional() -> None:
    assert not WorkflowEvent.model_fields["target_component"].is_required()
    assert not WorkflowEvent.model_fields["stage_before"].is_required()
    assert not WorkflowEvent.model_fields["stage_after"].is_required()


def test_workflow_event_rejects_invalid_event_id() -> None:
    with pytest.raises(ValidationError):
        WorkflowEvent(
            event_id="EVENT-001",
            project_id="PRJ-001",
            event_type=EventType.AGENT_STARTED,
            source_component="Requirement Gathering and Analysis Agent",
            message="Requirement processing started.",
            created_at=NOW,
        )


def test_traceability_link_valid_pairwise_link() -> None:
    link = TraceabilityLink(
        trace_id="TRACE-001",
        project_id="PRJ-001",
        source_artifact_id="REQ-001",
        source_artifact_type="REQUIREMENT",
        target_artifact_id="TEST-001",
        target_artifact_type="TEST_CASE",
        relation_type=TraceabilityRelationType.RELATED_TO,
        created_at=NOW,
    )

    assert link.source_artifact_id == "REQ-001"
    assert link.target_artifact_id == "TEST-001"
    assert set(TraceabilityLink.model_fields) == {
        "trace_id",
        "project_id",
        "source_artifact_id",
        "source_artifact_type",
        "target_artifact_id",
        "target_artifact_type",
        "relation_type",
        "created_at",
    }


def test_traceability_link_rejects_identical_source_and_target() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        TraceabilityLink(
            trace_id="TRACE-001",
            project_id="PRJ-001",
            source_artifact_id="REQ-001",
            source_artifact_type="REQUIREMENT",
            target_artifact_id="REQ-001",
            target_artifact_type="REQUIREMENT",
            relation_type=TraceabilityRelationType.RELATED_TO,
            created_at=NOW,
        )


def test_base_artifact_validates_common_contract() -> None:
    artifact = BaseArtifact(
        project_id="PRJ-001",
        artifact_id="REQ-001",
        artifact_type="REQUIREMENT",
        title="Manage books",
        status=ArtifactStatus.WAITING_FOR_APPROVAL,
        approval_gate=ApprovalGate.H1,
        created_by_agent="Requirement Gathering and Analysis Agent",
        created_at=NOW,
        updated_at=NOW,
        version=1,
        traceability_refs=["TRACE-001"],
    )

    assert artifact.version == 1
    assert artifact.traceability_refs == ["TRACE-001"]


@pytest.mark.parametrize("version", [0, -1])
def test_base_artifact_requires_positive_version(version: int) -> None:
    with pytest.raises(ValidationError):
        BaseArtifact(
            project_id="PRJ-001",
            artifact_id="REQ-001",
            artifact_type="REQUIREMENT",
            title="Manage books",
            status=ArtifactStatus.IN_PROGRESS,
            approval_gate=ApprovalGate.H1,
            created_by_agent="Requirement Gathering and Analysis Agent",
            created_at=NOW,
            updated_at=NOW,
            version=version,
        )


@pytest.mark.parametrize("field", ["artifact_type", "title", "created_by_agent"])
def test_base_artifact_rejects_blank_required_metadata(field: str) -> None:
    values = {
        "project_id": "PRJ-001",
        "artifact_id": "REQ-001",
        "artifact_type": "REQUIREMENT",
        "title": "Manage books",
        "status": ArtifactStatus.IN_PROGRESS,
        "approval_gate": ApprovalGate.H1,
        "created_by_agent": "Requirement Gathering and Analysis Agent",
        "created_at": NOW,
        "updated_at": NOW,
        "version": 1,
    }
    values[field] = "   "

    with pytest.raises(ValidationError, match="must not be blank"):
        BaseArtifact(**values)


def test_base_artifact_rejects_reverse_timestamp_order() -> None:
    with pytest.raises(ValidationError, match="updated_at"):
        BaseArtifact(
            project_id="PRJ-001",
            artifact_id="REQ-001",
            artifact_type="REQUIREMENT",
            title="Manage books",
            status=ArtifactStatus.IN_PROGRESS,
            approval_gate=ApprovalGate.H1,
            created_by_agent="Requirement Gathering and Analysis Agent",
            created_at=NOW,
            updated_at=datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc),
            version=1,
        )


def agent1_metadata(artifact_id: str, artifact_type: str) -> dict[str, object]:
    return {
        "project_id": "PRJ-001",
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "title": "Agent 1 artifact",
        "status": ArtifactStatus.WAITING_FOR_APPROVAL,
        "approval_gate": ApprovalGate.H1,
        "created_by_agent": "Requirement Gathering and Analysis Agent",
        "created_at": NOW,
        "updated_at": NOW,
        "version": 3,
    }


@pytest.mark.parametrize("requirement_kind", list(RequirementKind))
def test_requirement_schema_and_kind(requirement_kind: RequirementKind) -> None:
    artifact = Requirement(
        **agent1_metadata("REQ-001", "REQUIREMENT"),
        requirement_kind=requirement_kind,
        statement="The system shall manage books.",
        source_reference="Client interview paragraph 2",
        quality_flags=["CLEAR"],
    )

    assert artifact.artifact_type is Agent1ArtifactType.REQUIREMENT
    assert artifact.requirement_kind is requirement_kind
    assert artifact.traceability_refs == []


def test_user_story_schema() -> None:
    artifact = UserStory(
        **agent1_metadata("US-001", "USER_STORY"),
        actor="Librarian",
        goal="manage books",
        benefit="the catalogue remains current",
        story_text="As a librarian, I want to manage books.",
    )

    assert artifact.artifact_id == "US-001"


def test_acceptance_criteria_schema() -> None:
    artifact = AcceptanceCriteria(
        **agent1_metadata("AC-001", "ACCEPTANCE_CRITERION"),
        criterion="Given a valid book, it is added to the catalogue.",
    )

    assert artifact.artifact_id == "AC-001"


@pytest.mark.parametrize("finding_type", list(QualityFindingType))
def test_quality_finding_schema_and_type(
    finding_type: QualityFindingType,
) -> None:
    artifact = QualityFinding(
        **agent1_metadata("REQ-010", "QUALITY_FINDING"),
        finding_type=finding_type,
        description="The retention period is unclear.",
        affected_artifact_ids=["REQ-001"],
    )

    assert artifact.finding_type is finding_type


def test_persona_schema() -> None:
    artifact = Persona(
        **agent1_metadata("REQ-011", "PERSONA"),
        name="Library staff member",
        role="Librarian",
        goals=["Maintain an accurate catalogue"],
        pain_points=["Duplicate manual entry"],
        context="Uses the system during daily circulation work.",
    )

    assert artifact.artifact_type is Agent1ArtifactType.PERSONA


def test_srs_document_schema_and_reference_lists() -> None:
    artifact = SrsDocument(
        **agent1_metadata("REQ-012", "SRS_DOCUMENT"),
        overview="Library management requirements package.",
        scope="Catalogue and circulation workflows.",
        assumptions=["Authenticated staff operate the system."],
        constraints=["Prototype deployment."],
        requirement_ids=["REQ-001"],
        user_story_ids=["US-001"],
        acceptance_criteria_ids=["AC-001"],
        persona_ids=["REQ-011"],
        quality_finding_ids=["REQ-010"],
    )

    assert artifact.version == 3
    assert artifact.user_story_ids == ["US-001"]


@pytest.mark.parametrize(
    "schema,artifact_id,artifact_type,fields",
    [
        (
            Requirement,
            "US-001",
            "REQUIREMENT",
            {
                "requirement_kind": "FUNCTIONAL",
                "statement": "Statement",
                "source_reference": "Source",
            },
        ),
        (
            UserStory,
            "REQ-001",
            "USER_STORY",
            {
                "actor": "Actor",
                "goal": "Goal",
                "benefit": "Benefit",
                "story_text": "Story",
            },
        ),
        (
            AcceptanceCriteria,
            "REQ-001",
            "ACCEPTANCE_CRITERION",
            {"criterion": "Criterion"},
        ),
        (
            QualityFinding,
            "US-001",
            "QUALITY_FINDING",
            {"finding_type": "AMBIGUITY", "description": "Description"},
        ),
        (
            Persona,
            "AC-001",
            "PERSONA",
            {"name": "Name", "role": "Role", "context": "Context"},
        ),
        (
            SrsDocument,
            "US-001",
            "SRS_DOCUMENT",
            {"overview": "Overview", "scope": "Scope"},
        ),
    ],
)
def test_agent1_artifact_id_prefix_mapping(
    schema, artifact_id: str, artifact_type: str, fields: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        schema(**agent1_metadata(artifact_id, artifact_type), **fields)


def test_agent1_discriminator_and_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Requirement(
            **agent1_metadata("REQ-001", "PERSONA"),
            requirement_kind="FUNCTIONAL",
            statement="Statement",
            source_reference="Source",
        )

    with pytest.raises(ValidationError):
        Requirement(
            **agent1_metadata("REQ-001", "REQUIREMENT"),
            requirement_kind="FUNCTIONAL",
            statement="Statement",
            source_reference="Source",
            unsupported_field=True,
        )


def test_traceability_relation_type_is_restricted() -> None:
    with pytest.raises(ValidationError):
        TraceabilityLink(
            trace_id="TRACE-001",
            project_id="PRJ-001",
            source_artifact_id="US-001",
            source_artifact_type="USER_STORY",
            target_artifact_id="REQ-001",
            target_artifact_type="REQUIREMENT",
            relation_type="UNKNOWN_RELATION",
            created_at=NOW,
        )


def test_response_envelope_defaults_are_safe() -> None:
    first = SuccessResponse[dict[str, str]](
        message="Operation completed successfully",
        data={"project_id": "PRJ-001"},
    )
    second = SuccessResponse[dict[str, str]](
        message="Operation completed successfully",
        data={"project_id": "PRJ-002"},
    )

    first.errors.append(ErrorDetail(field="name", message="Example"))

    assert first.success is True
    assert second.errors == []
    assert second.workflow_stage is None
    assert second.next_action is None


def test_error_response_uses_canonical_envelope() -> None:
    response = ErrorResponse(
        message="Validation failed",
        errors=[ErrorDetail(field="project_id", message="Project not found")],
        workflow_stage=WorkflowStage.REQUIREMENTS_IN_PROGRESS,
        next_action="FIX_INPUT",
    )

    assert response.success is False
    assert response.data is None
    assert response.errors[0].field == "project_id"
