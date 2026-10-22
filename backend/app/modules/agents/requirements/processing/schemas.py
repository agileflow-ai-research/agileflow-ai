from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentProcessingStatus(StrEnum):
    READY = "READY"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentType(StrEnum):
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"


class DocumentBlockType(StrEnum):
    PARAGRAPH = "PARAGRAPH"
    TABLE = "TABLE"


class DocumentTextSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_offsets(self) -> "DocumentTextSpan":
        if self.end_offset < self.start_offset:
            raise ValueError("Span end must not precede its start")
        if self.end_offset - self.start_offset != len(self.text):
            raise ValueError("Span offsets must match its extracted text length")
        return self


class DocumentPageSpan(DocumentTextSpan):
    page_number: int = Field(ge=1)


class DocumentBlockSpan(DocumentTextSpan):
    block_index: int = Field(ge=0)
    block_type: DocumentBlockType


class DocumentTextRange(DocumentTextSpan):
    pass


class DocumentStructuralProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[DocumentPageSpan] = Field(default_factory=list)
    blocks: list[DocumentBlockSpan] = Field(default_factory=list)
    text_ranges: list[DocumentTextRange] = Field(default_factory=list)


class DocumentProcessingErrorCode(StrEnum):
    NO_MACHINE_READABLE_TEXT = "NO_MACHINE_READABLE_TEXT"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    SOURCE_CHECKSUM_MISMATCH = "SOURCE_CHECKSUM_MISMATCH"
    PROCESSING_RESULT_INVALID = "PROCESSING_RESULT_INVALID"


class DocumentProcessingError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: DocumentProcessingErrorCode
    message: str = Field(min_length=1, max_length=500)


class DocumentProcessingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^DOC-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    processor_version: str = Field(pattern=r"^\d+$")
    status: DocumentProcessingStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: DocumentProcessingError | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "DocumentProcessingRecord":
        if self.status is DocumentProcessingStatus.READY:
            if self.started_at is not None or self.completed_at is not None or self.error:
                raise ValueError("READY processing cannot contain execution data")
        elif self.status is DocumentProcessingStatus.PROCESSING:
            if self.started_at is None or self.completed_at is not None or self.error:
                raise ValueError("PROCESSING requires only started_at")
        elif self.status is DocumentProcessingStatus.COMPLETED:
            if self.started_at is None or self.completed_at is None or self.error:
                raise ValueError("COMPLETED requires timestamps and no error")
        elif self.started_at is None or self.completed_at is None or self.error is None:
            raise ValueError("FAILED requires timestamps and an error")
        return self


class DocumentProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^DOC-\d{3,}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    processor_version: str = Field(pattern=r"^\d+$")
    document_type: DocumentType
    text: str = Field(min_length=1)
    character_count: int = Field(gt=0)
    page_count: int | None = Field(default=None, ge=1)
    paragraph_count: int | None = Field(default=None, ge=0)
    table_count: int | None = Field(default=None, ge=0)
    structural_provenance: DocumentStructuralProvenance
    processed_at: datetime

    @model_validator(mode="after")
    def validate_structural_provenance(self) -> "DocumentProcessingResult":
        provenance = self.structural_provenance
        if self.document_type is DocumentType.PDF:
            if provenance.blocks or provenance.text_ranges:
                raise ValueError("PDF provenance may contain only page spans")
            if self.page_count is None or len(provenance.pages) != self.page_count:
                raise ValueError("PDF provenance must contain every page")
            if [span.page_number for span in provenance.pages] != list(
                range(1, self.page_count + 1)
            ):
                raise ValueError("PDF page provenance must be ordered")
            spans: list[DocumentTextSpan] = list(provenance.pages)
        elif self.document_type is DocumentType.DOCX:
            if provenance.pages or provenance.text_ranges:
                raise ValueError("DOCX provenance may contain only block spans")
            expected_count = (self.paragraph_count or 0) + (self.table_count or 0)
            if len(provenance.blocks) != expected_count:
                raise ValueError("DOCX provenance must contain every extracted block")
            if [span.block_index for span in provenance.blocks] != list(
                range(expected_count)
            ):
                raise ValueError("DOCX block provenance must be ordered")
            spans = list(provenance.blocks)
        else:
            if provenance.pages or provenance.blocks or len(provenance.text_ranges) != 1:
                raise ValueError("TXT provenance must contain one whole-text range")
            spans = list(provenance.text_ranges)

        previous_end = 0
        for span in spans:
            if span.start_offset < previous_end:
                raise ValueError("Document provenance spans must be ordered")
            if self.text[span.start_offset : span.end_offset] != span.text:
                raise ValueError("Document provenance does not match extracted text")
            previous_end = span.end_offset
        return self

