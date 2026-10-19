"""Agent 4 extraction result. Generic content and metric models come from the shared package."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.document_extraction.schemas import (
    DocumentType,
    ExtractionContent,
    ExtractionMetrics,
    ExtractionStatus,
    ExtractionWarning,
    validate_content_matches_type,
)
from app.common.status import AgentRunMode
from app.modules.agents.testing_validation.contracts.enums import Agent4ArtifactType


class TestGenerationExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^A4UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    run_mode: Literal[AgentRunMode.TEST_GENERATION] = AgentRunMode.TEST_GENERATION
    artifact_type: Agent4ArtifactType
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
    def validate_document_shape(self) -> "TestGenerationExtractionResult":
        validate_content_matches_type(self.document_type, self.content, self.metrics)
        return self
