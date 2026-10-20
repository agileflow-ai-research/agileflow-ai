from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.workflow.contracts.common import (
    StrictWorkflowContract,
)


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


class RequirementN2SourceSnapshot(StrictWorkflowContract):
    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RequirementN2Error(StrictWorkflowContract):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    affected_source_ids: list[str] = Field(default_factory=list)


class RequirementN2SourceProgress(StrictWorkflowContract):
    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    processing_status: RequirementN2SourceStatus = RequirementN2SourceStatus.READY
    preparation_status: RequirementN2SourceStatus = RequirementN2SourceStatus.READY
    chunk_count: int = Field(default=0, ge=0)
    error: RequirementN2Error | None = None


class RequirementN2ResultSummary(StrictWorkflowContract):
    source_count: int = Field(ge=1)
    completed_source_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)


class RequirementN2Execution(StrictWorkflowContract):
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
