from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.id_generator import generate_id, validate_id
from app.common.traceability import TraceabilityRelationType
from app.modules.reports.repository import (
    TraceabilityRepository,
    TraceabilityRepositoryError,
)
from app.modules.requirements.repository import (
    RequirementsArtifactRepository,
    RequirementsArtifactRepositoryError,
)
from app.schemas.requirements import Agent1ArtifactType
from app.schemas.traceability import TraceabilityLink


class TraceabilityValidationError(ValueError):
    """Raised when a requested Agent 1 relationship is invalid."""


class TraceabilityEndpointNotFoundError(TraceabilityValidationError):
    """Raised when an endpoint does not exist in the requested project."""


class TraceabilityArtifactTypeMismatchError(TraceabilityValidationError):
    """Raised when supplied endpoint types do not match persisted artifacts."""


class TraceabilityRelationValidationError(TraceabilityValidationError):
    """Raised when source/target types do not support a relation."""


class TraceabilityServiceError(RuntimeError):
    """Raised when traceability cannot be stored or retrieved safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TraceabilityService:
    """Internal Agent 1 traceability creation and typed retrieval."""

    _RELATION_TYPE_RULES = {
        TraceabilityRelationType.REFINES: (
            {Agent1ArtifactType.USER_STORY},
            {Agent1ArtifactType.REQUIREMENT},
        ),
        TraceabilityRelationType.ACCEPTANCE_CRITERION_FOR: (
            {Agent1ArtifactType.ACCEPTANCE_CRITERION},
            {Agent1ArtifactType.USER_STORY},
        ),
        TraceabilityRelationType.IDENTIFIES_ISSUE_IN: (
            {Agent1ArtifactType.QUALITY_FINDING},
            {Agent1ArtifactType.REQUIREMENT},
        ),
        TraceabilityRelationType.DERIVED_FROM: (
            {Agent1ArtifactType.SRS_DOCUMENT},
            {
                Agent1ArtifactType.REQUIREMENT,
                Agent1ArtifactType.USER_STORY,
                Agent1ArtifactType.ACCEPTANCE_CRITERION,
                Agent1ArtifactType.PERSONA,
                Agent1ArtifactType.QUALITY_FINDING,
            },
        ),
        TraceabilityRelationType.RELATED_TO: (
            set(Agent1ArtifactType),
            set(Agent1ArtifactType),
        ),
    }

    def __init__(
        self,
        repository: TraceabilityRepository,
        artifact_repository: RequirementsArtifactRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._artifact_repository = artifact_repository
        self._clock = clock

    def create_link(
        self,
        project_id: str,
        source_artifact_id: str,
        source_artifact_type: Agent1ArtifactType,
        target_artifact_id: str,
        target_artifact_type: Agent1ArtifactType,
        relation_type: TraceabilityRelationType,
    ) -> TraceabilityLink:
        try:
            self._validate_project_id(project_id)
            try:
                source_type = Agent1ArtifactType(source_artifact_type)
                target_type = Agent1ArtifactType(target_artifact_type)
                relation = TraceabilityRelationType(relation_type)
            except (TypeError, ValueError) as exc:
                raise TraceabilityValidationError(
                    "Unsupported Agent 1 artifact type or relation"
                ) from exc
            if source_artifact_id == target_artifact_id:
                raise TraceabilityValidationError(
                    "source and target artifact IDs must be different"
                )

            actual_source_type = self._get_endpoint_type(
                project_id, source_artifact_id, "source"
            )
            actual_target_type = self._get_endpoint_type(
                project_id, target_artifact_id, "target"
            )
            if source_type is not actual_source_type:
                raise TraceabilityArtifactTypeMismatchError(
                    "Supplied source artifact type does not match persistence"
                )
            if target_type is not actual_target_type:
                raise TraceabilityArtifactTypeMismatchError(
                    "Supplied target artifact type does not match persistence"
                )
            self._validate_relation(relation, source_type, target_type)

            existing = self._repository.find_exact_edge(
                project_id,
                source_artifact_id,
                target_artifact_id,
                relation,
            )
            if existing is not None:
                return existing

            link = TraceabilityLink(
                trace_id=generate_id(
                    "TRACE",
                    self._repository.next_trace_sequence(project_id),
                ),
                project_id=project_id,
                source_artifact_id=source_artifact_id,
                source_artifact_type=source_type.value,
                target_artifact_id=target_artifact_id,
                target_artifact_type=target_type.value,
                relation_type=relation,
                created_at=self._clock(),
            )
            return self._repository.create_link(project_id, link)
        except TraceabilityValidationError:
            raise
        except (
            RequirementsArtifactRepositoryError,
            TraceabilityRepositoryError,
            ValidationError,
        ) as exc:
            raise TraceabilityServiceError(
                "Traceability link creation failed"
            ) from exc

    def get_link(
        self, project_id: str, trace_id: str
    ) -> TraceabilityLink | None:
        return self._read(
            project_id,
            lambda: self._repository.find_link_by_id(project_id, trace_id),
        )

    def find_exact_edge(
        self,
        project_id: str,
        source_artifact_id: str,
        target_artifact_id: str,
        relation_type: TraceabilityRelationType,
    ) -> TraceabilityLink | None:
        try:
            relation = TraceabilityRelationType(relation_type)
        except (TypeError, ValueError) as exc:
            raise TraceabilityValidationError(
                "Unsupported traceability relation"
            ) from exc
        return self._read(
            project_id,
            lambda: self._repository.find_exact_edge(
                project_id,
                source_artifact_id,
                target_artifact_id,
                relation,
            ),
        )

    def list_links(self, project_id: str) -> list[TraceabilityLink]:
        return self._read(project_id, lambda: self._repository.list_links(project_id))

    def list_outgoing_links(
        self, project_id: str, source_artifact_id: str
    ) -> list[TraceabilityLink]:
        return self._read(
            project_id,
            lambda: self._repository.list_outgoing_links(
                project_id, source_artifact_id
            ),
        )

    def list_incoming_links(
        self, project_id: str, target_artifact_id: str
    ) -> list[TraceabilityLink]:
        return self._read(
            project_id,
            lambda: self._repository.list_incoming_links(
                project_id, target_artifact_id
            ),
        )

    def _read(self, project_id: str, operation):
        try:
            self._validate_project_id(project_id)
            return operation()
        except TraceabilityValidationError:
            raise
        except (TraceabilityRepositoryError, ValidationError) as exc:
            raise TraceabilityServiceError("Traceability retrieval failed") from exc

    @staticmethod
    def _validate_project_id(project_id: str) -> None:
        try:
            validate_id(project_id, "PRJ")
        except ValueError as exc:
            raise TraceabilityValidationError(str(exc)) from exc

    def _get_endpoint_type(
        self,
        project_id: str,
        artifact_id: str,
        endpoint_name: str,
    ) -> Agent1ArtifactType:
        versions = self._artifact_repository.list_artifact_versions(
            project_id, artifact_id
        )
        if not versions:
            raise TraceabilityEndpointNotFoundError(
                f"Traceability {endpoint_name} artifact was not found"
            )
        artifact_types = {artifact.artifact_type for artifact in versions}
        if len(artifact_types) != 1:
            raise TraceabilityArtifactTypeMismatchError(
                f"Traceability {endpoint_name} has inconsistent artifact types"
            )
        return Agent1ArtifactType(next(iter(artifact_types)))

    @classmethod
    def _validate_relation(
        cls,
        relation: TraceabilityRelationType,
        source_type: Agent1ArtifactType,
        target_type: Agent1ArtifactType,
    ) -> None:
        allowed_sources, allowed_targets = cls._RELATION_TYPE_RULES[relation]
        if source_type not in allowed_sources or target_type not in allowed_targets:
            raise TraceabilityRelationValidationError(
                f"{relation.value} does not support the supplied artifact types"
            )
