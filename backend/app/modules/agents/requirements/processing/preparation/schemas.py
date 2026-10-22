from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType


class EvidencePreparationStatus(StrEnum):
    READY = "READY"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvidencePreparationErrorCode(StrEnum):
    PARENT_PROCESSING_NOT_COMPLETED = "PARENT_PROCESSING_NOT_COMPLETED"
    PARENT_PROCESSING_RESULT_UNAVAILABLE = "PARENT_PROCESSING_RESULT_UNAVAILABLE"
    NORMALIZED_TEXT_EMPTY = "NORMALIZED_TEXT_EMPTY"
    PREPARATION_RESULT_INVALID = "PREPARATION_RESULT_INVALID"
    PREPARATION_FAILED = "PREPARATION_FAILED"


class EvidencePreparationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: EvidencePreparationErrorCode
    message: str = Field(min_length=1, max_length=500)


class ChunkerConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunker_version: str = Field(pattern=r"^\d+$")
    target_chars: int = Field(ge=100)
    max_chars: int = Field(ge=100)
    overlap_sentences: int = Field(ge=0, le=10)
    sentence_segmenter: str = Field(min_length=1, max_length=100)
    sentence_segmenter_version: str = Field(min_length=1, max_length=100)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bounds(self) -> "ChunkerConfiguration":
        if self.target_chars > self.max_chars:
            raise ValueError("Chunk target must not exceed the maximum")
        return self


class EvidencePreparationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_type: RequirementSourceType
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_result_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    normalizer_version: str = Field(pattern=r"^\d+$")
    chunker: ChunkerConfiguration
    status: EvidencePreparationStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: EvidencePreparationError | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "EvidencePreparationRecord":
        if self.status is EvidencePreparationStatus.READY:
            if self.started_at is not None or self.completed_at is not None or self.error:
                raise ValueError("READY preparation cannot contain execution data")
        elif self.status is EvidencePreparationStatus.PROCESSING:
            if self.started_at is None or self.completed_at is not None or self.error:
                raise ValueError("PROCESSING requires only started_at")
            if self.parent_result_fingerprint is None:
                raise ValueError("PROCESSING requires a parent result fingerprint")
        elif self.status is EvidencePreparationStatus.COMPLETED:
            if self.started_at is None or self.completed_at is None or self.error:
                raise ValueError("COMPLETED requires timestamps and no error")
            if self.parent_result_fingerprint is None:
                raise ValueError("COMPLETED requires a parent result fingerprint")
        elif self.started_at is None or self.completed_at is None or self.error is None:
            raise ValueError("FAILED requires timestamps and an error")
        return self


class DocumentBlockReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_index: int = Field(ge=0)
    block_type: str = Field(pattern=r"^(?:PARAGRAPH|TABLE)$")


class MediaSegmentReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    parent_start_offset: int | None = Field(default=None, ge=0)
    parent_end_offset: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "MediaSegmentReference":
        if self.end_seconds < self.start_seconds:
            raise ValueError("Segment end must not precede its start")
        if (self.parent_start_offset is None) != (self.parent_end_offset is None):
            raise ValueError("Parent transcript offsets must be provided together")
        if (
            self.parent_start_offset is not None
            and self.parent_end_offset < self.parent_start_offset
        ):
            raise ValueError("Parent transcript end must not precede its start")
        return self


class NormalizedProvenanceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_start_offset: int = Field(ge=0)
    normalized_end_offset: int = Field(ge=0)
    parent_start_offset: int | None = Field(default=None, ge=0)
    parent_end_offset: int | None = Field(default=None, ge=0)
    page_numbers: list[int] = Field(default_factory=list)
    document_blocks: list[DocumentBlockReference] = Field(default_factory=list)
    media_segments: list[MediaSegmentReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_offsets(self) -> "NormalizedProvenanceSpan":
        if self.normalized_end_offset < self.normalized_start_offset:
            raise ValueError("Normalized span end must not precede its start")
        if (self.parent_start_offset is None) != (self.parent_end_offset is None):
            raise ValueError("Parent offsets must be provided together")
        if (
            self.parent_start_offset is not None
            and self.parent_end_offset < self.parent_start_offset
        ):
            raise ValueError("Parent span end must not precede its start")
        return self


class NormalizedEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_type: RequirementSourceType
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_processor_version: str = Field(pattern=r"^\d+$")
    parent_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    transcription_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    extraction_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    normalizer_version: str = Field(pattern=r"^\d+$")
    normalized_text: str = Field(min_length=1)
    provenance: list[NormalizedProvenanceSpan] = Field(min_length=1)
    created_at: datetime


class EvidenceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{16}$")
    content: str = Field(min_length=1)
    normalized_start_offset: int = Field(ge=0)
    normalized_end_offset: int = Field(gt=0)
    provenance: list[NormalizedProvenanceSpan] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> "EvidenceChunk":
        if self.normalized_end_offset <= self.normalized_start_offset:
            raise ValueError("Chunk end must follow its start")
        return self


class EvidenceChunkResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_type: RequirementSourceType
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_version: str = Field(pattern=r"^\d+$")
    chunker: ChunkerConfiguration
    chunks: list[EvidenceChunk] = Field(min_length=1)
    created_at: datetime
