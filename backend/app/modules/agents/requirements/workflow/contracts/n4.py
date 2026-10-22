from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.modules.agents.requirements.workflow.contracts.common import StrictWorkflowContract


class RequirementN4Status(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class RequirementN4Error(StrictWorkflowContract):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class RequirementN4ResultSummary(StrictWorkflowContract):
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    analyzed_requirement_count: int = Field(ge=0)
    exact_duplicate_group_count: int = Field(ge=0)
    exact_duplicate_affected_requirement_count: int = Field(ge=0)
    semantic_duplicate_pair_count: int = Field(ge=0)
    potential_pair_count: int = Field(ge=0)
    nli_evaluated_pair_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    ambiguity_count: int = Field(ge=0)
    missing_information_count: int = Field(ge=0)
    clarity_affected_requirement_count: int = Field(ge=0)
    total_finding_count: int = Field(ge=0)
    clarification_candidate_count: int = Field(ge=0)
    total_affected_requirement_count: int = Field(ge=0)
    finding_counts: dict[str, int]
    artifact_digests: dict[str, str]
    execution_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    detector_fingerprints: dict[str, str]


class RequirementN4Execution(StrictWorkflowContract):
    node_id: str = "REQUIREMENT_QUALITY_ENGINEERING"
    node_version: str
    execution_id: str = Field(pattern=r"^N4-[0-9A-F]{16}-\d{3}$")
    attempt_id: str = Field(pattern=r"^ATT-\d{3}$")
    execution_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_number: int = Field(ge=1)
    status: RequirementN4Status
    authoritative_n3_execution_id: str = Field(pattern=r"^N3-[0-9A-F]{16}-\d{3}$")
    n3_attempt: int = Field(ge=1)
    n3_structured_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    retryable: bool = False
    error: RequirementN4Error | None = None
    result_summary: RequirementN4ResultSummary | None = None
