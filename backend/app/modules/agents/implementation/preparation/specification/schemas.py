from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agents.implementation.preparation.canonical.schemas import (
    CanonicalSourceRef,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.preparation.semantic_extraction.schemas import (
    EvidenceSpan,
)

from .constants import (
    FinalArtifactStatus,
    FinalFieldOrigin,
    ProjectSpecificationStatus,
    SemanticDecisionAction,
    SemanticDecisionKind,
    SemanticReviewStatus,
    SourceSpecificationStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SpecificationSourceError(StrictModel):
    error_code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class SpecificationSourceState(StrictModel):
    source_id: str
    filename: str | None = None
    status: SourceSpecificationStatus
    pending_semantic_decision_count: int = Field(default=0, ge=0)
    final_artifact_count: int = Field(default=0, ge=0)
    error: SpecificationSourceError | None = None


class ProjectSpecificationRecord(StrictModel):
    agent_project_id: str
    owner_user_id: str
    status: ProjectSpecificationStatus
    sources: list[SpecificationSourceState]
    started_at: datetime
    updated_at: datetime


class ProjectSpecificationStatusResponse(StrictModel):
    agent_project_id: str
    status: ProjectSpecificationStatus
    source_count: int = Field(ge=0)
    applicable_source_count: int = Field(ge=0)
    ready_source_count: int = Field(ge=0)
    waiting_artifact_review_count: int = Field(ge=0)
    waiting_semantic_review_count: int = Field(ge=0)
    failed_source_count: int = Field(ge=0)
    pending_semantic_decision_count: int = Field(ge=0)
    sources: list[SpecificationSourceState]
    started_at: datetime | None = None
    updated_at: datetime | None = None


class SemanticReviewItem(StrictModel):
    decision_id: str = Field(pattern=r"^SRD-[0-9A-F]{24}$")
    artifact_id: str = Field(pattern=r"^CA-[0-9A-F]{24}$")
    artifact_type: ArtifactDetectionLabel
    kind: SemanticDecisionKind
    field_path: str = Field(min_length=1, max_length=1000)
    deterministic_value: Any | None = None
    semantic_value: Any
    evidence: list[EvidenceSpan] = Field(min_length=1)
    allowed_actions: list[SemanticDecisionAction] = Field(min_length=1)
    decision: SemanticDecisionAction | None = None
    reviewer_owner_id: str | None = Field(default=None, max_length=100)
    decided_at: datetime | None = None


class DocumentSemanticReviewState(StrictModel):
    agent_project_id: str
    upload_id: str
    original_filename: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    human_review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str
    status: SemanticReviewStatus
    items: list[SemanticReviewItem]
    updated_at: datetime


class SemanticDecisionUpdate(StrictModel):
    expected_review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: SemanticDecisionAction


class FinalFieldProvenance(StrictModel):
    field_path: str
    origin: FinalFieldOrigin
    source_refs: list[CanonicalSourceRef] = Field(default_factory=list)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    decision_id: str | None = None


class FinalTrustedArtifact(StrictModel):
    final_artifact_id: str = Field(pattern=r"^FTA-[0-9A-F]{24}$")
    artifact_type: ArtifactDetectionLabel
    status: FinalArtifactStatus
    data: dict[str, Any]
    field_provenance: list[FinalFieldProvenance]
    source_refs: list[CanonicalSourceRef]
    human_decisions: list[SemanticReviewItem]
    canonical_artifact_id: str = Field(pattern=r"^CA-[0-9A-F]{24}$")
    semantic_preview_id: str | None = None
    schema_version: str
    created_at: datetime


class DocumentFinalTrustedArtifacts(StrictModel):
    agent_project_id: str
    upload_id: str
    original_filename: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    human_review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_artifact_digest: str | None = None
    semantic_review_fingerprint: str | None = None
    human_decision_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    schema_version: str
    artifacts: list[FinalTrustedArtifact]
    created_at: datetime
