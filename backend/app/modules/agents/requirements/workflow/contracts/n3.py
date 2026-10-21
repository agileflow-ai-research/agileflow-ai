from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.modules.agents.requirements.workflow.contracts.common import StrictWorkflowContract


class RequirementN3Status(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class RequirementN3Error(StrictWorkflowContract):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class RequirementN3ResultSummary(StrictWorkflowContract):
    candidate_count: int = Field(ge=0)
    functional_requirement_count: int = Field(ge=0)
    non_functional_requirement_count: int = Field(ge=0)
    excluded_candidate_count: int = Field(ge=0)
    candidate_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_set_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    classifier_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class RequirementN3Execution(StrictWorkflowContract):
    node_id: str = "REQUIREMENT_DISCOVERY_AND_STRUCTURING"
    node_version: str
    execution_id: str = Field(pattern=r"^N3-[0-9A-F]{16}-\d{3}$")
    attempt_id: str = Field(pattern=r"^ATT-\d{3}$")
    execution_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_number: int = Field(ge=1)
    status: RequirementN3Status
    n2_execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    chunk_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    discovery_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_detector_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    classifier_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    structuring_contract_version: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error: RequirementN3Error | None = None
    retryable: bool = False
    result_summary: RequirementN3ResultSummary | None = None
