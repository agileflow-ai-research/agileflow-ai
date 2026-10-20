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
    processed_at: datetime

