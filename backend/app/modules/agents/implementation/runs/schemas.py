from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.status import AgentType
from app.modules.agents.implementation.contracts.enums import (
    ImplementationOutputCode,
    GitHubRepositoryVisibility,
)
from app.modules.agents.implementation.preparation.consolidation.schemas import (
    TrustedProjectSpecification,
)
from app.modules.agents.implementation.preparation.readiness.trusted.schemas import (
    TrustedReadinessSnapshot,
    TrustedStackAdaptation,
)

from .constants import IMPLEMENTATION_RUN_SNAPSHOT_KIND


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImplementationRunStatus(StrEnum):
    READY_FOR_GENERATION = "READY_FOR_GENERATION"


class FinalApprovalDecision(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ImplementationRunCreateRequest(StrictModel):
    approved: Literal[True]
    acknowledged_warning_codes: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=8, max_length=128)
    expected_project_specification_id: str = Field(
        pattern=r"^TPS-[0-9A-F]{24}$"
    )
    expected_readiness_id: str = Field(pattern=r"^RDY-[0-9A-F]{24}$")
    expected_readiness_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_stack_adaptation_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    @field_validator("acknowledged_warning_codes")
    @classmethod
    def unique_warning_codes(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("acknowledged_warning_codes must not contain duplicates")
        if any(not value.strip() for value in values):
            raise ValueError("warning codes must not be blank")
        return values


class FinalApprovalSnapshot(StrictModel):
    approval_id: str = Field(pattern=r"^APR-[0-9a-f]{32}$")
    agent_project_id: str
    reviewer_owner_id: str
    decision: FinalApprovalDecision
    acknowledged_warning_codes: list[str]
    project_specification_id: str
    project_specification_source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_specification_decision_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    readiness_id: str
    readiness_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str
    created_at: datetime


class DeliveryConnectionSnapshot(StrictModel):
    owner_id: str
    github_user_id: int
    github_login: str
    installation_account_login: str
    account_type: Literal["User"]
    status: Literal["CONNECTED"]


class DeliveryRepositorySnapshot(StrictModel):
    binding_id: str
    repository_id: int
    owner: str
    name: str
    full_name: str
    html_url: str
    visibility: GitHubRepositoryVisibility
    default_branch: str | None = None
    is_empty: bool


class DeliverySnapshot(StrictModel):
    policy_version: str
    configured: bool
    delivery_ready: bool
    required_before_delivery_execution: bool
    connection: DeliveryConnectionSnapshot | None = None
    repository: DeliveryRepositorySnapshot | None = None


class ImplementationRunInputSnapshot(StrictModel):
    snapshot_kind: Literal[IMPLEMENTATION_RUN_SNAPSHOT_KIND]
    schema_version: str
    run_status: ImplementationRunStatus
    project_specification_id: str
    project_specification_source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_specification_decision_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    trusted_project_specification: TrustedProjectSpecification
    readiness_id: str
    readiness_policy_version: str
    readiness_status: str
    readiness_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    trusted_readiness: TrustedReadinessSnapshot
    selected_outputs: list[ImplementationOutputCode] = Field(min_length=1)
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_stack: dict[str, str]
    stack_adaptation_decision: TrustedStackAdaptation | None = None
    approval: FinalApprovalSnapshot
    delivery_snapshot: DeliverySnapshot
    traceability_root_refs: list[str]


class ImplementationRunResponse(StrictModel):
    run_id: str
    agent_project_id: str
    agent_type: AgentType
    run_status: ImplementationRunStatus
    created_at: datetime
    project_specification_id: str
    project_specification_source_set_digest: str
    project_specification_decision_digest: str
    readiness_id: str
    readiness_policy_version: str
    readiness_status: str
    readiness_fingerprint: str
    selected_outputs: list[ImplementationOutputCode]
    selected_outputs_digest: str
    implementation_stack: dict[str, str]
    stack_adaptation_decision: TrustedStackAdaptation | None
    approval_id: str
    approval_fingerprint: str
    delivery_snapshot: DeliverySnapshot
    traceability_root_refs: list[str]
    schema_version: str
    approved_input: ImplementationRunInputSnapshot


class ImplementationRunListItem(StrictModel):
    run_id: str
    run_status: ImplementationRunStatus
    created_at: datetime
    readiness_status: str
    readiness_id: str
    readiness_fingerprint: str
    selected_outputs: list[ImplementationOutputCode]
    approval_id: str
    delivery_configured: bool
