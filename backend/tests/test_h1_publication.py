from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from pymongo.errors import OperationFailure

from app.common.status import ApprovalGate, ArtifactStatus, EventType, WorkflowStage
from app.common.traceability import TraceabilityRelationType
from app.database.collections import (
    APPROVALS,
    BACKLOG_ITEMS,
    CLIENT_INPUTS,
    DESIGN_ARTIFACTS,
    EXECUTION_LOGS,
    IMPLEMENTATION_ARTIFACTS,
    PROJECTS,
    REQUIREMENTS,
    TEST_CASES,
    TEST_RESULTS,
    TRACEABILITY_LINKS,
    WORKFLOW_EVENTS,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.orchestrator.readiness import evaluate_specialist_handoff
from app.modules.orchestrator.repository import OrchestratorRepository
from app.modules.orchestrator.service import OrchestratorService
from app.modules.reports.repository import TraceabilityRepository
from app.modules.reports.service import TraceabilityService
from app.modules.requirements.repository import RequirementsArtifactRepository
from app.modules.requirements.schemas import (
    AcceptanceCriteriaInput,
    PersonaInput,
    QualityFindingInput,
    RequirementInput,
    SrsDocumentInput,
    UserStoryInput,
)
from app.modules.requirements.service import (
    H1PublicationProjectNotFoundError,
    H1PublicationService,
    H1PublicationServiceError,
    H1PublicationStageError,
    H1PublicationTraceabilityError,
    H1PublicationValidationError,
    RequirementsArtifactService,
)
from app.schemas.requirements import Agent1ArtifactType


NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
ALL_COLLECTIONS = (
    PROJECTS,
    CLIENT_INPUTS,
    REQUIREMENTS,
    DESIGN_ARTIFACTS,
    BACKLOG_ITEMS,
    TEST_CASES,
    IMPLEMENTATION_ARTIFACTS,
    EXECUTION_LOGS,
    TEST_RESULTS,
    APPROVALS,
    TRACEABILITY_LINKS,
    WORKFLOW_EVENTS,
)


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, fields: list[tuple[str, int]]) -> "FakeCursor":
        for field, direction in reversed(fields):
            self._documents.sort(
                key=lambda document: document.get(field),
                reverse=direction < 0,
            )
        return self

    def limit(self, count: int) -> "FakeCursor":
        self._documents = self._documents[:count]
        return self

    def __iter__(self):
        return iter(self._documents)


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.fail_updates = False
        self.fail_inserts = False

    @staticmethod
    def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
        return all(document.get(key) == value for key, value in query.items())

    @staticmethod
    def _project(
        document: dict[str, Any], projection: dict[str, int] | None
    ) -> dict[str, Any]:
        result = deepcopy(document)
        if projection is None:
            return result
        included = {key for key, value in projection.items() if value and key != "_id"}
        if included:
            result = {key: result[key] for key in included if key in result}
        if projection.get("_id") == 0:
            result.pop("_id", None)
        return result

    def find(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> FakeCursor:
        return FakeCursor(
            [
                self._project(document, projection)
                for document in self.documents
                if self._matches(document, query)
            ]
        )

    def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        return next(iter(self.find(query, projection)), None)

    def insert_one(self, document: dict[str, Any]) -> object:
        if self.fail_inserts:
            raise OperationFailure("test insert failure")
        stored = deepcopy(document)
        stored["_id"] = f"mongo-{len(self.documents) + 1}"
        self.documents.append(stored)
        return object()

    def insert_many(
        self, documents: list[dict[str, Any]], ordered: bool = True
    ) -> object:
        assert ordered is True
        for document in documents:
            self.insert_one(document)
        return object()

    def update_many(
        self, query: dict[str, Any], update: dict[str, dict[str, Any]]
    ) -> object:
        if self.fail_updates:
            raise OperationFailure("test update failure")
        for document in self.documents:
            if self._matches(document, query):
                document.update(deepcopy(update["$set"]))
        return object()

    def find_one_and_update(
        self,
        query: dict[str, Any],
        update: dict[str, dict[str, Any]],
        projection: dict[str, int] | None = None,
        return_document=None,
    ) -> dict[str, Any] | None:
        del return_document
        if self.fail_updates:
            raise OperationFailure("test update failure")
        for document in self.documents:
            if self._matches(document, query):
                document.update(deepcopy(update["$set"]))
                return self._project(document, projection)
        return None


class FakeDatabase:
    def __init__(self) -> None:
        self.collections = {name: FakeCollection() for name in ALL_COLLECTIONS}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


def project_document(
    project_id: str,
    stage: WorkflowStage = WorkflowStage.REQUIREMENTS_IN_PROGRESS,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "owner_user_id": "USR-001",
        "name": f"Project {project_id}",
        "domain": "Library",
        "description": "H1 publication test",
        "current_stage": stage.value,
        "status": ArtifactStatus.IN_PROGRESS.value,
        "created_by": "USR-001",
        "created_at": NOW,
        "updated_at": NOW,
    }


def metadata(
    artifact_type: Agent1ArtifactType,
    artifact_id: str,
    *,
    project_id: str = "PRJ-001",
    version: int = 1,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "title": f"{artifact_type.value} title",
        "status": ArtifactStatus.IN_PROGRESS,
        "approval_gate": ApprovalGate.H1,
        "created_by_agent": "Requirement Gathering and Analysis Agent",
        "created_at": NOW,
        "updated_at": NOW,
        "version": version,
    }


def requirement(
    artifact_id: str = "REQ-001", **metadata_overrides
) -> RequirementInput:
    return RequirementInput(
        **metadata(
            Agent1ArtifactType.REQUIREMENT,
            artifact_id,
            **metadata_overrides,
        ),
        requirement_kind="FUNCTIONAL",
        statement="The system shall manage books.",
        source_reference="Client interview",
    )


def story(version: int = 1) -> UserStoryInput:
    return UserStoryInput(
        **metadata(Agent1ArtifactType.USER_STORY, "US-001", version=version),
        actor="Librarian",
        goal="manage books",
        benefit="the catalogue stays current",
        story_text="As a librarian, I want to manage books.",
    )


def criterion(version: int = 1) -> AcceptanceCriteriaInput:
    return AcceptanceCriteriaInput(
        **metadata(
            Agent1ArtifactType.ACCEPTANCE_CRITERION,
            "AC-001",
            version=version,
        ),
        criterion="Given a valid book, it is saved.",
    )


def persona(version: int = 1) -> PersonaInput:
    return PersonaInput(
        **metadata(Agent1ArtifactType.PERSONA, "REQ-003", version=version),
        name="Librarian",
        role="Staff",
        context="Daily catalogue work.",
    )


def quality_finding(
    affected_ids: list[str], version: int = 1
) -> QualityFindingInput:
    return QualityFindingInput(
        **metadata(
            Agent1ArtifactType.QUALITY_FINDING,
            "REQ-002",
            version=version,
        ),
        finding_type="AMBIGUITY",
        description="The retention period is unclear.",
        affected_artifact_ids=affected_ids,
    )


def srs(requirement_ids: list[str], version: int = 1) -> SrsDocumentInput:
    return SrsDocumentInput(
        **metadata(
            Agent1ArtifactType.SRS_DOCUMENT,
            "REQ-004",
            version=version,
        ),
        overview="Library requirements.",
        scope="Catalogue workflows.",
        requirement_ids=requirement_ids,
    )


@dataclass
class PublicationContext:
    database: FakeDatabase
    artifact_repository: RequirementsArtifactRepository
    artifact_service: RequirementsArtifactService
    traceability_service: TraceabilityService
    orchestrator_repository: OrchestratorRepository
    publication_service: H1PublicationService

    def persist(self, version: int, artifacts: list, project_id="PRJ-001"):
        return self.artifact_service.persist_h1_snapshot(
            project_id, version, artifacts
        )

    def link(
        self,
        source_id: str,
        source_type: Agent1ArtifactType,
        target_id: str,
        target_type: Agent1ArtifactType,
        relation: TraceabilityRelationType,
        project_id: str = "PRJ-001",
    ):
        return self.traceability_service.create_link(
            project_id,
            source_id,
            source_type,
            target_id,
            target_type,
            relation,
        )


@pytest.fixture
def publication_context() -> PublicationContext:
    database = FakeDatabase()
    database[PROJECTS].documents.extend(
        [project_document("PRJ-001"), project_document("PRJ-002")]
    )
    artifact_repository = RequirementsArtifactRepository(database)
    artifact_service = RequirementsArtifactService(artifact_repository)
    traceability_repository = TraceabilityRepository(database)
    traceability_service = TraceabilityService(
        traceability_repository,
        artifact_repository,
        clock=lambda: NOW,
    )
    orchestrator_repository = OrchestratorRepository(database)
    publication_service = H1PublicationService(
        artifact_repository,
        traceability_service,
        orchestrator_repository,
        clock=lambda: NOW,
    )
    return PublicationContext(
        database,
        artifact_repository,
        artifact_service,
        traceability_service,
        orchestrator_repository,
        publication_service,
    )


def test_valid_snapshot_publishes_without_changing_body_or_identity(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement(), persona()])
    before = deepcopy(context.database[REQUIREMENTS].documents)

    result = context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    after = context.database[REQUIREMENTS].documents
    assert result.project_id == "PRJ-001"
    assert result.gate_id is ApprovalGate.H1
    assert result.artifact_version == 1
    assert result.artifact_count == 2
    assert result.status is ArtifactStatus.WAITING_FOR_APPROVAL
    assert {item["status"] for item in after} == {
        ArtifactStatus.WAITING_FOR_APPROVAL.value
    }
    immutable_fields = {
        "project_id",
        "artifact_id",
        "artifact_type",
        "approval_gate",
        "version",
        "created_at",
        "statement",
        "source_reference",
        "name",
        "role",
        "context",
    }
    for old, new in zip(before, after, strict=True):
        for field in immutable_fields & old.keys():
            assert new[field] == old[field]


