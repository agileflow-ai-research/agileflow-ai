from datetime import datetime
from typing import Any

from pydantic import ValidationError
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.common.status import ApprovalGate, ArtifactStatus
from app.database.collections import CLIENT_INPUTS, PROJECTS, REQUIREMENTS
from app.database.mongodb import get_database
from app.modules.requirements.schemas import Agent1ArtifactModel, ClientInputResponse
from app.schemas.requirements import (
    AcceptanceCriteria,
    Agent1ArtifactType,
    Persona,
    QualityFinding,
    Requirement,
    SrsDocument,
    UserStory,
)


class ClientInputRepositoryError(RuntimeError):
    """Raised when ClientInput persistence cannot be completed."""


class RequirementsArtifactRepositoryError(RuntimeError):
    """Raised when typed Agent 1 artifact persistence cannot be completed."""


class UnsupportedArtifactTypeError(RequirementsArtifactRepositoryError):
    """Raised when a requirements document has an unknown discriminator."""


class ArtifactVersionConflictError(RequirementsArtifactRepositoryError):
    """Raised when an immutable stored identity already exists."""


class ClientInputRepository:
    """Persistence operations for project-owned ClientInput records."""

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._projects = configured_database[PROJECTS]
        self._client_inputs = configured_database[CLIENT_INPUTS]

    @staticmethod
    def _public_document(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        try:
            document = self._projects.find_one(
                {"project_id": project_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not verify project"
            ) from exc
        return self._public_document(document) if document is not None else None

    def create_client_input(
        self,
        client_input: ClientInputResponse,
    ) -> dict[str, Any]:
        document = client_input.model_dump(mode="python")
        try:
            self._client_inputs.insert_one(document.copy())
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not create client input"
            ) from exc
        return self._public_document(document)

    def list_client_inputs(self, project_id: str) -> list[dict[str, Any]]:
        try:
            documents = self._client_inputs.find(
                {"project_id": project_id},
                {"_id": 0},
            )
            return [self._public_document(document) for document in documents]
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not list client inputs"
            ) from exc

    def has_client_input(self, project_id: str) -> bool:
        try:
            return (
                self._client_inputs.find_one(
                    {"project_id": project_id},
                    {"_id": 1},
                )
                is not None
            )
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not check client input"
            ) from exc


