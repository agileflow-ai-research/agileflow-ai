from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.common.status import (
    ApprovalDecision,
    ApprovalGate,
    ArtifactStatus,
    WorkflowStage,
)
from app.common.traceability import TraceabilityRelationType
from app.database.collections import (
    APPROVALS,
    PROJECTS,
    REQUIREMENTS,
    TRACEABILITY_LINKS,
    WORKFLOW_EVENTS,
)
from app.modules.approvals.repository import ApprovalRepository
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
from app.modules.requirements.service import RequirementsArtifactService
from app.modules.shared_knowledge.schemas import ApprovedArtifactSnapshot
from app.modules.shared_knowledge.service import (
    ApprovedSnapshotConsistencyError,
    ApprovedSnapshotNotAvailableError,
    SharedKnowledgeService,
    SharedKnowledgeValidationError,
    UnsupportedKnowledgeGateError,
)
from app.schemas.approval import Approval
from app.schemas.requirements import (
    AcceptanceCriteria,
    Agent1ArtifactType,
    Persona,
    QualityFinding,
    Requirement,
    SrsDocument,
    UserStory,
)
from app.schemas.traceability import TraceabilityLink


NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


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


class FakeDatabase:
    def __init__(self) -> None:
        self.collections = {
            REQUIREMENTS: FakeCollection(),
            TRACEABILITY_LINKS: FakeCollection(),
            APPROVALS: FakeCollection(),
            PROJECTS: FakeCollection(),
            WORKFLOW_EVENTS: FakeCollection(),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


def artifact_metadata(
    artifact_type: Agent1ArtifactType,
    artifact_id: str,
    *,
    project_id: str = "PRJ-001",
    version: int = 1,
    status: ArtifactStatus = ArtifactStatus.WAITING_FOR_APPROVAL,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "title": f"{artifact_type.value} v{version}",
        "status": status,
        "approval_gate": ApprovalGate.H1,
        "created_by_agent": "Requirement Gathering and Analysis Agent",
        "created_at": NOW,
        "updated_at": NOW,
        "version": version,
    }


def h1_snapshot(
    version: int = 1,
    *,
    project_id: str = "PRJ-001",
    status: ArtifactStatus = ArtifactStatus.WAITING_FOR_APPROVAL,
):
    common = {"project_id": project_id, "version": version, "status": status}
    return [
        RequirementInput(
            **artifact_metadata(
                Agent1ArtifactType.REQUIREMENT, "REQ-001", **common
            ),
            requirement_kind="FUNCTIONAL",
            statement=f"The system shall manage books in version {version}.",
            source_reference="Client interview",
        ),
        UserStoryInput(
            **artifact_metadata(Agent1ArtifactType.USER_STORY, "US-001", **common),
            actor="Librarian",
            goal="manage books",
            benefit="the catalogue stays current",
            story_text=f"As a librarian, I want version {version}.",
        ),
        AcceptanceCriteriaInput(
            **artifact_metadata(
                Agent1ArtifactType.ACCEPTANCE_CRITERION, "AC-001", **common
            ),
            criterion=f"Version {version} is accepted.",
        ),
        QualityFindingInput(
            **artifact_metadata(
                Agent1ArtifactType.QUALITY_FINDING, "REQ-002", **common
            ),
            finding_type="AMBIGUITY",
            description="The retention period is unclear.",
        ),
        PersonaInput(
            **artifact_metadata(Agent1ArtifactType.PERSONA, "REQ-003", **common),
            name="Librarian",
            role="Staff",
            context="Daily catalogue work.",
        ),
        SrsDocumentInput(
            **artifact_metadata(
                Agent1ArtifactType.SRS_DOCUMENT, "REQ-004", **common
            ),
            overview=f"Library requirements version {version}.",
            scope="Catalogue workflows.",
        ),
    ]


def add_approval(
    database: FakeDatabase,
    decision: ApprovalDecision,
    artifact_version: int,
    *,
    project_id: str = "PRJ-001",
    approval_id: str = "APP-001",
    timestamp: datetime = NOW,
) -> Approval:
    approval = Approval(
        approval_id=approval_id,
        project_id=project_id,
        gate_id=ApprovalGate.H1,
        reviewer_role="Supervisor",
        decision=decision,
        comment=f"Decision: {decision.value}",
        timestamp=timestamp,
        artifact_version=artifact_version,
        next_stage=(
            WorkflowStage.DESIGN_IN_PROGRESS
            if decision is ApprovalDecision.APPROVE
            else WorkflowStage.H1_WAITING_APPROVAL
        ),
    )
    database.collections[APPROVALS].insert_one(approval.model_dump(mode="python"))
    return approval


@pytest.fixture
def knowledge_context():
    database = FakeDatabase()
    artifact_repository = RequirementsArtifactRepository(database)
    artifact_service = RequirementsArtifactService(artifact_repository)
    traceability_service = TraceabilityService(
        TraceabilityRepository(database),
        artifact_repository,
        clock=lambda: NOW,
    )
    service = SharedKnowledgeService(
        artifact_repository,
        ApprovalRepository(database),
        traceability_service,
    )
    return database, artifact_service, traceability_service, service


def persist_versions(artifact_service: RequirementsArtifactService, *versions: int):
    for version in versions:
        artifact_service.persist_h1_snapshot(
            "PRJ-001", version, h1_snapshot(version)
        )


def test_approved_h1_returns_exact_typed_snapshot_without_mongo_id(
    knowledge_context,
) -> None:
    database, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1)
    add_approval(database, ApprovalDecision.APPROVE, 1)

    result = service.get_approved_h1_snapshot("PRJ-001")

    assert isinstance(result, ApprovedArtifactSnapshot)
    assert result.artifact_version == 1
    assert result.artifact_count == 6
    assert [type(artifact) for artifact in result.artifacts] == [
        Requirement,
        UserStory,
        AcceptanceCriteria,
        QualityFinding,
        Persona,
        SrsDocument,
    ]
    assert all(
        artifact.status is ArtifactStatus.WAITING_FOR_APPROVAL
        for artifact in result.artifacts
    )
    assert all("_id" not in artifact.model_dump() for artifact in result.artifacts)


