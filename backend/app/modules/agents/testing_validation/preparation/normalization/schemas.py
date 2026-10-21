from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputOriginAgent,
    TestGenerationInputSourceType,
    TestGenerationInputSuppliedVia,
)
from app.modules.agents.testing_validation.preparation.extraction.schemas import (
    Agent4DocumentFormat,
    Agent4ExtractionStatus,
    Agent4ExtractionWarning,
)
from app.modules.agents.testing_validation.sources.schemas import (
    TestGenerationSourceStatus,
)


class StrictNormalizationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NormalizationStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    PENDING_ANALYSIS = "PENDING_ANALYSIS"
    FAILED = "FAILED"


class NormalizedSegmentKind(StrEnum):
    TEXT = "TEXT"
    DOCUMENT_TEXT = "DOCUMENT_TEXT"
    PDF_PAGE = "PDF_PAGE"
    DOCX_HEADING = "DOCX_HEADING"
    DOCX_PARAGRAPH = "DOCX_PARAGRAPH"
    DOCX_TABLE = "DOCX_TABLE"
    STRUCTURED_DOCUMENT = "STRUCTURED_DOCUMENT"


class NormalizedSegment(StrictNormalizationContract):
    segment_id: str = Field(pattern=r"^A4SEG-[0-9a-f]{32}$")
    kind: NormalizedSegmentKind
    position: int = Field(ge=1)
    text: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: int | None = Field(default=None, ge=1)
    block_index: int | None = Field(default=None, ge=1)
    heading_level: int | None = Field(default=None, ge=1, le=9)
    table_rows: list[list[str]] | None = None


class DocumentExtractionProvenance(StrictNormalizationContract):
    extraction_id: str = Field(pattern=r"^A4EXT-[0-9a-f]{32}$")
    document_format: Agent4DocumentFormat
    extraction_status: Agent4ExtractionStatus
    extraction_schema_version: str
    extractor_name: str
    extractor_version: str


class NormalizationFailureCode(StrEnum):
    DOCUMENT_EXTRACTION_FAILED = "DOCUMENT_EXTRACTION_FAILED"


class NormalizationFailure(StrictNormalizationContract):
    code: NormalizationFailureCode
    message: str = Field(min_length=1, max_length=500)


class NormalizedTestingArtifact(StrictNormalizationContract):
    schema_version: Literal["1"] = "1"
    normalizer_version: str
    normalized_artifact_id: str = Field(pattern=r"^A4ART-[0-9a-f]{32}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    artifact_type: TestGenerationInputArtifactType
    source_type: TestGenerationInputSourceType
    normally_supplied_by: TestGenerationInputOriginAgent
    supplied_via: Literal[
        TestGenerationInputSuppliedVia.STANDALONE_MANUAL_INPUT
    ]
    collection_status: TestGenerationSourceStatus
    normalization_status: NormalizationStatus
    textual_context_usable: bool
    source_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_text: str | None = None
    structured_content: Any = None
    normalized_segments: list[NormalizedSegment] = Field(default_factory=list)
    original_filename: str | None = Field(default=None, max_length=255)
    extension: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, gt=0)
    source_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    extraction: DocumentExtractionProvenance | None = None
    extraction_warnings: list[Agent4ExtractionWarning] = Field(default_factory=list)
    truncated: bool = False
    failure: NormalizationFailure | None = None
    normalized_at: datetime

    @model_validator(mode="after")
    def validate_shape(self) -> "NormalizedTestingArtifact":
        is_text = self.source_type is TestGenerationInputSourceType.TEXT
        is_document = self.source_type is TestGenerationInputSourceType.DOCUMENT
        file_fields = (
            self.original_filename,
            self.extension,
            self.mime_type,
            self.size_bytes,
            self.source_sha256,
        )
        if is_text:
            if any(value is not None for value in file_fields) or self.extraction:
                raise ValueError("TEXT normalization cannot contain file provenance")
        elif any(value is None for value in file_fields):
            raise ValueError("File normalization requires complete file provenance")
        if is_document and self.extraction is None:
            raise ValueError("DOCUMENT normalization requires extraction provenance")
        if not is_document and self.extraction is not None:
            raise ValueError("Only DOCUMENT normalization may contain extraction provenance")
        if self.textual_context_usable:
            if not self.normalized_text or not self.normalized_segments:
                raise ValueError("Usable textual context requires text and segments")
            if self.normalization_status not in {
                NormalizationStatus.READY,
                NormalizationStatus.READY_WITH_WARNINGS,
            }:
                raise ValueError("Usable textual context requires a ready status")
        elif self.normalized_text is not None or self.normalized_segments:
            raise ValueError("Unusable textual context cannot contain text segments")
        if self.normalization_status is NormalizationStatus.FAILED:
            if self.failure is None:
                raise ValueError("FAILED normalization requires failure evidence")
        elif self.failure is not None:
            raise ValueError("Only FAILED normalization may contain failure evidence")
        if self.normalization_status is NormalizationStatus.PENDING_ANALYSIS:
            if self.source_type is not TestGenerationInputSourceType.IMAGE:
                raise ValueError("Only IMAGE normalization may be pending analysis")
        return self