class RequirementsArtifactRepository:
    """Typed, project-scoped access to Agent 1 artifact history."""

    _SCHEMA_BY_TYPE = {
        Agent1ArtifactType.REQUIREMENT: Requirement,
        Agent1ArtifactType.USER_STORY: UserStory,
        Agent1ArtifactType.ACCEPTANCE_CRITERION: AcceptanceCriteria,
        Agent1ArtifactType.QUALITY_FINDING: QualityFinding,
        Agent1ArtifactType.PERSONA: Persona,
        Agent1ArtifactType.SRS_DOCUMENT: SrsDocument,
    }

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._requirements = configured_database[REQUIREMENTS]

    @staticmethod
    def _public_document(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    @classmethod
    def _deserialize(cls, document: dict[str, Any]) -> Agent1ArtifactModel:
        public_document = cls._public_document(document)
        try:
            artifact_type = Agent1ArtifactType(public_document.get("artifact_type"))
            schema = cls._SCHEMA_BY_TYPE[artifact_type]
        except (KeyError, TypeError, ValueError) as exc:
            raise UnsupportedArtifactTypeError(
                "Unsupported requirements artifact type"
            ) from exc
        try:
            return schema.model_validate(public_document)
        except ValidationError as exc:
            raise RequirementsArtifactRepositoryError(
                "Invalid persisted Agent 1 artifact"
            ) from exc

    def next_artifact_sequence(self, prefix: str) -> int:
        """Scan the shared collection-wide prefix family for its next sequence."""
        if prefix not in {"REQ", "US", "AC"}:
            raise ValueError("Agent 1 artifact prefix must be REQ, US, or AC")
        try:
            largest_sequence = 0
            for document in self._requirements.find(
                {}, {"artifact_id": 1, "_id": 0}
            ):
                artifact_id = document.get("artifact_id")
                if not isinstance(artifact_id, str):
                    continue
                try:
                    validate_id(artifact_id, prefix)
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(artifact_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not allocate an Agent 1 artifact ID"
            ) from exc

    def create_artifact_version(
        self, artifact: Agent1ArtifactModel
    ) -> Agent1ArtifactModel:
        return self.create_artifact_versions([artifact])[0]

    def create_artifact_versions(
        self, artifacts: list[Agent1ArtifactModel]
    ) -> list[Agent1ArtifactModel]:
        if not artifacts:
            return []
        project_ids = {artifact.project_id for artifact in artifacts}
        if len(project_ids) != 1:
            raise ValueError("Artifact writes must target one project")
        identities = [
            (artifact.project_id, artifact.artifact_id, artifact.version)
            for artifact in artifacts
        ]
        if len(identities) != len(set(identities)):
            raise ArtifactVersionConflictError(
                "Duplicate artifact identity in persistence batch"
            )
        if any(
            self.artifact_version_exists(project_id, artifact_id, version)
            for project_id, artifact_id, version in identities
        ):
            raise ArtifactVersionConflictError(
                "Artifact version already exists and cannot be overwritten"
            )
        documents = [artifact.model_dump(mode="python") for artifact in artifacts]
        try:
            self._requirements.insert_many(
                [document.copy() for document in documents], ordered=True
            )
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not persist Agent 1 artifacts"
            ) from exc
        return [self._deserialize(document) for document in documents]

    def find_artifact_version(
        self, project_id: str, artifact_id: str, version: int
    ) -> Agent1ArtifactModel | None:
        try:
            document = self._requirements.find_one(
                {
                    "project_id": project_id,
                    "artifact_id": artifact_id,
                    "version": version,
                },
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not retrieve Agent 1 artifact"
            ) from exc
        return self._deserialize(document) if document is not None else None

    def artifact_version_exists(
        self, project_id: str, artifact_id: str, version: int
    ) -> bool:
        try:
            return self._requirements.find_one(
                {
                    "project_id": project_id,
                    "artifact_id": artifact_id,
                    "version": version,
                },
                {"_id": 1},
            ) is not None
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not check Agent 1 artifact identity"
            ) from exc

    def list_h1_snapshot(
        self, project_id: str, version: int
    ) -> list[Agent1ArtifactModel]:
        try:
            documents = self._requirements.find(
                {
                    "project_id": project_id,
                    "approval_gate": ApprovalGate.H1.value,
                    "version": version,
                },
                {"_id": 0},
            )
            return [self._deserialize(document) for document in documents]
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not list H1 snapshot"
            ) from exc

    def list_artifacts_by_type(
        self, project_id: str, artifact_type: Agent1ArtifactType
    ) -> list[Agent1ArtifactModel]:
        try:
            documents = self._requirements.find(
                {
                    "project_id": project_id,
                    "artifact_type": artifact_type.value,
                },
                {"_id": 0},
            )
            return [self._deserialize(document) for document in documents]
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not list Agent 1 artifacts by type"
            ) from exc

    def get_latest_artifact_version(
        self, project_id: str, artifact_id: str
    ) -> Agent1ArtifactModel | None:
        try:
            documents = self._requirements.find(
                {"project_id": project_id, "artifact_id": artifact_id},
                {"_id": 0},
            ).sort([("version", -1)]).limit(1)
            document = next(iter(documents), None)
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not retrieve latest Agent 1 artifact version"
            ) from exc
        return self._deserialize(document) if document is not None else None

    def list_artifact_versions(
        self, project_id: str, artifact_id: str
    ) -> list[Agent1ArtifactModel]:
        """Return all stored versions of one stable project artifact identity."""
        try:
            documents = self._requirements.find(
                {"project_id": project_id, "artifact_id": artifact_id},
                {"_id": 0},
            ).sort([("version", 1)])
            return [self._deserialize(document) for document in documents]
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not list Agent 1 artifact versions"
            ) from exc

    def publish_h1_snapshot_status(
        self,
        project_id: str,
        version: int,
        updated_at: datetime,
    ) -> list[Agent1ArtifactModel]:
        """Move only one persisted H1 snapshot from in-progress to review."""
        try:
            self._requirements.update_many(
                {
                    "project_id": project_id,
                    "approval_gate": ApprovalGate.H1.value,
                    "version": version,
                    "status": ArtifactStatus.IN_PROGRESS.value,
                },
                {
                    "$set": {
                        "status": ArtifactStatus.WAITING_FOR_APPROVAL.value,
                        "updated_at": updated_at,
                    }
                },
            )
            return self.list_h1_snapshot(project_id, version)
        except PyMongoError as exc:
            raise RequirementsArtifactRepositoryError(
                "Could not publish H1 artifact status"
            ) from exc
