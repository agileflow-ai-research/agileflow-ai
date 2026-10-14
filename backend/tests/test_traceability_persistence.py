from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest

from app.common.status import ApprovalGate, ArtifactStatus
from app.common.traceability import TraceabilityRelationType
from app.database.collections import REQUIREMENTS, TRACEABILITY_LINKS
from app.modules.reports.repository import (
    InvalidTraceabilityDocumentError,
    TraceabilityRepository,
)
from app.modules.reports.service import (
    TraceabilityArtifactTypeMismatchError,
    TraceabilityEndpointNotFoundError,
    TraceabilityRelationValidationError,
    TraceabilityService,
    TraceabilityServiceError,
    TraceabilityValidationError,
)
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
from app.schemas.requirements import Agent1ArtifactType
from app.schemas.traceability import TraceabilityLink


NOW = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)


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
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


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
        "title": artifact_type.value,
        "status": ArtifactStatus.IN_PROGRESS,
        "approval_gate": ApprovalGate.H1,
        "created_by_agent": "Requirement Gathering and Analysis Agent",
        "created_at": NOW,
        "updated_at": NOW,
        "version": version,
    }


def agent1_snapshot(project_id: str = "PRJ-001", version: int = 1):
    suffix = "" if project_id == "PRJ-001" else "9"
    return [
        RequirementInput(
            **metadata(
                Agent1ArtifactType.REQUIREMENT,
                f"REQ-{suffix}001",
                project_id=project_id,
                version=version,
            ),
            requirement_kind="FUNCTIONAL",
            statement="The system shall manage books.",
            source_reference="Client interview",
        ),
        UserStoryInput(
            **metadata(
                Agent1ArtifactType.USER_STORY,
                f"US-{suffix}001",
                project_id=project_id,
                version=version,
            ),
            actor="Librarian",
            goal="manage books",
            benefit="the catalogue stays current",
            story_text="As a librarian, I want to manage books.",
        ),
        AcceptanceCriteriaInput(
            **metadata(
                Agent1ArtifactType.ACCEPTANCE_CRITERION,
                f"AC-{suffix}001",
                project_id=project_id,
                version=version,
            ),
            criterion="Given a valid book, it is saved.",
        ),
        QualityFindingInput(
            **metadata(
                Agent1ArtifactType.QUALITY_FINDING,
                f"REQ-{suffix}002",
                project_id=project_id,
                version=version,
            ),
            finding_type="AMBIGUITY",
            description="The retention period is unclear.",
        ),
        PersonaInput(
            **metadata(
                Agent1ArtifactType.PERSONA,
                f"REQ-{suffix}003",
                project_id=project_id,
                version=version,
            ),
            name="Librarian",
            role="Staff",
            context="Daily catalogue work.",
        ),
        SrsDocumentInput(
            **metadata(
                Agent1ArtifactType.SRS_DOCUMENT,
                f"REQ-{suffix}004",
                project_id=project_id,
                version=version,
            ),
            overview="Library requirements.",
            scope="Catalogue workflows.",
        ),
    ]


@pytest.fixture
def traceability_context():
    database = FakeDatabase()
    artifact_repository = RequirementsArtifactRepository(database)
    artifact_service = RequirementsArtifactService(artifact_repository)
    artifact_service.persist_h1_snapshot("PRJ-001", 1, agent1_snapshot())
    artifact_service.persist_h1_snapshot(
        "PRJ-002", 1, agent1_snapshot("PRJ-002")
    )
    repository = TraceabilityRepository(database)
    service = TraceabilityService(
        repository,
        artifact_repository,
        clock=lambda: NOW,
    )
    return database, repository, artifact_service, service


def create_link(
    service: TraceabilityService,
    source_id: str = "US-001",
    source_type: Agent1ArtifactType = Agent1ArtifactType.USER_STORY,
    target_id: str = "REQ-001",
    target_type: Agent1ArtifactType = Agent1ArtifactType.REQUIREMENT,
    relation: TraceabilityRelationType = TraceabilityRelationType.REFINES,
    project_id: str = "PRJ-001",
) -> TraceabilityLink:
    return service.create_link(
        project_id,
        source_id,
        source_type,
        target_id,
        target_type,
        relation,
    )


def test_trace_id_allocation_uses_only_traceability_collection(
    traceability_context,
) -> None:
    database, repository, _, _ = traceability_context
    assert repository.next_trace_sequence("PRJ-001") == 1
    database.collections[TRACEABILITY_LINKS].documents.extend(
        [{"trace_id": "TRACE-001"}, {"trace_id": "TRACE-009"}]
    )
    database.collections[REQUIREMENTS].documents.append(
        {"trace_id": "TRACE-999"}
    )

    assert repository.next_trace_sequence("PRJ-001") == 10