def test_approval_version_wins_over_newer_persisted_draft(knowledge_context) -> None:
    database, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1, 2, 3)
    add_approval(database, ApprovalDecision.APPROVE, 2)

    result = service.get_approved_h1_snapshot("PRJ-001")

    assert result.artifact_version == 2
    assert {artifact.version for artifact in result.artifacts} == {2}
    assert service.get_latest_artifact_version("PRJ-001", "REQ-001").version == 3


@pytest.mark.parametrize(
    "decision",
    [
        ApprovalDecision.REJECT,
        ApprovalDecision.REQUEST_CHANGES,
        ApprovalDecision.HOLD,
    ],
)
def test_non_approved_effective_decision_blocks_snapshot(
    knowledge_context, decision: ApprovalDecision
) -> None:
    database, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1)
    add_approval(database, decision, 1)

    with pytest.raises(ApprovedSnapshotNotAvailableError):
        service.get_approved_h1_snapshot("PRJ-001")


def test_no_approval_blocks_even_artifact_status_approved(knowledge_context) -> None:
    _, artifacts, _, service = knowledge_context
    artifacts.persist_h1_snapshot(
        "PRJ-001",
        1,
        h1_snapshot(1, status=ArtifactStatus.APPROVED),
    )

    with pytest.raises(ApprovedSnapshotNotAvailableError):
        service.get_approved_h1_snapshot("PRJ-001")


def test_effective_approval_uses_existing_newest_decision_rules(
    knowledge_context,
) -> None:
    database, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1, 2)
    add_approval(database, ApprovalDecision.APPROVE, 1)
    add_approval(
        database,
        ApprovalDecision.REQUEST_CHANGES,
        2,
        approval_id="APP-002",
        timestamp=NOW + timedelta(minutes=1),
    )

    with pytest.raises(ApprovedSnapshotNotAvailableError):
        service.get_approved_h1_snapshot("PRJ-001")

    add_approval(
        database,
        ApprovalDecision.APPROVE,
        2,
        approval_id="APP-003",
        timestamp=NOW + timedelta(minutes=2),
    )
    assert service.get_approved_h1_snapshot("PRJ-001").artifact_version == 2


def test_missing_approved_version_is_consistency_error(knowledge_context) -> None:
    database, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1)
    add_approval(database, ApprovalDecision.APPROVE, 99)

    with pytest.raises(ApprovedSnapshotConsistencyError):
        service.get_approved_h1_snapshot("PRJ-001")


