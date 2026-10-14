from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from app.common.status import ApprovalGate, ArtifactStatus
from app.database.collections import REQUIREMENTS
from app.modules.requirements.repository import (
    ArtifactVersionConflictError,
    RequirementsArtifactRepository,
    UnsupportedArtifactTypeError,
)
from app.modules.requirements.schemas import (
    AcceptanceCriteriaInput,
    PersonaInput,
    QualityFindingInput,
    RequirementInput,
    SrsDocumentInput,
    UserStoryInput,
)
from app.modules.requirements.service import (
    ArtifactIdentityConflictError,
    H1SnapshotValidationError,
    RequirementsArtifactService,
)
from app.schemas.requirements import (
    AcceptanceCriteria,
    Agent1ArtifactType,
    Persona,
    QualityFinding,
    Requirement,
    SrsDocument,
    UserStory,
)


NOW = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)


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

    def insert_many(
        self, documents: list[dict[str, Any]], ordered: bool = True
    ) -> object:
        assert ordered is True
        for document in documents:
            stored = deepcopy(document)
            stored["_id"] = f"mongo-{len(self.documents) + 1}"
            self.documents.append(stored)
        return object()


class FakeDatabase:
    def __init__(self) -> None:
        self.requirements = FakeCollection()

    def __getitem__(self, name: str) -> FakeCollection:
        assert name == REQUIREMENTS
        return self.requirements


@pytest.fixture
def persistence():
    database = FakeDatabase()
    repository = RequirementsArtifactRepository(database)
    return database, repository, RequirementsArtifactService(repository)


def metadata(
    artifact_type: Agent1ArtifactType,
    *,
    artifact_id: str | None = None,
    project_id: str = "PRJ-001",
    version: int = 1,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "title": f"{artifact_type.value} artifact",
        "status": ArtifactStatus.IN_PROGRESS,
        "approval_gate": ApprovalGate.H1,
        "created_by_agent": "Requirement Gathering and Analysis Agent",
        "created_at": NOW,
        "updated_at": NOW,
        "version": version,
    }


def requirement_input(**overrides) -> RequirementInput:
    values = {
        **metadata(Agent1ArtifactType.REQUIREMENT),
        "requirement_kind": "FUNCTIONAL",
        "statement": "The system shall manage books.",
        "source_reference": "Client interview",
        **overrides,
    }
    return RequirementInput(**values)


def mixed_snapshot(version: int = 1, project_id: str = "PRJ-001"):
    common = {"version": version, "project_id": project_id}
    return [
        requirement_input(**common),
        UserStoryInput(
            **metadata(Agent1ArtifactType.USER_STORY, **common),
            actor="Librarian",
            goal="manage books",
            benefit="the catalogue stays current",
            story_text="As a librarian, I want to manage books.",
        ),
        AcceptanceCriteriaInput(
            **metadata(Agent1ArtifactType.ACCEPTANCE_CRITERION, **common),
            criterion="Given a valid book, it is saved.",
        ),
        QualityFindingInput(
            **metadata(Agent1ArtifactType.QUALITY_FINDING, **common),
            finding_type="AMBIGUITY",
            description="The retention period is unclear.",
        ),
        PersonaInput(
            **metadata(Agent1ArtifactType.PERSONA, **common),
            name="Library staff member",
            role="Librarian",
            context="Maintains the daily catalogue.",
        ),
        SrsDocumentInput(
            **metadata(Agent1ArtifactType.SRS_DOCUMENT, **common),
            overview="Library requirements.",
            scope="Catalogue workflows.",
        ),
    ]


def test_complete_mixed_snapshot_persists_all_typed_artifacts(persistence) -> None:
    database, repository, service = persistence

    result = service.persist_h1_snapshot("PRJ-001", 1, mixed_snapshot())

    assert result.project_id == "PRJ-001"
    assert result.version == 1
    assert [type(artifact) for artifact in result.artifacts] == [
        Requirement,
        UserStory,
        AcceptanceCriteria,
        QualityFinding,
        Persona,
        SrsDocument,
    ]
    assert len(database.requirements.documents) == 6
    assert all(artifact.status is ArtifactStatus.IN_PROGRESS for artifact in result.artifacts)
    assert all("_id" not in artifact.model_dump() for artifact in result.artifacts)
    assert len(repository.list_h1_snapshot("PRJ-001", 1)) == 6


