from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType


class RequirementOutputCode(StrEnum):
    FUNCTIONAL_REQUIREMENTS = "FUNCTIONAL_REQUIREMENTS"
    NON_FUNCTIONAL_REQUIREMENTS = "NON_FUNCTIONAL_REQUIREMENTS"
    USER_STORIES = "USER_STORIES"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    PERSONAS = "PERSONAS"
    SRS = "SRS"


class RequirementN1State(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETE = "COMPLETE"


class RequirementN2Status(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class RequirementN2SourceStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class RequirementN2SourceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RequirementN2Error(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    affected_source_ids: list[str] = Field(default_factory=list)


class RequirementN2SourceProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    processing_status: RequirementN2SourceStatus = RequirementN2SourceStatus.READY
    preparation_status: RequirementN2SourceStatus = RequirementN2SourceStatus.READY
    chunk_count: int = Field(default=0, ge=0)
    error: RequirementN2Error | None = None


class RequirementN2ResultSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_count: int = Field(ge=1)
    completed_source_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)


class RequirementN2Execution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = "PROCESSING_AND_CHUNKING"
    node_version: str
    execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    attempt_id: str = Field(pattern=r"^ATT-\d{3}$")
    execution_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_number: int = Field(ge=1)
    status: RequirementN2Status
    confirmed_source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_sources: list[RequirementN2SourceSnapshot] = Field(min_length=1)
    source_progress: list[RequirementN2SourceProgress] = Field(min_length=1)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error: RequirementN2Error | None = None
    retryable: bool = False
    result_summary: RequirementN2ResultSummary | None = None
    chunk_set_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class RequirementOutputSelectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_outputs: list[RequirementOutputCode] = Field(min_length=1)

    @field_validator("selected_outputs")
    @classmethod
    def reject_duplicates(
        cls, value: list[RequirementOutputCode]
    ) -> list[RequirementOutputCode]:
        if len(value) != len(set(value)):
            raise ValueError("selected_outputs must not contain duplicates")
        return value


class RequirementN1Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_at: datetime


class RequirementWorkflowRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    workflow_version: str
    agent_project_id: str
    owner_user_id: str
    selected_outputs: list[RequirementOutputCode]
    selection_revision: int = Field(ge=0)
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    n1_confirmation: RequirementN1Confirmation | None = None
    n2_executions: list[RequirementN2Execution] = Field(default_factory=list)
    current_n2_execution_id: str | None = None
    created_at: datetime
    updated_at: datetime


class RequirementWorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    workflow_version: str
    agent_project_id: str
    selected_outputs: list[RequirementOutputCode]
    selection_revision: int
    selection_digest: str
    source_set_digest: str
    source_count: int
    n1_state: RequirementN1State
    n1_confirmation_current: bool
    confirmed_source_set_digest: str | None = None
    confirmed_selection_digest: str | None = None
    confirmed_at: datetime | None = None
    n2_execution: RequirementN2Execution | None = None
    n2_is_current: bool = False
    n2_execution_count: int = 0
    created_at: datetime
    updated_at: datetime
