from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.agents.implementation.contracts.enums import ImplementationOutputCode
from app.modules.agents.implementation.preparation.schemas import ArtifactDetectionLabel
from app.modules.agents.implementation.preparation.readiness.schemas import (
    FindingSeverity,
    HumanResolutionDecision,
    ReadinessStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StackAdaptationRequest(StrictModel):
    decision: HumanResolutionDecision
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str | None = Field(default=None, max_length=500)


class TrustedReadinessEvaluationRequest(StrictModel):
    selected_outputs: list[ImplementationOutputCode] = Field(min_length=1, max_length=8)
    stack_adaptation: StackAdaptationRequest | None = None

    @field_validator("selected_outputs")
    @classmethod
    def unique_outputs(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("selected_outputs must not contain duplicates")
        return values


class TrustedReadinessContinuationRequest(StrictModel):
    expected_readiness_id: str = Field(pattern=r"^RDY-[0-9A-F]{24}$")
    expected_readiness_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledged_warning_codes: list[str] = Field(min_length=1)

    @field_validator("acknowledged_warning_codes")
    @classmethod
    def unique_warning_codes(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("acknowledged_warning_codes must not contain duplicates")
        if any(not value.strip() for value in values):
            raise ValueError("warning codes must not be blank")
        return values


class TrustedReadinessContinuationDecision(StrictModel):
    decision_id: str = Field(pattern=r"^RCD-[0-9a-f]{32}$")
    agent_project_id: str
    readiness_id: str = Field(pattern=r"^RDY-[0-9A-F]{24}$")
    readiness_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    readiness_policy_version: str
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_specification_id: str
    stack_adaptation_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    acknowledged_warning_codes: list[str]
    warning_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer_owner_id: str
    decision: Literal["CONTINUE_WITH_WARNINGS"] = "CONTINUE_WITH_WARNINGS"
    created_at: datetime


class RequirementKind(StrEnum):
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"


class TrustedCoverageItem(StrictModel):
    category: ArtifactDetectionLabel
    present: bool
    project_item_ids: list[str] = Field(default_factory=list)


class TrustedReadinessFinding(StrictModel):
    finding_id: str = Field(pattern=r"^TRF-[0-9a-f]{16}$")
    issue_code: str
    severity: FindingSeverity
    title: str
    message: str
    related_selected_outputs: list[ImplementationOutputCode] = Field(default_factory=list)
    related_project_item_ids: list[str] = Field(default_factory=list)
    related_artifact_categories: list[ArtifactDetectionLabel] = Field(default_factory=list)
    resolution_action: HumanResolutionDecision | None = None
    provided_value: str | None = None
    supported_value: str | None = None
    resolved: bool = False


class TrustedOutputReadiness(StrictModel):
    output: ImplementationOutputCode
    status: ReadinessStatus
    finding_ids: list[str] = Field(default_factory=list)


class TrustedStackAdaptation(StrictModel):
    decision: HumanResolutionDecision
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved: bool
    note: str | None = None
    approved_at: datetime | None = None


class TrustedReadinessSnapshot(StrictModel):
    readiness_id: str = Field(pattern=r"^RDY-[0-9A-F]{24}$")
    readiness_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_project_id: str
    status: ReadinessStatus
    selected_outputs: list[ImplementationOutputCode]
    policy_version: str
    schema_version: str
    project_specification_id: str | None = None
    source_set_digest: str | None = None
    project_specification_decision_digest: str | None = None
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    stack_adaptation: TrustedStackAdaptation | None = None
    coverage: list[TrustedCoverageItem]
    output_readiness: list[TrustedOutputReadiness]
    findings: list[TrustedReadinessFinding]
    effective_stack: dict[str, str]
    evaluated_at: datetime
    current: bool = True
    continuation_required: bool = False
    continuation_approved: bool = False
    continuation_decision_id: str | None = None
