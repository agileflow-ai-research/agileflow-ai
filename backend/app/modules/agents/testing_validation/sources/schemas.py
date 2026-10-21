from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputOriginAgent,
    TestGenerationInputSourceType,
    TestGenerationInputSuppliedVia,
    validate_test_generation_input_policy,
)
from app.modules.agents.testing_validation.sources.constants import (
    TEXT_MAX_CHARACTERS,
)


class StrictAgent4SourceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TestGenerationSourceStatus(StrEnum):
    READY = "READY"
    UPLOADED = "UPLOADED"
    PENDING_ANALYSIS = "PENDING_ANALYSIS"


class TestGenerationTextSourceCreate(StrictAgent4SourceContract):
    artifact_type: TestGenerationInputArtifactType
    normally_supplied_by: TestGenerationInputOriginAgent
    label: str | None = Field(default=None, max_length=200)
    content: str = Field(max_length=TEXT_MAX_CHARACTERS)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must be non-empty")
        return normalized

    @model_validator(mode="after")
    def validate_policy(self) -> "TestGenerationTextSourceCreate":
        validate_test_generation_input_policy(
            artifact_type=self.artifact_type,
            source_type=TestGenerationInputSourceType.TEXT,
            normally_supplied_by=self.normally_supplied_by,
        )
        return self


class TestGenerationSourceRecord(StrictAgent4SourceContract):
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    artifact_type: TestGenerationInputArtifactType
    source_type: TestGenerationInputSourceType
    normally_supplied_by: TestGenerationInputOriginAgent
    supplied_via: Literal[
        TestGenerationInputSuppliedVia.STANDALONE_MANUAL_INPUT
    ] = TestGenerationInputSuppliedVia.STANDALONE_MANUAL_INPUT
    label: str | None = Field(default=None, max_length=200)
    collection_status: TestGenerationSourceStatus
    created_at: datetime
    text_content: str | None = Field(default=None, max_length=TEXT_MAX_CHARACTERS)
    original_filename: str | None = Field(default=None, max_length=255)
    extension: str | None = Field(default=None, pattern=r"^\.[a-z0-9]+$")
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, gt=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_source_shape(self) -> "TestGenerationSourceRecord":
        validate_test_generation_input_policy(
            artifact_type=self.artifact_type,
            source_type=self.source_type,
            normally_supplied_by=self.normally_supplied_by,
        )
        file_fields = (
            self.original_filename,
            self.extension,
            self.mime_type,
            self.size_bytes,
            self.sha256,
        )
        if self.source_type is TestGenerationInputSourceType.TEXT:
            if self.collection_status is not TestGenerationSourceStatus.READY:
                raise ValueError("TEXT sources must be READY")
            if self.text_content is None or not self.text_content.strip():
                raise ValueError("TEXT sources require text_content")
            if any(value is not None for value in file_fields):
                raise ValueError("TEXT sources cannot contain file metadata")
        else:
            expected_status = (
                TestGenerationSourceStatus.UPLOADED
                if self.source_type is TestGenerationInputSourceType.DOCUMENT
                else TestGenerationSourceStatus.PENDING_ANALYSIS
            )
            if self.collection_status is not expected_status:
                raise ValueError(
                    f"{self.source_type.value} sources must be {expected_status.value}"
                )
            if self.text_content is not None or any(
                value is None for value in file_fields
            ):
                raise ValueError("File sources require complete file metadata")
        return self