def test_req_family_shares_one_collection_sequence(persistence) -> None:
    _, _, service = persistence

    result = service.persist_h1_snapshot("PRJ-001", 1, mixed_snapshot())

    by_type = {artifact.artifact_type: artifact.artifact_id for artifact in result.artifacts}
    assert by_type[Agent1ArtifactType.REQUIREMENT] == "REQ-001"
    assert by_type[Agent1ArtifactType.QUALITY_FINDING] == "REQ-002"
    assert by_type[Agent1ArtifactType.PERSONA] == "REQ-003"
    assert by_type[Agent1ArtifactType.SRS_DOCUMENT] == "REQ-004"
    assert by_type[Agent1ArtifactType.USER_STORY] == "US-001"
    assert by_type[Agent1ArtifactType.ACCEPTANCE_CRITERION] == "AC-001"


def test_allocator_scans_each_canonical_family_across_projects(persistence) -> None:
    database, repository, _ = persistence
    database.requirements.documents.extend(
        [
            {"project_id": "PRJ-002", "artifact_id": "REQ-009"},
            {"project_id": "PRJ-002", "artifact_id": "US-011"},
            {"project_id": "PRJ-002", "artifact_id": "AC-004"},
            {"project_id": "PRJ-002", "artifact_id": "invalid"},
        ]
    )

    assert repository.next_artifact_sequence("REQ") == 10
    assert repository.next_artifact_sequence("US") == 12
    assert repository.next_artifact_sequence("AC") == 5


def test_stable_id_is_reused_and_both_versions_remain_queryable(persistence) -> None:
    _, repository, service = persistence
    first = service.persist_h1_snapshot(
        "PRJ-001", 1, [requirement_input(artifact_id="REQ-001")]
    )
    second = service.persist_h1_snapshot(
        "PRJ-001",
        2,
        [
            requirement_input(
                artifact_id="REQ-001",
                version=2,
                statement="The system shall manage books and journals.",
            )
        ],
    )

    assert first.artifacts[0].artifact_id == second.artifacts[0].artifact_id
    assert repository.find_artifact_version("PRJ-001", "REQ-001", 1).version == 1
    assert repository.find_artifact_version("PRJ-001", "REQ-001", 2).version == 2
    assert repository.get_latest_artifact_version("PRJ-001", "REQ-001").version == 2


def test_historical_identity_cannot_be_overwritten(persistence) -> None:
    database, _, service = persistence
    service.persist_h1_snapshot(
        "PRJ-001", 1, [requirement_input(artifact_id="REQ-001")]
    )

    with pytest.raises(ArtifactIdentityConflictError, match="cannot be overwritten"):
        service.persist_h1_snapshot(
            "PRJ-001",
            1,
            [requirement_input(artifact_id="REQ-001", statement="Changed")],
        )

    assert len(database.requirements.documents) == 1
    assert database.requirements.documents[0]["statement"] != "Changed"


def test_repository_itself_rejects_duplicate_stored_identity(persistence) -> None:
    _, repository, service = persistence
    artifact = service.persist_h1_snapshot(
        "PRJ-001", 1, [requirement_input(artifact_id="REQ-001")]
    ).artifacts[0]

    with pytest.raises(ArtifactVersionConflictError):
        repository.create_artifact_version(artifact)


@pytest.mark.parametrize(
    ("project_id", "version", "artifacts", "message"),
    [
        ("PRJ-001", 1, [], "must not be empty"),
        ("PRJ-001", 0, [requirement_input()], "integer >= 1"),
        (
            "PRJ-001",
            1,
            [requirement_input(project_id="PRJ-002")],
            "snapshot project_id",
        ),
        (
            "PRJ-001",
            1,
            [requirement_input(version=2)],
            "snapshot version",
        ),
    ],
)
def test_snapshot_validation_rejects_invalid_package(
    persistence, project_id, version, artifacts, message
) -> None:
    database, _, service = persistence

    with pytest.raises(H1SnapshotValidationError, match=message):
        service.persist_h1_snapshot(project_id, version, artifacts)

    assert database.requirements.documents == []


def test_internal_input_rejects_wrong_gate() -> None:
    with pytest.raises(ValidationError):
        RequirementInput(
            **{
                **metadata(Agent1ArtifactType.REQUIREMENT),
                "approval_gate": ApprovalGate.H2,
            },
            requirement_kind="FUNCTIONAL",
            statement="Statement",
            source_reference="Source",
        )


