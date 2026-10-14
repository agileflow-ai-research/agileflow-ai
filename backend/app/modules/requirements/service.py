from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.id_generator import generate_id, validate_id
from app.common.status import ApprovalGate
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
    H1SnapshotResult,
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


class ClientInputServiceError(RuntimeError):
    """Raised when a ClientInput operation cannot be completed safely."""


class H1SnapshotValidationError(ValueError):
    """Raised when a complete H1 snapshot violates persistence rules."""


class ArtifactIdentityConflictError(H1SnapshotValidationError):
    """Raised when immutable artifact identity/history would be violated."""


class RequirementsArtifactServiceError(RuntimeError):
    """Raised when H1 artifact persistence cannot be completed safely."""


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
