"""Typed Agent 4 TEST_GENERATION input sources.

A source is a manually supplied artifact with stable identity and honest provenance.
It never carries normalized content, classification, readiness, or plan information.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.document_extraction.schemas import ExtractionStatus
from app.common.status import AgentRunMode
from app.modules.agents.testing_validation.contracts.enums import (
    Agent4ArtifactType,
    Agent4InputSourceType,
    InputOriginAgent,
    InputProcessingStatus,
    SuppliedVia,
)
from app.modules.agents.testing_validation.inputs.constants import (
    MAX_LABEL_CHARACTERS,
    MAX_TEXT_SOURCE_CHARACTERS,
)


class TestGenerationSource(BaseModel):
    """Public representation of one collected source. Storage paths and owners are never included."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^(LOCAL|A4UP)-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    run_mode: Literal[AgentRunMode.TEST_GENERATION] = AgentRunMode.TEST_GENERATION
    artifact_type: Agent4ArtifactType
    source_type: Agent4InputSourceType
    normally_supplied_by: InputOriginAgent
    supplied_via: SuppliedVia = SuppliedVia.STANDALONE_MANUAL_INPUT
    label: str | None = Field(default=None, max_length=MAX_LABEL_CHARACTERS)
    processing_status: InputProcessingStatus
    text_content: str | None = None
    original_filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, gt=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    extraction_status: ExtractionStatus | None = None
    created_at: datetime


class TextSourceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_type: Agent4ArtifactType
    origin_agent: InputOriginAgent | None = None
    label: str | None = Field(default=None, max_length=MAX_LABEL_CHARACTERS)
    content: str = Field(max_length=MAX_TEXT_SOURCE_CHARACTERS)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("content")
    @classmethod
    def require_nonblank_content(cls, value: str) -> str:
        # Internal formatting is preserved. Only leading and trailing whitespace is trimmed.
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must be non-empty")
        return normalized