@pytest.mark.parametrize(
    ("source_id", "source_type", "target_id", "target_type", "relation"),
    [
        (
            "US-001",
            Agent1ArtifactType.USER_STORY,
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            TraceabilityRelationType.REFINES,
        ),
        (
            "AC-001",
            Agent1ArtifactType.ACCEPTANCE_CRITERION,
            "US-001",
            Agent1ArtifactType.USER_STORY,
            TraceabilityRelationType.ACCEPTANCE_CRITERION_FOR,
        ),
        (
            "REQ-002",
            Agent1ArtifactType.QUALITY_FINDING,
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            TraceabilityRelationType.IDENTIFIES_ISSUE_IN,
        ),
        (
            "REQ-004",
            Agent1ArtifactType.SRS_DOCUMENT,
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            TraceabilityRelationType.DERIVED_FROM,
        ),
        (
            "REQ-003",
            Agent1ArtifactType.PERSONA,
            "US-001",
            Agent1ArtifactType.USER_STORY,
            TraceabilityRelationType.RELATED_TO,
        ),
    ],
)
def test_supported_agent1_relations_are_created(
    traceability_context,
    source_id,
    source_type,
    target_id,
    target_type,
    relation,
) -> None:
    database, _, _, service = traceability_context

    link = create_link(
        service, source_id, source_type, target_id, target_type, relation
    )

    assert isinstance(link, TraceabilityLink)
    assert link.trace_id == "TRACE-001"
    assert link.relation_type is relation
    stored = database.collections[TRACEABILITY_LINKS].documents[0]
    assert set(stored) == set(TraceabilityLink.model_fields) | {"_id"}
    assert "source_version" not in stored
    assert "target_version" not in stored


@pytest.mark.parametrize(
    "target_id,target_type",
    [
        ("REQ-001", Agent1ArtifactType.REQUIREMENT),
        ("US-001", Agent1ArtifactType.USER_STORY),
        ("AC-001", Agent1ArtifactType.ACCEPTANCE_CRITERION),
        ("REQ-003", Agent1ArtifactType.PERSONA),
        ("REQ-002", Agent1ArtifactType.QUALITY_FINDING),
    ],
)
def test_srs_derived_from_accepts_all_approved_targets(
    traceability_context, target_id, target_type
) -> None:
    _, _, _, service = traceability_context

    link = create_link(
        service,
        "REQ-004",
        Agent1ArtifactType.SRS_DOCUMENT,
        target_id,
        target_type,
        TraceabilityRelationType.DERIVED_FROM,
    )

    assert link.target_artifact_type == target_type.value


def test_exact_duplicate_is_idempotent(traceability_context) -> None:
    database, _, _, service = traceability_context

    first = create_link(service)
    second = create_link(service)

    assert second.trace_id == first.trace_id == "TRACE-001"
    assert len(database.collections[TRACEABILITY_LINKS].documents) == 1


def test_duplicate_request_still_validates_supplied_types(
    traceability_context,
) -> None:
    database, _, _, service = traceability_context
    create_link(service)

    with pytest.raises(TraceabilityArtifactTypeMismatchError, match="source"):
        create_link(service, source_type=Agent1ArtifactType.REQUIREMENT)

    assert len(database.collections[TRACEABILITY_LINKS].documents) == 1


def test_different_relation_and_direction_are_distinct(traceability_context) -> None:
    database, _, _, service = traceability_context
    first = create_link(
        service,
        "REQ-004",
        Agent1ArtifactType.SRS_DOCUMENT,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.DERIVED_FROM,
    )
    second = create_link(
        service,
        "REQ-004",
        Agent1ArtifactType.SRS_DOCUMENT,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.RELATED_TO,
    )
    reverse = create_link(
        service,
        "REQ-001",
        Agent1ArtifactType.REQUIREMENT,
        "REQ-004",
        Agent1ArtifactType.SRS_DOCUMENT,
        TraceabilityRelationType.RELATED_TO,
    )

    assert {first.trace_id, second.trace_id, reverse.trace_id} == {
        "TRACE-001",
        "TRACE-002",
        "TRACE-003",
    }
    assert len(database.collections[TRACEABILITY_LINKS].documents) == 3


@pytest.mark.parametrize(
    ("source_id", "target_id", "message"),
    [
        ("US-999", "REQ-001", "source"),
        ("US-001", "REQ-999", "target"),
        ("US-9001", "REQ-001", "source"),
        ("US-001", "REQ-9001", "target"),
    ],
)
def test_missing_or_foreign_project_endpoint_is_rejected(
    traceability_context, source_id, target_id, message
) -> None:
    database, _, _, service = traceability_context

    with pytest.raises(TraceabilityEndpointNotFoundError, match=message):
        create_link(service, source_id=source_id, target_id=target_id)

    assert database.collections[TRACEABILITY_LINKS].documents == []


