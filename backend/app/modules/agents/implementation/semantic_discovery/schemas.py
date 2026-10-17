from datetime import datetime
from enum import StrEnum

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
