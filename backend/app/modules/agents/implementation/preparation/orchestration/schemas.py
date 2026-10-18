from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.agents.implementation.contracts.enums import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
)
from .constants import (
    PreparationStage,
    ProjectPreparationStatus,
    SourcePreparationStatus,
)


class PreparationTextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_id: str = Field(pattern=r"^LOCAL-[A-Za-z0-9_-]{1,80}$")
    artifact_type: ImplementationArtifactType
    label: str | None = Field(default=None, max_length=200)
    content: str = Field(max_length=200_000)

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


class ProjectPreparationStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_inputs: list[PreparationTextInput] = Field(
        default_factory=list, max_length=50
    )

    @model_validator(mode="after")
    def validate_text_inputs(self) -> "ProjectPreparationStartRequest":
        if len({item.input_id for item in self.text_inputs}) != len(
            self.text_inputs
        ):
            raise ValueError("text input IDs must be unique")
        if sum(len(item.content) for item in self.text_inputs) > 1_000_000:
            raise ValueError("manual text input exceeds the total size limit")
        return self


class PreparationSourceError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class PreparationSourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_kind: ImplementationInputSourceType
    artifact_type: ImplementationArtifactType
    label: str | None = None
    filename: str | None = None
    status: SourcePreparationStatus
    current_stage: PreparationStage | None = None
    error: PreparationSourceError | None = None


class PersistedPreparationSource(PreparationSourceStatus):
    text_content: str | None = None


class ProjectPreparationStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_project_id: str
    status: ProjectPreparationStatus
    source_count: int = Field(ge=0)
    eligible_source_count: int = Field(ge=0)
    processed_source_count: int = Field(ge=0)
    completed_source_count: int = Field(ge=0)
    active_source_count: int = Field(ge=0)
    failed_source_count: int = Field(ge=0)
    sources: list[PreparationSourceStatus]
    requires_human_review: bool
    human_review_source_count: int = Field(ge=0)
    started_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectPreparationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_project_id: str
    owner_user_id: str
    status: ProjectPreparationStatus
    sources: list[PersistedPreparationSource]
    started_at: datetime
    updated_at: datetime
