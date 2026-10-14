from pydantic import ValidationError

from app.common.id_generator import validate_id
from app.common.status import ApprovalDecision, ApprovalGate, ArtifactStatus
from app.modules.approvals.repository import (
    ApprovalRepository,
    ApprovalRepositoryError,
)
from app.modules.reports.service import (
    TraceabilityService,
    TraceabilityServiceError,
)
from app.modules.requirements.repository import (
    RequirementsArtifactRepository,
    RequirementsArtifactRepositoryError,
)
from app.modules.requirements.schemas import Agent1ArtifactModel
from app.modules.shared_knowledge.schemas import ApprovedArtifactSnapshot
from app.schemas.approval import Approval
from app.schemas.requirements import Agent1ArtifactType
from app.schemas.traceability import TraceabilityLink


class SharedKnowledgeValidationError(ValueError):
    """Raised when a structured internal retrieval request is invalid."""


class UnsupportedKnowledgeGateError(SharedKnowledgeValidationError):
    """Raised when no typed artifact adapter exists for a gate."""


class ApprovedSnapshotNotAvailableError(SharedKnowledgeValidationError):
    """Raised when the effective H1 decision does not authorize retrieval."""


class ApprovedSnapshotConsistencyError(RuntimeError):
    """Raised when an effective approval references missing artifact state."""


class SharedKnowledgeServiceError(RuntimeError):
    """Raised when typed Shared Knowledge Base retrieval fails safely."""


