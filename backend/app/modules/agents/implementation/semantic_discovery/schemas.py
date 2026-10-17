from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.implementation.extraction.schemas import DocumentType


class ChunkingStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ChunkWarningCode(StrEnum):
    SOURCE_EXTRACTION_PARTIAL = "SOURCE_EXTRACTION_PARTIAL"
    OVERSIZED_SECTION_SPLIT = "OVERSIZED_SECTION_SPLIT"
    OVERSIZED_TABLE_SPLIT = "OVERSIZED_TABLE_SPLIT"
    OVERSIZED_CODE_BLOCK_SPLIT = "OVERSIZED_CODE_BLOCK_SPLIT"
    STRUCTURED_CONTENT_SPLIT = "STRUCTURED_CONTENT_SPLIT"
    CONTENT_TRUNCATED = "CONTENT_TRUNCATED"
    NO_USABLE_CONTENT = "NO_USABLE_CONTENT"
    CHUNKING_FALLBACK_USED = "CHUNKING_FALLBACK_USED"


class ChunkContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading_path: list[str] = Field(default_factory=list)
    section_title: str | None = None
    heading_depth: int = Field(default=0, ge=0, le=9)
    structure_type: str | None = Field(default=None, max_length=40)
    structural_warning: ChunkWarningCode | None = None


class ChunkProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    original_filename: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: DocumentType
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    block_start: int | None = Field(default=None, ge=1)
    block_end: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    structured_path: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_ranges(self) -> "ChunkProvenance":
        for start_name, end_name in (
            ("page_start", "page_end"), ("block_start", "block_end"),
            ("line_start", "line_end"),
        ):
            start, end = getattr(self, start_name), getattr(self, end_name)
            if (start is None) != (end is None) or (
                start is not None and end is not None and end < start
            ):
                raise ValueError(f"invalid {start_name}/{end_name} range")
        return self


class SemanticChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_count: int = Field(ge=1)
    character_count: int = Field(ge=1)
    context: ChunkContext
    provenance: ChunkProvenance


class ChunkMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_count: int = Field(ge=0)
    total_lexical_tokens: int = Field(ge=0)
    average_chunk_tokens: float = Field(ge=0)
    min_chunk_tokens: int = Field(ge=0)
    max_chunk_tokens: int = Field(ge=0)


class DocumentChunkingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: DocumentType
    extraction_version: str = Field(pattern=r"^\d+$")
    chunker_version: str = Field(pattern=r"^\d+$")
    status: ChunkingStatus
    metrics: ChunkMetrics
    warnings: list[ChunkWarningCode]
    chunks: list[SemanticChunk]
    created_at: datetime


class ArtifactDetectionLabel(StrEnum):
    FUNCTIONAL_REQUIREMENTS = "FUNCTIONAL_REQUIREMENTS"
    NON_FUNCTIONAL_REQUIREMENTS = "NON_FUNCTIONAL_REQUIREMENTS"
    USER_STORIES = "USER_STORIES"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    SYSTEM_ARCHITECTURE = "SYSTEM_ARCHITECTURE"
    DATABASE_SCHEMA = "DATABASE_SCHEMA"
    API_SPECIFICATION = "API_SPECIFICATION"
    UI_FLOW = "UI_FLOW"
    TECHNOLOGY_STACK = "TECHNOLOGY_STACK"
    TECHNICAL_CONSTRAINTS = "TECHNICAL_CONSTRAINTS"
    IMPLEMENTATION_TASKS = "IMPLEMENTATION_TASKS"
    TEST_CASES = "TEST_CASES"
    OTHER_CONTEXT = "OTHER_CONTEXT"


class RuleStrength(StrEnum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


class RuleEvidenceSource(StrEnum):
    TEXT = "TEXT"
    HEADING = "HEADING"
    STRUCTURED_PATH = "STRUCTURED_PATH"


class RuleEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,80}$")
    matched_text: str = Field(min_length=1, max_length=240)
    source: RuleEvidenceSource


class RulePrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: ArtifactDetectionLabel
    rule_score: float = Field(ge=0, le=1)
    strength: RuleStrength
    evidence: list[RuleEvidence] = Field(min_length=1)


class ChunkRuleDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    predictions: list[RulePrediction] = Field(min_length=1)
    unclassified: bool

    @model_validator(mode="after")
    def validate_other_context(self) -> "ChunkRuleDetection":
        labels = {prediction.label for prediction in self.predictions}
        other = ArtifactDetectionLabel.OTHER_CONTEXT in labels
        if other != self.unclassified or (other and len(labels) != 1):
            raise ValueError("OTHER_CONTEXT must be the sole unclassified prediction")
        return self


class RuleDetectionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_count: int = Field(ge=0)
    classified_chunk_count: int = Field(ge=0)
    other_context_chunk_count: int = Field(ge=0)
    prediction_count: int = Field(ge=0)
    per_label_counts: dict[ArtifactDetectionLabel, int]
    strong_prediction_count: int = Field(ge=0)
    moderate_prediction_count: int = Field(ge=0)
    weak_prediction_count: int = Field(ge=0)


class DocumentRuleDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    original_filename: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: DocumentType
    extraction_version: str = Field(pattern=r"^\d+$")
    chunker_version: str = Field(pattern=r"^\d+$")
    rule_detector_version: str = Field(pattern=r"^\d+$")
    score_semantics: Literal["HEURISTIC_NOT_PROBABILITY"] = (
        "HEURISTIC_NOT_PROBABILITY"
    )
    metrics: RuleDetectionMetrics
    detections: list[ChunkRuleDetection]
    created_at: datetime
