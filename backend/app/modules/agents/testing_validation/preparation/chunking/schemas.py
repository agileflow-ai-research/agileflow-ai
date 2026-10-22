from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.preparation.normalization.schemas import (
    NormalizedSegmentKind,
)


class StrictChunkContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TestingChunkSourceSpan(StrictChunkContract):
    source_segment_id: str = Field(pattern=r"^A4SEG-[0-9a-f]{32}$")
    segment_kind: NormalizedSegmentKind
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    block_index: int | None = Field(default=None, ge=1)
    structured_path: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_range(self) -> "TestingChunkSourceSpan":
        if self.end_offset < self.start_offset:
            raise ValueError("source span end must not precede its start")
        return self


class TestingChunk(StrictChunkContract):
    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    normalized_artifact_id: str = Field(pattern=r"^A4ART-[0-9a-f]{32}$")
    artifact_type: TestGenerationInputArtifactType
    source_type: TestGenerationInputSourceType
    sequence: int = Field(ge=1)
    heading_path: list[str] = Field(default_factory=list)
    structure_type: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_count: int = Field(ge=1)
    overlap_token_count: int = Field(ge=0)
    source_segment_ids: list[str] = Field(min_length=1)
    source_spans: list[TestingChunkSourceSpan] = Field(min_length=1)
    source_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalization_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    inherited_warning_codes: list[str] = Field(default_factory=list)


class TestingChunkMetrics(StrictChunkContract):
    chunk_count: int = Field(ge=1)
    total_tokens: int = Field(ge=1)
    min_chunk_tokens: int = Field(ge=1)
    max_chunk_tokens: int = Field(ge=1)


class TestingChunkSet(StrictChunkContract):
    schema_version: Literal["1"] = "1"
    chunker_version: str
    policy_version: str
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_set_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    normalized_artifact_id: str = Field(pattern=r"^A4ART-[0-9a-f]{32}$")
    normalization_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_ids: list[str] = Field(min_length=1)
    chunks: list[TestingChunk] = Field(min_length=1)
    metrics: TestingChunkMetrics
    created_at: datetime

    @model_validator(mode="after")
    def validate_manifest(self) -> "TestingChunkSet":
        if self.chunk_ids != [chunk.chunk_id for chunk in self.chunks]:
            raise ValueError("chunk manifest order does not match chunks")
        if self.metrics.chunk_count != len(self.chunks):
            raise ValueError("chunk count does not match chunks")
        if [chunk.sequence for chunk in self.chunks] != list(
            range(1, len(self.chunks) + 1)
        ):
            raise ValueError("chunk sequence must be contiguous")
        return self