def test_snapshot_service_defensively_rejects_wrong_gate(persistence) -> None:
    database, _, service = persistence
    artifact = requirement_input().model_copy(
        update={"approval_gate": ApprovalGate.H2}
    )

    with pytest.raises(H1SnapshotValidationError, match="gate H1"):
        service.persist_h1_snapshot("PRJ-001", 1, [artifact])

    assert database.requirements.documents == []


def test_duplicate_explicit_id_is_rejected_before_writes(persistence) -> None:
    database, _, service = persistence
    artifacts = [
        requirement_input(artifact_id="REQ-010"),
        requirement_input(artifact_id="REQ-010", statement="Another"),
    ]

    with pytest.raises(H1SnapshotValidationError, match="Duplicate artifact IDs"):
        service.persist_h1_snapshot("PRJ-001", 1, artifacts)

    assert database.requirements.documents == []


@pytest.mark.parametrize(
    ("artifact_type", "artifact_id", "extra"),
    [
        (Agent1ArtifactType.REQUIREMENT, "US-001", {}),
        (
            Agent1ArtifactType.USER_STORY,
            "REQ-001",
            {
                "actor": "Actor",
                "goal": "Goal",
                "benefit": "Benefit",
                "story_text": "Story",
            },
        ),
        (
            Agent1ArtifactType.ACCEPTANCE_CRITERION,
            "REQ-001",
            {"criterion": "Criterion"},
        ),
    ],
)
def test_input_models_reject_wrong_id_family(artifact_type, artifact_id, extra) -> None:
    schema = {
        Agent1ArtifactType.REQUIREMENT: RequirementInput,
        Agent1ArtifactType.USER_STORY: UserStoryInput,
        Agent1ArtifactType.ACCEPTANCE_CRITERION: AcceptanceCriteriaInput,
    }[artifact_type]
    fields = metadata(artifact_type, artifact_id=artifact_id)
    if artifact_type is Agent1ArtifactType.REQUIREMENT:
        fields.update(
            requirement_kind="FUNCTIONAL",
            statement="Statement",
            source_reference="Source",
        )
    fields.update(extra)

    with pytest.raises(ValidationError):
        schema(**fields)


def test_project_scoped_reads_do_not_leak(persistence) -> None:
    _, repository, service = persistence
    service.persist_h1_snapshot(
        "PRJ-001", 1, [requirement_input(artifact_id="REQ-001")]
    )
    service.persist_h1_snapshot(
        "PRJ-002",
        1,
        [
            requirement_input(
                project_id="PRJ-002",
                artifact_id="REQ-002",
            )
        ],
    )

    assert repository.find_artifact_version("PRJ-002", "REQ-001", 1) is None
    assert [item.artifact_id for item in repository.list_h1_snapshot("PRJ-001", 1)] == [
        "REQ-001"
    ]
    assert [
        item.artifact_id
        for item in repository.list_artifacts_by_type(
            "PRJ-002", Agent1ArtifactType.REQUIREMENT
        )
    ] == ["REQ-002"]


def test_repository_fails_safely_for_unknown_discriminator(persistence) -> None:
    database, repository, _ = persistence
    database.requirements.documents.append(
        {
            **requirement_input(artifact_id="REQ-001").model_dump(mode="python"),
            "artifact_type": "UNKNOWN",
            "_id": "internal",
        }
    )

    with pytest.raises(UnsupportedArtifactTypeError):
        repository.list_h1_snapshot("PRJ-001", 1)


def test_existing_artifact_id_cannot_change_type_across_versions(persistence) -> None:
    database, _, service = persistence
    service.persist_h1_snapshot(
        "PRJ-001", 1, [requirement_input(artifact_id="REQ-001")]
    )
    persona = PersonaInput(
        **metadata(
            Agent1ArtifactType.PERSONA,
            artifact_id="REQ-001",
            version=2,
        ),
        name="Librarian",
        role="Staff",
        context="Daily operations",
    )

    with pytest.raises(ArtifactIdentityConflictError, match="artifact_type"):
        service.persist_h1_snapshot("PRJ-001", 2, [persona])

    assert len(database.requirements.documents) == 1