class SharedKnowledgeService:
    """Read-only coordinator over typed artifacts, approvals, and links."""

    def __init__(
        self,
        artifact_repository: RequirementsArtifactRepository,
        approval_repository: ApprovalRepository,
        traceability_service: TraceabilityService,
    ) -> None:
        self._artifacts = artifact_repository
        self._approvals = approval_repository
        self._traceability = traceability_service

    def get_artifact(
        self,
        project_id: str,
        artifact_id: str,
        version: int | None = None,
    ) -> Agent1ArtifactModel | None:
        self._validate_project_id(project_id)
        if version is None:
            return self._artifact_read(
                lambda: self._artifacts.get_latest_artifact_version(
                    project_id, artifact_id
                )
            )
        self._validate_version(version)
        return self._artifact_read(
            lambda: self._artifacts.find_artifact_version(
                project_id, artifact_id, version
            )
        )

    def list_artifacts(
        self,
        project_id: str,
        artifact_type: Agent1ArtifactType | None = None,
        version: int | None = None,
        status: ArtifactStatus | None = None,
    ) -> list[Agent1ArtifactModel]:
        self._validate_project_id(project_id)
        normalized_type = self._normalize_artifact_type(artifact_type)
        normalized_status = self._normalize_status(status)
        if version is not None:
            self._validate_version(version)
        return self._artifact_read(
            lambda: self._artifacts.list_artifacts(
                project_id=project_id,
                artifact_type=normalized_type,
                version=version,
                status=normalized_status,
            )
        )

    def get_latest_artifact_version(
        self,
        project_id: str,
        artifact_id: str,
    ) -> Agent1ArtifactModel | None:
        return self.get_artifact(project_id, artifact_id)

    def get_approved_h1_snapshot(
        self,
        project_id: str,
    ) -> ApprovedArtifactSnapshot:
        return self.get_approved_snapshot(project_id, ApprovalGate.H1)

    def get_approved_snapshot(
        self,
        project_id: str,
        gate_id: ApprovalGate,
    ) -> ApprovedArtifactSnapshot:
        self._validate_project_id(project_id)
        try:
            gate = ApprovalGate(gate_id)
        except (TypeError, ValueError) as exc:
            raise UnsupportedKnowledgeGateError(
                "No Shared Knowledge adapter exists for the requested gate"
            ) from exc
        if gate is not ApprovalGate.H1:
            raise UnsupportedKnowledgeGateError(
                f"Approved retrieval for {gate.value} is not implemented"
            )
        try:
            document = self._approvals.get_effective_approval(project_id, gate)
        except ApprovalRepositoryError as exc:
            raise SharedKnowledgeServiceError(
                "Effective Approval retrieval failed"
            ) from exc
        if document is None:
            raise ApprovedSnapshotNotAvailableError(
                "No effective H1 Approval exists"
            )
        try:
            approval = Approval.model_validate(document)
        except ValidationError as exc:
            raise ApprovedSnapshotConsistencyError(
                "Effective H1 Approval is malformed"
            ) from exc
        if approval.decision is not ApprovalDecision.APPROVE:
            raise ApprovedSnapshotNotAvailableError(
                f"Effective H1 decision is {approval.decision.value}"
            )

        try:
            artifacts = self._artifacts.list_h1_snapshot(
                project_id,
                approval.artifact_version,
            )
        except RequirementsArtifactRepositoryError as exc:
            raise SharedKnowledgeServiceError(
                "Approved H1 artifact retrieval failed"
            ) from exc
        if not artifacts:
            raise ApprovedSnapshotConsistencyError(
                "Effective H1 Approval references a missing snapshot"
            )
        if any(
            artifact.project_id != project_id
            or artifact.approval_gate is not ApprovalGate.H1
            or artifact.version != approval.artifact_version
            for artifact in artifacts
        ):
            raise ApprovedSnapshotConsistencyError(
                "Approved H1 snapshot identity is inconsistent"
            )
        return ApprovedArtifactSnapshot(
            project_id=project_id,
            gate_id=ApprovalGate.H1,
            artifact_version=approval.artifact_version,
            approval=approval,
            artifacts=artifacts,
            artifact_count=len(artifacts),
        )

    def get_outgoing_links(
        self,
        project_id: str,
        artifact_id: str,
    ) -> list[TraceabilityLink]:
        self._validate_project_id(project_id)
        return self._traceability_read(
            lambda: self._traceability.list_outgoing_links(
                project_id, artifact_id
            )
        )

    def get_incoming_links(
        self,
        project_id: str,
        artifact_id: str,
    ) -> list[TraceabilityLink]:
        self._validate_project_id(project_id)
        return self._traceability_read(
            lambda: self._traceability.list_incoming_links(
                project_id, artifact_id
            )
        )

    def get_approved_h1_links(
        self,
        project_id: str,
    ) -> list[TraceabilityLink]:
        snapshot = self.get_approved_h1_snapshot(project_id)
        member_ids = {artifact.artifact_id for artifact in snapshot.artifacts}
        links = self._traceability_read(
            lambda: self._traceability.list_links(project_id)
        )
        return [
            link
            for link in links
            if link.source_artifact_id in member_ids
            and link.target_artifact_id in member_ids
        ]

    @staticmethod
    def _validate_project_id(project_id: str) -> None:
        try:
            validate_id(project_id, "PRJ")
        except ValueError as exc:
            raise SharedKnowledgeValidationError(str(exc)) from exc

    @staticmethod
    def _validate_version(version: int) -> None:
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise SharedKnowledgeValidationError(
                "version must be an integer >= 1"
            )

    @staticmethod
    def _normalize_artifact_type(
        artifact_type: Agent1ArtifactType | None,
    ) -> Agent1ArtifactType | None:
        if artifact_type is None:
            return None
        try:
            return Agent1ArtifactType(artifact_type)
        except (TypeError, ValueError) as exc:
            raise SharedKnowledgeValidationError(
                "Unsupported Agent 1 artifact type"
            ) from exc

    @staticmethod
    def _normalize_status(
        status: ArtifactStatus | None,
    ) -> ArtifactStatus | None:
        if status is None:
            return None
        try:
            return ArtifactStatus(status)
        except (TypeError, ValueError) as exc:
            raise SharedKnowledgeValidationError(
                "Unsupported artifact status"
            ) from exc

    @staticmethod
    def _artifact_read(operation):
        try:
            return operation()
        except RequirementsArtifactRepositoryError as exc:
            raise SharedKnowledgeServiceError(
                "Artifact retrieval failed"
            ) from exc

    @staticmethod
    def _traceability_read(operation):
        try:
            return operation()
        except TraceabilityServiceError as exc:
            raise SharedKnowledgeServiceError(
                "Traceability retrieval failed"
            ) from exc
