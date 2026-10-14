from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.id_generator import generate_id, validate_id
from app.common.status import ApprovalGate, ArtifactStatus, EventType, WorkflowStage
from app.common.traceability import TraceabilityRelationType
from app.modules.auth.authorization import (
    ProjectAccessNotFoundError,
    authorize_project_access,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.requirements.repository import (
    ClientInputRepository,
    ClientInputRepositoryError,
    RequirementsArtifactRepository,
    RequirementsArtifactRepositoryError,
)
from app.modules.requirements.schemas import (
    Agent1ArtifactInputModel,
    Agent1ArtifactModel,
    ClientInputCreateRequest,
    ClientInputResponse,
    H1PublicationResult,
    H1SnapshotResult,
)
from app.modules.orchestrator.policy import (
    ORCHESTRATOR_COMPONENT,
    REQUIREMENTS_COMPONENT,
)
from app.modules.orchestrator.readiness import (
    SPECIALIST_HANDOFF_RULES,
    matching_readiness_event,
)
from app.modules.orchestrator.repository import (
    OrchestratorRepository,
    OrchestratorRepositoryError,
)
from app.modules.reports.service import (
    TraceabilityService,
    TraceabilityServiceError,
)
from app.schemas.requirements import (
    ARTIFACT_ID_PREFIX_BY_TYPE,
    AcceptanceCriteria,
    Agent1ArtifactType,
    Persona,
    QualityFinding,
    Requirement,
    SrsDocument,
    UserStory,
)
from app.schemas.project import Project
from app.schemas.workflow import WorkflowEvent


class ClientInputServiceError(RuntimeError):
    """Raised when a ClientInput operation cannot be completed safely."""


class H1SnapshotValidationError(ValueError):
    """Raised when a complete H1 snapshot violates persistence rules."""


class ArtifactIdentityConflictError(H1SnapshotValidationError):
    """Raised when immutable artifact identity/history would be violated."""


class RequirementsArtifactServiceError(RuntimeError):
    """Raised when H1 artifact persistence cannot be completed safely."""


class H1PublicationValidationError(ValueError):
    """Raised when a persisted H1 package is not publishable."""


class H1PublicationProjectNotFoundError(H1PublicationValidationError):
    """Raised when the publication project does not exist."""


class H1PublicationStageError(H1PublicationValidationError):
    """Raised when publication is incompatible with the current stage."""


class H1PublicationTraceabilityError(H1PublicationValidationError):
    """Raised when required selected-version traceability is incomplete."""


class H1PublicationServiceError(RuntimeError):
    """Raised when H1 publication cannot be completed safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClientInputService:
    """Project ownership rules for ClientInput persistence."""

    def __init__(
        self,
        repository: ClientInputRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def create_client_input(
        self,
        project_id: str,
        request: ClientInputCreateRequest,
        current_user: UserPublicResponse,
    ) -> ClientInputResponse:
        try:
            authorize_project_access(project_id, current_user, self._repository)

            client_input = ClientInputResponse(
                project_id=project_id,
                input_type=request.input_type,
                content=request.content,
                original_filename=request.original_filename,
                mime_type=request.mime_type,
                metadata=request.metadata,
                created_at=self._clock(),
            )
            document = self._repository.create_client_input(client_input)
            return ClientInputResponse.model_validate(document)
        except ProjectAccessNotFoundError:
            raise
        except (ClientInputRepositoryError, ValidationError) as exc:
            raise ClientInputServiceError(
                "Client input creation failed"
            ) from exc

    def list_client_inputs(
        self,
        project_id: str,
        current_user: UserPublicResponse,
    ) -> list[ClientInputResponse]:
        try:
            authorize_project_access(project_id, current_user, self._repository)

            return [
                ClientInputResponse.model_validate(document)
                for document in self._repository.list_client_inputs(project_id)
            ]
        except ProjectAccessNotFoundError:
            raise
        except (ClientInputRepositoryError, ValidationError) as exc:
            raise ClientInputServiceError(
                "Client input listing failed"
            ) from exc


ClientInputProjectNotFoundError = ProjectAccessNotFoundError


class RequirementsArtifactService:
    """Validate and append complete immutable H1 artifact snapshots."""

    _SCHEMA_BY_TYPE = {
        Agent1ArtifactType.REQUIREMENT: Requirement,
        Agent1ArtifactType.USER_STORY: UserStory,
        Agent1ArtifactType.ACCEPTANCE_CRITERION: AcceptanceCriteria,
        Agent1ArtifactType.QUALITY_FINDING: QualityFinding,
        Agent1ArtifactType.PERSONA: Persona,
        Agent1ArtifactType.SRS_DOCUMENT: SrsDocument,
    }

    def __init__(self, repository: RequirementsArtifactRepository) -> None:
        self._repository = repository

    def persist_h1_snapshot(
        self,
        project_id: str,
        version: int,
        artifacts: list[Agent1ArtifactInputModel],
    ) -> H1SnapshotResult:
        try:
            try:
                validate_id(project_id, "PRJ")
            except ValueError as exc:
                raise H1SnapshotValidationError(str(exc)) from exc
            if (
                isinstance(version, bool)
                or not isinstance(version, int)
                or version < 1
            ):
                raise H1SnapshotValidationError("version must be an integer >= 1")
            if not artifacts:
                raise H1SnapshotValidationError("H1 snapshot must not be empty")

            supplied_ids: set[str] = set()
            for artifact in artifacts:
                if artifact.project_id != project_id:
                    raise H1SnapshotValidationError(
                        "All artifacts must use the snapshot project_id"
                    )
                if artifact.approval_gate is not ApprovalGate.H1:
                    raise H1SnapshotValidationError(
                        "All artifacts must use approval gate H1"
                    )
                if artifact.version != version:
                    raise H1SnapshotValidationError(
                        "All artifacts must use the snapshot version"
                    )
                if artifact.artifact_type not in self._SCHEMA_BY_TYPE:
                    raise H1SnapshotValidationError(
                        "Unsupported Agent 1 artifact type"
                    )
                if artifact.artifact_id is not None:
                    prefix = ARTIFACT_ID_PREFIX_BY_TYPE[artifact.artifact_type]
                    try:
                        validate_id(artifact.artifact_id, prefix)
                    except ValueError as exc:
                        raise H1SnapshotValidationError(str(exc)) from exc
                    if artifact.artifact_id in supplied_ids:
                        raise H1SnapshotValidationError(
                            "Duplicate artifact IDs are not allowed in one snapshot"
                        )
                    supplied_ids.add(artifact.artifact_id)

            next_sequence: dict[str, int] = {}
            prepared: list[Agent1ArtifactModel] = []
            for artifact in artifacts:
                artifact_id = artifact.artifact_id
                prefix = ARTIFACT_ID_PREFIX_BY_TYPE[artifact.artifact_type]
                if artifact_id is None:
                    if prefix not in next_sequence:
                        next_sequence[prefix] = (
                            self._repository.next_artifact_sequence(prefix)
                        )
                    sequence = next_sequence[prefix]
                    artifact_id = generate_id(prefix, sequence)
                    while artifact_id in supplied_ids:
                        sequence += 1
                        artifact_id = generate_id(prefix, sequence)
                    next_sequence[prefix] = sequence + 1
                    supplied_ids.add(artifact_id)

                if self._repository.artifact_version_exists(
                    project_id,
                    artifact_id,
                    version,
                ):
                    raise ArtifactIdentityConflictError(
                        "Artifact version already exists and cannot be overwritten"
                    )

                latest = self._repository.get_latest_artifact_version(
                    project_id,
                    artifact_id,
                )
                if (
                    latest is not None
                    and latest.artifact_type is not artifact.artifact_type
                ):
                    raise ArtifactIdentityConflictError(
                        "An artifact_id cannot change artifact_type across versions"
                    )

                values = artifact.model_dump(mode="python")
                values["artifact_id"] = artifact_id
                prepared.append(
                    self._SCHEMA_BY_TYPE[artifact.artifact_type].model_validate(
                        values
                    )
                )

            persisted = self._repository.create_artifact_versions(prepared)
            return H1SnapshotResult(
                project_id=project_id,
                version=version,
                artifacts=persisted,
            )
        except H1SnapshotValidationError:
            raise
        except (RequirementsArtifactRepositoryError, ValidationError) as exc:
            raise RequirementsArtifactServiceError(
                "H1 snapshot persistence failed"
            ) from exc


class H1PublicationService:
    """Publish one persisted H1 snapshot and emit its canonical handoff marker."""

    _SOURCE_STAGE = WorkflowStage.REQUIREMENTS_IN_PROGRESS
    _TARGET_STAGE = WorkflowStage.H1_WAITING_APPROVAL
    _ALLOWED_STATUSES = {
        ArtifactStatus.IN_PROGRESS,
        ArtifactStatus.WAITING_FOR_APPROVAL,
    }
    _SRS_REFERENCE_TYPES = {
        "requirement_ids": Agent1ArtifactType.REQUIREMENT,
        "user_story_ids": Agent1ArtifactType.USER_STORY,
        "acceptance_criteria_ids": Agent1ArtifactType.ACCEPTANCE_CRITERION,
        "persona_ids": Agent1ArtifactType.PERSONA,
        "quality_finding_ids": Agent1ArtifactType.QUALITY_FINDING,
    }

    def __init__(
        self,
        artifact_repository: RequirementsArtifactRepository,
        traceability_service: TraceabilityService,
        orchestrator_repository: OrchestratorRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._artifact_repository = artifact_repository
        self._traceability = traceability_service
        self._orchestrator = orchestrator_repository
        self._clock = clock

    def publish_h1_snapshot(
        self,
        project_id: str,
        version: int,
    ) -> H1PublicationResult:
        try:
            self._validate_identity(project_id, version)
            project = self._load_project(project_id)
            snapshot = self._artifact_repository.list_h1_snapshot(
                project_id, version
            )
            self._validate_snapshot(project_id, version, snapshot)
            self._validate_traceability(project_id, snapshot)
            existing_event = self._matching_publication_event(
                project_id, version
            )
            self._validate_stage(project, existing_event)

            statuses = {artifact.status for artifact in snapshot}
            if existing_event is not None:
                if statuses != {ArtifactStatus.WAITING_FOR_APPROVAL}:
                    raise H1PublicationValidationError(
                        "Published readiness event conflicts with artifact status"
                    )
                return self._result(project_id, version, snapshot, existing_event)

            published = self._artifact_repository.publish_h1_snapshot_status(
                project_id,
                version,
                self._clock(),
            )
            self._validate_snapshot(project_id, version, published)
            if {
                artifact.status for artifact in published
            } != {ArtifactStatus.WAITING_FOR_APPROVAL}:
                raise H1PublicationValidationError(
                    "H1 snapshot status publication did not complete"
                )

            event = self._orchestrator.create_workflow_event(
                self._build_readiness_event(project_id, version)
            )
            return self._result(project_id, version, published, event)
        except H1PublicationValidationError:
            raise
        except (
            OrchestratorRepositoryError,
            RequirementsArtifactRepositoryError,
            TraceabilityServiceError,
            ValidationError,
        ) as exc:
            raise H1PublicationServiceError("H1 publication failed") from exc

    @staticmethod
    def _validate_identity(project_id: str, version: int) -> None:
        try:
            validate_id(project_id, "PRJ")
        except ValueError as exc:
            raise H1PublicationValidationError(str(exc)) from exc
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise H1PublicationValidationError("version must be an integer >= 1")

    def _load_project(self, project_id: str) -> Project:
        document = self._orchestrator.get_project(project_id)
        if document is None:
            raise H1PublicationProjectNotFoundError("Project was not found")
        return Project.model_validate(document)

    @classmethod
    def _validate_stage(
        cls,
        project: Project,
        existing_event: WorkflowEvent | None,
    ) -> None:
        if project.current_stage is cls._SOURCE_STAGE:
            return
        if (
            project.current_stage is cls._TARGET_STAGE
            and existing_event is not None
        ):
            return
        raise H1PublicationStageError(
            "H1 publication requires REQUIREMENTS_IN_PROGRESS"
        )

    @classmethod
    def _validate_snapshot(
        cls,
        project_id: str,
        version: int,
        snapshot: list[Agent1ArtifactModel],
    ) -> None:
        if not snapshot:
            raise H1PublicationValidationError("H1 snapshot was not found")
        if not any(
            artifact.artifact_type is Agent1ArtifactType.REQUIREMENT
            for artifact in snapshot
        ):
            raise H1PublicationValidationError(
                "H1 snapshot must contain at least one Requirement"
            )
        identities: set[str] = set()
        for artifact in snapshot:
            if artifact.project_id != project_id:
                raise H1PublicationValidationError(
                    "H1 snapshot contains another project"
                )
            if artifact.approval_gate is not ApprovalGate.H1:
                raise H1PublicationValidationError(
                    "H1 snapshot contains another approval gate"
                )
            if artifact.version != version:
                raise H1PublicationValidationError(
                    "H1 snapshot contains another version"
                )
            if artifact.artifact_type not in Agent1ArtifactType:
                raise H1PublicationValidationError(
                    "H1 snapshot contains an unsupported artifact type"
                )
            if artifact.artifact_id in identities:
                raise H1PublicationValidationError(
                    "H1 snapshot contains duplicate artifact identities"
                )
            if artifact.status not in cls._ALLOWED_STATUSES:
                raise H1PublicationValidationError(
                    "H1 snapshot contains an invalid publication status"
                )
            identities.add(artifact.artifact_id)

    def _validate_traceability(
        self,
        project_id: str,
        snapshot: list[Agent1ArtifactModel],
    ) -> None:
        members = {artifact.artifact_id: artifact for artifact in snapshot}
        outgoing = {
            artifact_id: self._traceability.list_outgoing_links(
                project_id, artifact_id
            )
            for artifact_id in members
        }
        for artifact in snapshot:
            if artifact.artifact_type is Agent1ArtifactType.USER_STORY:
                self._require_edge(
                    artifact.artifact_id,
                    Agent1ArtifactType.REQUIREMENT,
                    TraceabilityRelationType.REFINES,
                    members,
                    outgoing,
                )
            elif (
                artifact.artifact_type
                is Agent1ArtifactType.ACCEPTANCE_CRITERION
            ):
                self._require_edge(
                    artifact.artifact_id,
                    Agent1ArtifactType.USER_STORY,
                    TraceabilityRelationType.ACCEPTANCE_CRITERION_FOR,
                    members,
                    outgoing,
                )
            elif artifact.artifact_type is Agent1ArtifactType.QUALITY_FINDING:
                self._validate_quality_finding(artifact, members, outgoing)
            elif artifact.artifact_type is Agent1ArtifactType.SRS_DOCUMENT:
                self._validate_srs(artifact, members, outgoing)

    @staticmethod
    def _require_edge(
        source_id: str,
        target_type: Agent1ArtifactType,
        relation: TraceabilityRelationType,
        members: dict[str, Agent1ArtifactModel],
        outgoing: dict[str, list],
        target_id: str | None = None,
    ) -> None:
        matching = [
            link
            for link in outgoing[source_id]
            if link.relation_type is relation
            and link.target_artifact_id in members
            and members[link.target_artifact_id].artifact_type is target_type
            and (target_id is None or link.target_artifact_id == target_id)
        ]
        if not matching:
            raise H1PublicationTraceabilityError(
                f"Required {relation.value} traceability is missing for {source_id}"
            )

    def _validate_quality_finding(
        self,
        artifact: QualityFinding,
        members: dict[str, Agent1ArtifactModel],
        outgoing: dict[str, list],
    ) -> None:
        for affected_id in artifact.affected_artifact_ids:
            affected = members.get(affected_id)
            if affected is None:
                raise H1PublicationTraceabilityError(
                    "QualityFinding references an artifact outside the H1 snapshot"
                )
            if affected.artifact_type is Agent1ArtifactType.REQUIREMENT:
                self._require_edge(
                    artifact.artifact_id,
                    Agent1ArtifactType.REQUIREMENT,
                    TraceabilityRelationType.IDENTIFIES_ISSUE_IN,
                    members,
                    outgoing,
                    target_id=affected_id,
                )

    def _validate_srs(
        self,
        artifact: SrsDocument,
        members: dict[str, Agent1ArtifactModel],
        outgoing: dict[str, list],
    ) -> None:
        for field_name, expected_type in self._SRS_REFERENCE_TYPES.items():
            for referenced_id in getattr(artifact, field_name):
                referenced = members.get(referenced_id)
                if referenced is None or referenced.artifact_type is not expected_type:
                    raise H1PublicationTraceabilityError(
                        "SrsDocument reference is outside the selected H1 snapshot"
                    )
                self._require_edge(
                    artifact.artifact_id,
                    expected_type,
                    TraceabilityRelationType.DERIVED_FROM,
                    members,
                    outgoing,
                    target_id=referenced_id,
                )

    def _matching_publication_event(
        self,
        project_id: str,
        version: int,
    ) -> WorkflowEvent | None:
        rule = SPECIALIST_HANDOFF_RULES[self._SOURCE_STAGE]
        matches = []
        for document in self._orchestrator.list_artifact_generated_events(
            project_id
        ):
            event = matching_readiness_event(document, project_id, rule)
            if (
                event is not None
                and event.metadata.get("artifact_version") == version
            ):
                matches.append(event)
        return (
            max(matches, key=lambda event: (event.created_at, event.event_id))
            if matches
            else None
        )

    def _build_readiness_event(
        self,
        project_id: str,
        version: int,
    ) -> WorkflowEvent:
        return WorkflowEvent(
            event_id=generate_id("EVT", self._orchestrator.next_event_sequence()),
            project_id=project_id,
            event_type=EventType.ARTIFACT_GENERATED,
            source_component=REQUIREMENTS_COMPONENT,
            target_component=ORCHESTRATOR_COMPONENT,
            stage_before=self._SOURCE_STAGE,
            stage_after=self._SOURCE_STAGE,
            message="Specialist evidence package is ready for review.",
            metadata={
                "handoff_ready": True,
                "source_stage": self._SOURCE_STAGE.value,
                "target_stage": self._TARGET_STAGE.value,
                "artifact_version": version,
            },
            created_at=self._clock(),
        )

    @staticmethod
    def _result(
        project_id: str,
        version: int,
        artifacts: list[Agent1ArtifactModel],
        event: WorkflowEvent,
    ) -> H1PublicationResult:
        return H1PublicationResult(
            project_id=project_id,
            gate_id=ApprovalGate.H1,
            artifact_version=version,
            artifact_count=len(artifacts),
            status=ArtifactStatus.WAITING_FOR_APPROVAL,
            readiness_event=event,
        )
