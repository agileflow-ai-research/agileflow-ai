from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DocumentType(StrEnum):
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"
    MD = "MD"
    JSON = "JSON"
    YAML = "YAML"


class ExtractionWarningCode(StrEnum):
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
    NO_TEXT_ON_PAGE = "NO_TEXT_ON_PAGE"
    CONTENT_TRUNCATED = "CONTENT_TRUNCATED"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    INVALID_STRUCTURED_CONTENT = "INVALID_STRUCTURED_CONTENT"
    UNSUPPORTED_DOCUMENT_STRUCTURE = "UNSUPPORTED_DOCUMENT_STRUCTURE"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"


class ExtractionWarningLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int | None = Field(default=None, ge=1)
    block_index: int | None = Field(default=None, ge=1)


class ExtractionWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ExtractionWarningCode
    message: str = Field(min_length=1, max_length=500)
    location: ExtractionWarningLocation | None = None


class PDFPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1)
    text: str


class PDFContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pages: list[PDFPage]
    combined_text: str


class DOCXBlockType(StrEnum):
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    TABLE = "TABLE"


class DOCXBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_index: int = Field(ge=1)
    type: DOCXBlockType
    text: str | None = None
    level: int | None = Field(default=None, ge=1, le=9)
    rows: list[list[str]] | None = None

    @model_validator(mode="after")
    def validate_block_shape(self) -> "DOCXBlock":
        if self.type is DOCXBlockType.TABLE:
            if self.rows is None or self.text is not None or self.level is not None:
                raise ValueError("TABLE block requires rows only")
        elif self.text is None or self.rows is not None:
            raise ValueError("text block requires text and cannot contain rows")
        elif self.type is DOCXBlockType.HEADING and self.level is None:
            raise ValueError("HEADING block requires a level")
        elif self.type is DOCXBlockType.PARAGRAPH and self.level is not None:
            raise ValueError("PARAGRAPH block cannot contain a heading level")
        return self


class DOCXContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocks: list[DOCXBlock]
    combined_text: str


class TextContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    combined_text: str


class MarkdownContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markdown: str
    combined_text: str


class StructuredContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    structured_content: Any
    normalized_text: str


class PDFMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_count: int = Field(ge=0)
    processed_page_count: int = Field(ge=0)
    pages_with_text: int = Field(ge=0)
    pages_without_text: int = Field(ge=0)
    extracted_character_count: int = Field(ge=0)


class DOCXMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_count: int = Field(ge=0)
    paragraph_count: int = Field(ge=0)
    heading_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    extracted_character_count: int = Field(ge=0)


class TextMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extracted_character_count: int = Field(ge=0)
    line_count: int = Field(ge=0)


class StructuredMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root_type: Literal["OBJECT", "ARRAY", "STRING", "NUMBER", "BOOLEAN", "NULL"]
    extracted_character_count: int = Field(ge=0)


ExtractionContent = PDFContent | DOCXContent | TextContent | MarkdownContent | StructuredContent
ExtractionMetrics = PDFMetrics | DOCXMetrics | TextMetrics | StructuredMetrics
