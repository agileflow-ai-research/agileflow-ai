from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.document_extraction.schemas import DOCXBlock, PDFPage
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
)


class StrictAgent4ExtractionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Agent4DocumentFormat(StrEnum):
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"
    MD = "MD"
    JSON = "JSON"
    YAML = "YAML"
    YML = "YML"


class Agent4ExtractionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Agent4ExtractionErrorCode(StrEnum):
    UNSUPPORTED_DOCUMENT_FORMAT = "UNSUPPORTED_DOCUMENT_FORMAT"
    INVALID_PDF = "INVALID_PDF"
    INVALID_DOCX = "INVALID_DOCX"
    INVALID_JSON = "INVALID_JSON"
    INVALID_YAML = "INVALID_YAML"
    ENCODING_ERROR = "ENCODING_ERROR"
    CONTENT_LIMIT_EXCEEDED = "CONTENT_LIMIT_EXCEEDED"
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
    SOURCE_FILE_MISSING = "SOURCE_FILE_MISSING"
    SOURCE_SIZE_MISMATCH = "SOURCE_SIZE_MISMATCH"
    SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"


class Agent4ExtractionError(StrictAgent4ExtractionContract):
    code: Agent4ExtractionErrorCode
    message: str = Field(min_length=1, max_length=500)


class Agent4ExtractionWarning(StrictAgent4ExtractionContract):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    page_number: int | None = Field(default=None, ge=1)
    block_index: int | None = Field(default=None, ge=1)


class Agent4DocumentExtractionResult(StrictAgent4ExtractionContract):
    schema_version: Literal["1"] = "1"
    extraction_id: str = Field(pattern=r"^A4EXT-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    artifact_type: TestGenerationInputArtifactType
    document_format: Agent4DocumentFormat
    status: Agent4ExtractionStatus
    extractor_name: str
    extractor_version: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_size_bytes: int = Field(gt=0)
    extracted_text: str
    structured_content: Any = None
    pages: list[PDFPage] = Field(default_factory=list)
    blocks: list[DOCXBlock] = Field(default_factory=list)
    metrics: dict[str, int | str] = Field(default_factory=dict)
    warnings: list[Agent4ExtractionWarning] = Field(default_factory=list)
    truncated: bool = False
    error: Agent4ExtractionError | None = None
    extracted_at: datetime

    @model_validator(mode="after")
    def validate_result(self) -> "Agent4DocumentExtractionResult":
        if self.status is Agent4ExtractionStatus.FAILED and self.error is None:
            raise ValueError("FAILED extraction requires an error")
        if self.status is not Agent4ExtractionStatus.FAILED and self.error is not None:
            raise ValueError("usable extraction cannot contain a terminal error")
        if self.document_format is not Agent4DocumentFormat.PDF and self.pages:
            raise ValueError("only PDF results may contain pages")
        if self.document_format is not Agent4DocumentFormat.DOCX and self.blocks:
            raise ValueError("only DOCX results may contain blocks")
        return self
