"""Agent 3 extraction result schema.

Generic content, metric, warning, and status models live in the shared document
extraction package and are re-exported here so existing Agent 3 imports keep working.
Only the Agent 3 result envelope (A3UP identity and ImplementationArtifactType) is defined
in this module.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.document_extraction.schemas import (
    DOCXBlock,
    DOCXBlockType,
    DOCXContent,
    DOCXMetrics,
    DocumentType,
    ExtractionContent,
    ExtractionMetrics,
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    ExtractionWarningLocation,
    MarkdownContent,
    PDFContent,
    PDFMetrics,
    PDFPage,
    StructuredContent,
    StructuredMetrics,
    TextContent,
    TextMetrics,
    validate_content_matches_type,
)
from app.modules.agents.implementation.contracts.schemas import ImplementationArtifactType

__all__ = [
    "DOCXBlock",
    "DOCXBlockType",
    "DOCXContent",
    "DOCXMetrics",
    "DocumentExtractionResult",
    "DocumentType",
    "ExtractionContent",
    "ExtractionMetrics",
    "ExtractionStatus",
    "ExtractionWarning",
    "ExtractionWarningCode",
    "ExtractionWarningLocation",
    "MarkdownContent",
    "PDFContent",
    "PDFMetrics",
    "PDFPage",
    "StructuredContent",
    "StructuredMetrics",
    "TextContent",
    "TextMetrics",
]


class DocumentExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    artifact_type: ImplementationArtifactType
    original_filename: str = Field(min_length=1, max_length=255)
    document_type: DocumentType
    status: ExtractionStatus
    extractor_version: str = Field(pattern=r"^\d+$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: ExtractionContent
    metrics: ExtractionMetrics
    warnings: list[ExtractionWarning]
    extracted_at: datetime

    @model_validator(mode="after")
    def validate_document_shape(self) -> "DocumentExtractionResult":
        validate_content_matches_type(self.document_type, self.content, self.metrics)
        return self