@pytest.mark.parametrize(
    ("source_type", "target_type", "message"),
    [
        (Agent1ArtifactType.REQUIREMENT, Agent1ArtifactType.REQUIREMENT, "source"),
        (Agent1ArtifactType.USER_STORY, Agent1ArtifactType.PERSONA, "target"),
    ],
)
def test_supplied_artifact_type_mismatch_is_rejected(
    traceability_context, source_type, target_type, message
) -> None:
    _, _, _, service = traceability_context

    with pytest.raises(TraceabilityArtifactTypeMismatchError, match=message):
        create_link(service, source_type=source_type, target_type=target_type)


@pytest.mark.parametrize(
    ("source_id", "source_type", "target_id", "target_type", "relation"),
    [
        (
            "REQ-003",
            Agent1ArtifactType.PERSONA,
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            TraceabilityRelationType.REFINES,
        ),
        (
            "US-001",
            Agent1ArtifactType.USER_STORY,
            "AC-001",
            Agent1ArtifactType.ACCEPTANCE_CRITERION,
            TraceabilityRelationType.ACCEPTANCE_CRITERION_FOR,
        ),
        (
            "REQ-003",
            Agent1ArtifactType.PERSONA,
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            TraceabilityRelationType.IDENTIFIES_ISSUE_IN,
        ),
        (
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            "REQ-004",
            Agent1ArtifactType.SRS_DOCUMENT,
            TraceabilityRelationType.DERIVED_FROM,
        ),
    ],
)
def test_invalid_relation_type_combinations_are_rejected(
    traceability_context,
    source_id,
    source_type,
    target_id,
    target_type,
    relation,
) -> None:
    _, _, _, service = traceability_context

    with pytest.raises(TraceabilityRelationValidationError):
        create_link(
            service, source_id, source_type, target_id, target_type, relation
        )


def test_source_and_target_must_differ(traceability_context) -> None:
    _, _, _, service = traceability_context

    with pytest.raises(TraceabilityValidationError, match="must be different"):
        create_link(
            service,
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            "REQ-001",
            Agent1ArtifactType.REQUIREMENT,
            TraceabilityRelationType.RELATED_TO,
        )


def test_service_validates_project_id(traceability_context) -> None:
    database, _, _, service = traceability_context

    with pytest.raises(TraceabilityValidationError, match="PRJ"):
        create_link(service, project_id="REQ-001")

    assert database.collections[TRACEABILITY_LINKS].documents == []


def test_project_scoped_queries_and_exact_lookup(traceability_context) -> None:
    _, _, _, service = traceability_context
    outgoing = create_link(service)
    incoming = create_link(
        service,
        "AC-001",
        Agent1ArtifactType.ACCEPTANCE_CRITERION,
        "US-001",
        Agent1ArtifactType.USER_STORY,
        TraceabilityRelationType.ACCEPTANCE_CRITERION_FOR,
    )
    foreign = create_link(
        service,
        "US-9001",
        Agent1ArtifactType.USER_STORY,
        "REQ-9001",
        Agent1ArtifactType.REQUIREMENT,
        TraceabilityRelationType.REFINES,
        project_id="PRJ-002",
    )

    assert service.get_link("PRJ-001", outgoing.trace_id) == outgoing
    assert service.get_link("PRJ-002", outgoing.trace_id) is None
    assert service.find_exact_edge(
        "PRJ-001",
        "US-001",
        "REQ-001",
        TraceabilityRelationType.REFINES,
    ) == outgoing
    assert service.list_outgoing_links("PRJ-001", "US-001") == [outgoing]
    assert service.list_incoming_links("PRJ-001", "US-001") == [incoming]
    assert service.list_links("PRJ-001") == [outgoing, incoming]
    assert service.list_links("PRJ-002") == [foreign]


def test_returned_links_are_typed_and_hide_mongodb_id(
    traceability_context,
) -> None:
    _, _, _, service = traceability_context
    link = create_link(service)

    fetched = service.get_link("PRJ-001", link.trace_id)

    assert isinstance(fetched, TraceabilityLink)
    assert "_id" not in fetched.model_dump()


def test_malformed_stored_link_fails_safely(traceability_context) -> None:
    database, repository, _, service = traceability_context
    database.collections[TRACEABILITY_LINKS].documents.append(
        {
            "_id": "internal",
            "trace_id": "TRACE-001",
            "project_id": "PRJ-001",
            "relation_type": "UNKNOWN",
        }
    )

    with pytest.raises(InvalidTraceabilityDocumentError):
        repository.list_links("PRJ-001")
    with pytest.raises(TraceabilityServiceError):
        service.list_links("PRJ-001")


def test_link_remains_conceptual_when_artifacts_gain_versions(
    traceability_context,
) -> None:
    database, _, artifact_service, service = traceability_context
    link = create_link(service)
    version_two = agent1_snapshot(version=2)[:2]
    artifact_service.persist_h1_snapshot("PRJ-001", 2, version_two)

    duplicate = create_link(service)

    assert duplicate.trace_id == link.trace_id
    assert len(database.collections[TRACEABILITY_LINKS].documents) == 1
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