def test_publication_mutates_only_selected_version(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.persist(2, [requirement(version=2)])

    context.publication_service.publish_h1_snapshot("PRJ-001", 2)

    version_one = context.artifact_repository.list_h1_snapshot("PRJ-001", 1)
    version_two = context.artifact_repository.list_h1_snapshot("PRJ-001", 2)
    assert {item.status for item in version_one} == {ArtifactStatus.IN_PROGRESS}
    assert {item.status for item in version_two} == {
        ArtifactStatus.WAITING_FOR_APPROVAL
    }


@pytest.mark.parametrize(
    ("project_id", "version", "error"),
    [
        ("REQ-001", 1, H1PublicationValidationError),
        ("PRJ-999", 1, H1PublicationProjectNotFoundError),
        ("PRJ-001", 0, H1PublicationValidationError),
        ("PRJ-001", 1, H1PublicationValidationError),
    ],
)
def test_publication_identity_and_existence_validation(
    publication_context, project_id, version, error
) -> None:
    context = publication_context

    with pytest.raises(error):
        context.publication_service.publish_h1_snapshot(project_id, version)

    assert context.database[WORKFLOW_EVENTS].documents == []


def test_package_without_requirement_is_rejected(publication_context) -> None:
    context = publication_context
    context.persist(1, [persona()])

    with pytest.raises(H1PublicationValidationError, match="Requirement"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert context.database[WORKFLOW_EVENTS].documents == []


def test_wrong_gate_snapshot_is_not_publishable(publication_context) -> None:
    context = publication_context
    document = requirement().model_dump(mode="python")
    document["approval_gate"] = ApprovalGate.H2.value
    context.database[REQUIREMENTS].insert_one(document)

    with pytest.raises(H1PublicationValidationError, match="not found"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert context.database[REQUIREMENTS].documents[0]["status"] == "IN_PROGRESS"


def test_malformed_snapshot_fails_safely(publication_context) -> None:
    context = publication_context
    document = requirement().model_dump(mode="python")
    document.pop("statement")
    context.database[REQUIREMENTS].insert_one(document)

    with pytest.raises(H1PublicationServiceError):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert context.database[WORKFLOW_EVENTS].documents == []


def test_incompatible_project_stage_is_rejected(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.database[PROJECTS].documents[0]["current_stage"] = (
        WorkflowStage.DESIGN_IN_PROGRESS.value
    )

    with pytest.raises(H1PublicationStageError):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert context.database[WORKFLOW_EVENTS].documents == []


def test_unexpected_artifact_status_is_rejected(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.database[REQUIREMENTS].documents[0]["status"] = (
        ArtifactStatus.APPROVED.value
    )

    with pytest.raises(H1PublicationValidationError, match="status"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert context.database[WORKFLOW_EVENTS].documents == []


def test_user_story_requires_refines_link(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement(), story()])

    with pytest.raises(H1PublicationTraceabilityError, match="REFINES"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    context.link(
        "US-001",
        Agent1ArtifactType.USER_STORY,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
    )

    result = context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    assert result.artifact_count == 2


def test_acceptance_criterion_requires_story_link(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement(), story(), criterion()])
    context.link(
        "US-001",
        Agent1ArtifactType.USER_STORY,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
    )

    with pytest.raises(
        H1PublicationTraceabilityError, match="ACCEPTANCE_CRITERION_FOR"
    ):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    context.link(
        "AC-001",
        Agent1ArtifactType.ACCEPTANCE_CRITERION,
        "US-001",
        Agent1ArtifactType.USER_STORY,
        TraceabilityRelationType.ACCEPTANCE_CRITERION_FOR,
    )

    assert context.publication_service.publish_h1_snapshot(
        "PRJ-001", 1
    ).artifact_count == 3


def test_conceptual_link_must_end_in_selected_version(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement(), story()])
    context.link(
        "US-001",
        Agent1ArtifactType.USER_STORY,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
    )
    context.persist(
        2,
        [
            requirement("REQ-010", version=2),
            story(version=2),
        ],
    )

    with pytest.raises(H1PublicationTraceabilityError, match="REFINES"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 2)


def test_srs_reference_requires_membership_and_derived_link(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement(), srs(["REQ-001"])])

    with pytest.raises(H1PublicationTraceabilityError, match="DERIVED_FROM"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    context.link(
        "REQ-004",
        Agent1ArtifactType.SRS_DOCUMENT,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.DERIVED_FROM,
    )
    assert context.publication_service.publish_h1_snapshot(
        "PRJ-001", 1
    ).artifact_count == 2


def test_srs_reference_to_artifact_outside_version_is_rejected(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.persist(
        2,
        [requirement("REQ-010", version=2), srs(["REQ-001"], version=2)],
    )
    context.link(
        "REQ-004",
        Agent1ArtifactType.SRS_DOCUMENT,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.DERIVED_FROM,
    )

    with pytest.raises(H1PublicationTraceabilityError, match="outside"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 2)


def test_quality_finding_affected_requirement_requires_link(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement(), quality_finding(["REQ-001"])])

    with pytest.raises(
        H1PublicationTraceabilityError, match="IDENTIFIES_ISSUE_IN"
    ):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    context.link(
        "REQ-002",
        Agent1ArtifactType.QUALITY_FINDING,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.IDENTIFIES_ISSUE_IN,
    )
    assert context.publication_service.publish_h1_snapshot(
        "PRJ-001", 1
    ).artifact_count == 2


def test_readiness_event_matches_o35_contract(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])

    event = context.publication_service.publish_h1_snapshot(
        "PRJ-001", 1
    ).readiness_event

    assert event.event_type is EventType.ARTIFACT_GENERATED
    assert event.source_component == "Requirement Gathering and Analysis Agent"
    assert event.target_component == "Central SDLC Orchestrator"
    assert event.stage_before is WorkflowStage.REQUIREMENTS_IN_PROGRESS
    assert event.stage_after is WorkflowStage.REQUIREMENTS_IN_PROGRESS
    assert event.metadata == {
        "handoff_ready": True,
        "source_stage": "REQUIREMENTS_IN_PROGRESS",
        "target_stage": "H1_WAITING_APPROVAL",
        "artifact_version": 1,
    }
    assert len(context.database[WORKFLOW_EVENTS].documents) == 1


def test_validation_failure_emits_no_event_or_status_change(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement(), story()])

    with pytest.raises(H1PublicationTraceabilityError):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    artifacts = context.artifact_repository.list_h1_snapshot("PRJ-001", 1)
    assert {artifact.status for artifact in artifacts} == {
        ArtifactStatus.IN_PROGRESS
    }
    assert context.database[WORKFLOW_EVENTS].documents == []


def test_status_failure_emits_no_readiness_event(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.database[REQUIREMENTS].fail_updates = True

    with pytest.raises(H1PublicationServiceError):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert context.database[WORKFLOW_EVENTS].documents == []


def test_repeated_publication_reuses_readiness_event(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])

    first = context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    second = context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert second.readiness_event.event_id == first.readiness_event.event_id
    assert len(context.database[WORKFLOW_EVENTS].documents) == 1


def test_existing_event_with_inconsistent_package_status_fails_safely(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    context.database[REQUIREMENTS].documents[0]["status"] = (
        ArtifactStatus.IN_PROGRESS.value
    )

    with pytest.raises(H1PublicationValidationError, match="conflicts"):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert len(context.database[WORKFLOW_EVENTS].documents) == 1


def test_waiting_package_with_missing_event_completes_retry(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.artifact_repository.publish_h1_snapshot_status("PRJ-001", 1, NOW)

    result = context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert result.readiness_event.event_id == "EVT-001"
    assert len(context.database[WORKFLOW_EVENTS].documents) == 1


def test_event_failure_leaves_retryable_waiting_package(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.database[WORKFLOW_EVENTS].fail_inserts = True

    with pytest.raises(H1PublicationServiceError):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    assert context.artifact_repository.list_h1_snapshot(
        "PRJ-001", 1
    )[0].status is ArtifactStatus.WAITING_FOR_APPROVAL
    context.database[WORKFLOW_EVENTS].fail_inserts = False

    result = context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    assert result.readiness_event.event_id == "EVT-001"


def test_h1_stage_retry_requires_matching_published_event(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.artifact_repository.publish_h1_snapshot_status("PRJ-001", 1, NOW)
    context.database[PROJECTS].documents[0]["current_stage"] = (
        WorkflowStage.H1_WAITING_APPROVAL.value
    )

    with pytest.raises(H1PublicationStageError):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)


def test_after_handoff_retry_is_idempotent(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    first = context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    context.database[PROJECTS].documents[0]["current_stage"] = (
        WorkflowStage.H1_WAITING_APPROVAL.value
    )

    retry = context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert retry.readiness_event.event_id == first.readiness_event.event_id
    assert len(context.database[WORKFLOW_EVENTS].documents) == 1


def test_publication_is_project_scoped(publication_context) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    context.persist(
        1,
        [requirement("REQ-9001", project_id="PRJ-002")],
        project_id="PRJ-002",
    )

    context.publication_service.publish_h1_snapshot("PRJ-001", 1)

    assert context.artifact_repository.list_h1_snapshot(
        "PRJ-002", 1
    )[0].status is ArtifactStatus.IN_PROGRESS
    assert {
        document["project_id"]
        for document in context.database[WORKFLOW_EVENTS].documents
    } == {"PRJ-001"}


def test_foreign_project_traceability_cannot_satisfy_publication(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement(), story()])
    context.persist(
        1,
        [
            requirement("REQ-9001", project_id="PRJ-002"),
            UserStoryInput(
                **metadata(
                    Agent1ArtifactType.USER_STORY,
                    "US-9001",
                    project_id="PRJ-002",
                ),
                actor="Staff",
                goal="work",
                benefit="value",
                story_text="Story",
            ),
        ],
        project_id="PRJ-002",
    )
    context.link(
        "US-9001",
        Agent1ArtifactType.USER_STORY,
        "REQ-9001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
        project_id="PRJ-002",
    )

    with pytest.raises(H1PublicationTraceabilityError):
        context.publication_service.publish_h1_snapshot("PRJ-001", 1)


def test_existing_o35_and_next_step_consume_publication(
    publication_context,
) -> None:
    context = publication_context
    context.persist(1, [requirement()])
    before = evaluate_specialist_handoff(
        context.orchestrator_repository,
        "PRJ-001",
        WorkflowStage.REQUIREMENTS_IN_PROGRESS,
    )
    assert before.ready is False

    context.publication_service.publish_h1_snapshot("PRJ-001", 1)
    after = evaluate_specialist_handoff(
        context.orchestrator_repository,
        "PRJ-001",
        WorkflowStage.REQUIREMENTS_IN_PROGRESS,
    )
    assert after.ready is True

    user = UserPublicResponse(
        user_id="USR-001",
        name="Owner",
        email="owner@example.com",
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    transition = OrchestratorService(
        context.orchestrator_repository,
        clock=lambda: NOW,
    ).next_step("PRJ-001", user)

    assert transition.stage_before is WorkflowStage.REQUIREMENTS_IN_PROGRESS
    assert transition.stage_after is WorkflowStage.H1_WAITING_APPROVAL
    assert context.database[PROJECTS].documents[0]["current_stage"] == (
        WorkflowStage.H1_WAITING_APPROVAL.value
    )
    assert len(context.database[APPROVALS].documents) == 0
