from datetime import datetime
from enum import StrEnum

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