def test_structured_artifact_reads_are_exact_latest_and_filtered(
    knowledge_context,
) -> None:
    _, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1, 2)

    exact = service.get_artifact("PRJ-001", "REQ-001", version=1)
    latest = service.get_artifact("PRJ-001", "REQ-001")
    stories = service.list_artifacts(
        "PRJ-001",
        artifact_type=Agent1ArtifactType.USER_STORY,
        version=2,
        status=ArtifactStatus.WAITING_FOR_APPROVAL,
    )

    assert isinstance(exact, Requirement) and exact.version == 1
    assert isinstance(latest, Requirement) and latest.version == 2
    assert len(stories) == 1
    assert isinstance(stories[0], UserStory) and stories[0].version == 2
    assert service.get_artifact("PRJ-002", "REQ-001") is None


def test_structured_reads_validate_project_and_version(knowledge_context) -> None:
    _, _, _, service = knowledge_context
    with pytest.raises(SharedKnowledgeValidationError):
        service.get_artifact("not-a-project", "REQ-001")
    with pytest.raises(SharedKnowledgeValidationError):
        service.list_artifacts("PRJ-001", version=0)


def test_foreign_approval_cannot_authorize_project_snapshot(knowledge_context) -> None:
    database, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1)
    add_approval(
        database,
        ApprovalDecision.APPROVE,
        1,
        project_id="PRJ-002",
    )

    with pytest.raises(ApprovedSnapshotNotAvailableError):
        service.get_approved_h1_snapshot("PRJ-001")


def test_facade_delegates_typed_project_scoped_one_hop_links(
    knowledge_context,
) -> None:
    database, artifacts, traceability, service = knowledge_context
    persist_versions(artifacts, 1)
    link = traceability.create_link(
        "PRJ-001",
        "US-001",
        Agent1ArtifactType.USER_STORY,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
    )
    database.collections[TRACEABILITY_LINKS].documents.append(
        {
            **link.model_dump(mode="python"),
            "trace_id": "TRACE-999",
            "project_id": "PRJ-002",
            "_id": "foreign-link",
        }
    )

    outgoing = service.get_outgoing_links("PRJ-001", "US-001")
    incoming = service.get_incoming_links("PRJ-001", "REQ-001")

    assert outgoing == [link]
    assert incoming == [link]
    assert all(isinstance(item, TraceabilityLink) for item in outgoing + incoming)
    assert all("_id" not in item.model_dump() for item in outgoing + incoming)


def test_approved_links_intersect_both_endpoints_with_approved_package(
    knowledge_context,
) -> None:
    database, artifacts, traceability, service = knowledge_context
    persist_versions(artifacts, 1)
    approved_link = traceability.create_link(
        "PRJ-001",
        "US-001",
        Agent1ArtifactType.USER_STORY,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
    )
    artifacts.persist_h1_snapshot(
        "PRJ-001",
        2,
        [
            *h1_snapshot(2),
            RequirementInput(
                **artifact_metadata(
                    Agent1ArtifactType.REQUIREMENT,
                    "REQ-005",
                    version=2,
                ),
                requirement_kind="FUNCTIONAL",
                statement="A version-two-only requirement.",
                source_reference="Later interview",
            ),
        ],
    )
    traceability.create_link(
        "PRJ-001",
        "US-001",
        Agent1ArtifactType.USER_STORY,
        "REQ-005",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
    )
    add_approval(database, ApprovalDecision.APPROVE, 1)

    assert service.get_approved_h1_links("PRJ-001") == [approved_link]


@pytest.mark.parametrize(
    "gate",
    [ApprovalGate.H2, ApprovalGate.H3, ApprovalGate.H4, ApprovalGate.H5],
)
def test_unimplemented_gate_adapters_fail_explicitly(
    knowledge_context, gate: ApprovalGate
) -> None:
    _, _, _, service = knowledge_context
    with pytest.raises(UnsupportedKnowledgeGateError):
        service.get_approved_snapshot("PRJ-001", gate)


def test_retrieval_is_read_only_across_owned_collections(knowledge_context) -> None:
    database, artifacts, _, service = knowledge_context
    persist_versions(artifacts, 1)
    add_approval(database, ApprovalDecision.APPROVE, 1)
    before = deepcopy(
        {
            name: collection.documents
            for name, collection in database.collections.items()
        }
    )

    service.get_approved_h1_snapshot("PRJ-001")
    service.get_artifact("PRJ-001", "REQ-001")
    service.get_outgoing_links("PRJ-001", "REQ-001")

    after = {
        name: collection.documents
        for name, collection in database.collections.items()
    }
    assert after == before
