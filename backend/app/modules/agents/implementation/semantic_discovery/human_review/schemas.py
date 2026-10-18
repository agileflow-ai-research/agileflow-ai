from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.agents.implementation.extraction.schemas import DocumentType
from app.modules.agents.implementation.semantic_discovery.hybrid.schemas import (
    ChunkHybridDetection,
)
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel, ChunkProvenance, ChunkRuleDetection, SemanticChunk,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.schemas import (
    ChunkZeroShotDetection,
)

from .constants import MAX_REVIEW_NOTE_LENGTH


class HumanReviewAction(StrEnum):
    ACCEPT = "ACCEPT"
    RELABEL = "RELABEL"
    EXCLUDE = "EXCLUDE"
    ADD_LABEL = "ADD_LABEL"


class ChunkReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    IN_REVIEW = "IN_REVIEW"
    VERIFIED = "VERIFIED"


class DocumentReviewStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"


class HumanReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: HumanReviewAction
    source_candidate_label: ArtifactDetectionLabel | None = None
    final_label: ArtifactDetectionLabel | None = None
    note: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_LENGTH)

    @field_validator("note", mode="before")
    @classmethod
    def sanitize_note(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return None
        if any(not character.isprintable() and character not in "\n\t"
               for character in normalized):
            raise ValueError("Review notes must contain plain printable text")
        return normalized


class ChunkHumanReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: list[HumanReviewDecisionRequest] = Field(min_length=1)


class HumanReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: HumanReviewAction
    source_candidate_label: ArtifactDetectionLabel | None
    final_label: ArtifactDetectionLabel | None
    note: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_LENGTH)
    reviewer_owner_id: str = Field(min_length=1, max_length=100)
    reviewed_at: datetime


class MachineReviewSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hybrid_result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_labels: list[ArtifactDetectionLabel]


class ChunkHumanReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    chunk_index: int = Field(ge=0)
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: ChunkProvenance
    machine_snapshot: MachineReviewSnapshot
    decisions: list[HumanReviewDecision]
    verified_labels: list[ArtifactDetectionLabel]
    review_status: ChunkReviewStatus
    reviewed_at: datetime | None = None


class HumanReviewMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_chunks: int = Field(ge=0)
    verified_chunks: int = Field(ge=0)
    remaining_chunks: int = Field(ge=0)
    accepted_candidate_count: int = Field(ge=0)
    relabeled_candidate_count: int = Field(ge=0)
    excluded_candidate_count: int = Field(ge=0)
    added_label_count: int = Field(ge=0)
    review_completion_percentage: float = Field(ge=0, le=100)


class HumanReviewPipelineIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction_version: str = Field(pattern=r"^\d+$")
    chunker_version: str = Field(pattern=r"^\d+$")
    rule_detector_version: str = Field(pattern=r"^\d+$")
    zero_shot_classifier_version: str = Field(pattern=r"^\d+$")
    zero_shot_model_id: str
    zero_shot_model_revision: str
    zero_shot_label_map_version: str = Field(pattern=r"^\d+$")
    hybrid_decision_version: str = Field(pattern=r"^\d+$")
    hybrid_policy_version: str = Field(pattern=r"^\d+$")
    human_review_schema_version: str = Field(pattern=r"^\d+$")
    human_review_policy_version: str = Field(pattern=r"^\d+$")


class DocumentHumanReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    original_filename: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: DocumentType
    pipeline: HumanReviewPipelineIdentity
    rule_result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    zero_shot_result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    hybrid_result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer_owner_id: str | None = Field(default=None, max_length=100)
    review_status: DocumentReviewStatus
    chunks: list[ChunkHumanReview]
    metrics: HumanReviewMetrics
    created_at: datetime | None
    updated_at: datetime | None


class HumanReviewQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: int = Field(ge=1, le=6)
    chunk: SemanticChunk
    rule: ChunkRuleDetection
    model: ChunkZeroShotDetection
    hybrid: ChunkHybridDetection
    review: ChunkHumanReview


class HumanReviewStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review: DocumentHumanReviewResult
    review_queue: list[HumanReviewQueueItem]
    stale: bool
    stale_message: str | None = None
