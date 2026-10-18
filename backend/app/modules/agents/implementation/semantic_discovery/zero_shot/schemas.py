from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.implementation.extraction.schemas import DocumentType
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
    ChunkProvenance,
)


class ZeroShotStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ZeroShotWarningCode(StrEnum):
    MODEL_INPUT_TRUNCATED = "MODEL_INPUT_TRUNCATED"
    CHUNK_CLASSIFICATION_FAILED = "CHUNK_CLASSIFICATION_FAILED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"


class ZeroShotWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ZeroShotWarningCode
    message: str = Field(min_length=1, max_length=300)
    chunk_id: str | None = Field(default=None, pattern=r"^CHK-[0-9A-F]{20}$")


class ZeroShotModelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    task: Literal["zero-shot-classification"]
    hypothesis_template: str
    multi_label: Literal[True]
    label_map_version: str = Field(pattern=r"^\d+$")
    template_version: str = Field(pattern=r"^\d+$")
    device: Literal["cpu", "cuda", "unavailable"]


class ZeroShotScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: ArtifactDetectionLabel
    score: float = Field(ge=0, le=1)


class ChunkZeroShotDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: ChunkProvenance
    model_token_count: int = Field(ge=0)
    model_max_length: int = Field(ge=1)
    input_truncated: bool
    classification_succeeded: bool
    inference_ms: float = Field(ge=0)
    scores: list[ZeroShotScore]
    display_predictions: list[ZeroShotScore]

    @model_validator(mode="after")
    def validate_score_vector(self) -> "ChunkZeroShotDetection":
        labels = [score.label for score in self.scores]
        if self.classification_succeeded:
            if len(labels) != len(ArtifactDetectionLabel) or set(labels) != set(ArtifactDetectionLabel):
                raise ValueError("successful classification requires the complete taxonomy")
        elif self.scores or self.display_predictions:
            raise ValueError("failed classification cannot contain scores")
        if not set(item.label for item in self.display_predictions).issubset(labels):
            raise ValueError("display predictions must reference raw scores")
        return self


class ZeroShotMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_count: int = Field(ge=0)
    classified_chunk_count: int = Field(ge=0)
    truncated_chunk_count: int = Field(ge=0)
    failed_chunk_count: int = Field(ge=0)
    average_inference_ms_per_chunk: float = Field(ge=0)
    total_inference_ms: float = Field(ge=0)
    top_label_counts: dict[ArtifactDetectionLabel, int]


class DocumentZeroShotDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    original_filename: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: DocumentType
    extraction_version: str = Field(pattern=r"^\d+$")
    chunker_version: str = Field(pattern=r"^\d+$")
    classifier_type: Literal["ZERO_SHOT_NLI"] = "ZERO_SHOT_NLI"
    classifier_version: str = Field(pattern=r"^\d+$")
    score_semantics: Literal["ZERO_SHOT_NLI_NOT_DOMAIN_CALIBRATED"] = (
        "ZERO_SHOT_NLI_NOT_DOMAIN_CALIBRATED"
    )
    model: ZeroShotModelMetadata
    status: ZeroShotStatus
    chunks: list[ChunkZeroShotDetection]
    metrics: ZeroShotMetrics
    warnings: list[ZeroShotWarning]
    created_at: datetime
