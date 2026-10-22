"""
Pydantic contracts for the N4.4 context decision (CD1).

Holds the per-output profiles (decision, planning_allowed, references to the TB1 and FB1
assessments), the planning profiles N5 will read, the consolidated findings with their
origins, and the overall decision. CD1 reads persisted TR1, TB1, and FB1 only, so its
fingerprints show which upstream results it consumed.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.testing_validation.context_testability.feasibility.schemas import (
    FeasibilityStatus,
    RepresentationRecommendation,
)
from app.modules.agents.testing_validation.context_testability.testability.schemas import (
    TestabilityStatus,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode

from .constants import (
    CONTEXT_DECISION_ENGINE_VERSION,
    CONTEXT_DECISION_POLICY_VERSION,
    CONTEXT_DECISION_SCHEMA_VERSION,
    ConsolidatedFindingOrigin,
    ConsolidatedFindingSeverity,
    ContextDecisionStatus,
)


class StrictContextDecisionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConsolidatedOriginReference(StrictContextDecisionContract):
    origin: ConsolidatedFindingOrigin
    origin_finding_id: str = Field(pattern=r"^(?:A4TBF|A4FBF)-[0-9a-f]{32}$")


class ConsolidatedContextFinding(StrictContextDecisionContract):
    consolidated_finding_id: str = Field(pattern=r"^A4CTXF-[0-9a-f]{32}$")
    output_code: TestGenerationOutputCode
    severity: ConsolidatedFindingSeverity
    category: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    display_message: str = Field(min_length=1, max_length=500)
    origin_references: list[ConsolidatedOriginReference] = Field(min_length=1)
    evidence_node_ids: list[str]
    evidence_link_ids: list[str]
    semantic_fact_ids: list[str]
    source_ids: list[str]
    chunk_ids: list[str]

    @model_validator(mode="after")
    def validate_finding(self):
        origin_keys = [(item.origin.value, item.origin_finding_id) for item in self.origin_references]
        if origin_keys != sorted(set(origin_keys)):
            raise ValueError("finding origins must be unique and canonical")
        for values in (
            self.evidence_node_ids, self.evidence_link_ids, self.semantic_fact_ids,
            self.source_ids, self.chunk_ids,
        ):
            if values != sorted(set(values)):
                raise ValueError("finding evidence must be unique and canonical")
        return self


class OutputContextDecisionProfile(StrictContextDecisionContract):
    profile_id: str = Field(pattern=r"^A4CTXP-[0-9a-f]{32}$")
    output_code: TestGenerationOutputCode
    decision: ContextDecisionStatus
    planning_allowed: bool
    testability_status: TestabilityStatus
    feasibility_status: FeasibilityStatus
    recommended_representation: RepresentationRecommendation | None
    testability_assessment_ref: str = Field(pattern=r"^A4TBA-[0-9a-f]{32}$")
    feasibility_assessment_ref: str = Field(pattern=r"^A4FBA-[0-9a-f]{32}$")
    generation_profile_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    execution_status: Literal["NOT_EXECUTED"] | None = None
    blocking_finding_ids: list[str]
    warning_finding_ids: list[str]
    evidence_node_ids: list[str]
    evidence_link_ids: list[str]
    semantic_fact_ids: list[str]
    reason_codes: list[str]

    @model_validator(mode="after")
    def validate_profile(self):
        for values in (
            self.blocking_finding_ids, self.warning_finding_ids,
            self.evidence_node_ids, self.evidence_link_ids,
            self.semantic_fact_ids, self.reason_codes,
        ):
            if values != sorted(set(values)):
                raise ValueError("profile references must be unique and canonical")
        expected = (
            ContextDecisionStatus.BLOCKED
            if self.testability_status is TestabilityStatus.NOT_READY
            else ContextDecisionStatus.PROCEED_WITH_WARNINGS
            if self.testability_status is TestabilityStatus.READY_WITH_WARNINGS
            or (
                self.feasibility_status is FeasibilityStatus.SPECIFICATION_ONLY
                and not (
                    self.output_code is TestGenerationOutputCode.TEST_TRACEABILITY
                    and self.recommended_representation
                    is RepresentationRecommendation.STRUCTURED_ARTIFACT
                )
            )
            else ContextDecisionStatus.PROCEED
        )
        if self.decision is not expected:
            raise ValueError("decision does not match CP1")
        if self.planning_allowed != (self.decision is not ContextDecisionStatus.BLOCKED):
            raise ValueError("planning eligibility does not match decision")
        if (self.decision is ContextDecisionStatus.BLOCKED) != bool(self.blocking_finding_ids):
            raise ValueError("blocked profiles require blocking findings only")
        if self.feasibility_status is FeasibilityStatus.EXECUTABLE_POSSIBLE:
            if (
                self.recommended_representation is not RepresentationRecommendation.EXECUTABLE_CODE
                or self.generation_profile_fingerprint is None
                or self.execution_status != "NOT_EXECUTED"
            ):
                raise ValueError("executable profile must remain not executed")
        elif self.generation_profile_fingerprint is not None or self.execution_status is not None:
            raise ValueError("non-executable profile cannot carry execution state")
        if self.output_code is TestGenerationOutputCode.TEST_TRACEABILITY and (
            self.recommended_representation is RepresentationRecommendation.EXECUTABLE_CODE
            or self.feasibility_status is FeasibilityStatus.EXECUTABLE_POSSIBLE
        ):
            raise ValueError("test traceability is never executable code")
        return self


class DownstreamPlanningProfile(StrictContextDecisionContract):
    output_code: TestGenerationOutputCode
    planning_allowed: bool
    recommended_representation: RepresentationRecommendation | None
    executable_code_possible: bool
    evidence_node_ids: list[str]
    evidence_link_ids: list[str]
    semantic_fact_ids: list[str]
    blocking_finding_ids: list[str]
    warning_finding_ids: list[str]


class Agent4ContextDecisionResult(StrictContextDecisionContract):
    schema_version: Literal[CONTEXT_DECISION_SCHEMA_VERSION]
    engine_version: Literal[CONTEXT_DECISION_ENGINE_VERSION]
    policy_version: Literal[CONTEXT_DECISION_POLICY_VERSION]
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    confirmation_id: str = Field(pattern=r"^A4N1C-[0-9a-f]{32}$")
    selection_revision: int = Field(ge=1)
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_outputs: list[TestGenerationOutputCode] = Field(min_length=1)
    traceability_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    traceability_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    testability_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    testability_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    feasibility_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    feasibility_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_profiles: list[OutputContextDecisionProfile] = Field(min_length=1)
    planning_profiles: list[DownstreamPlanningProfile] = Field(min_length=1)
    overall_decision: ContextDecisionStatus
    planning_allowed_output_count: int = Field(ge=0)
    blocked_output_count: int = Field(ge=0)
    blocking_count: int = Field(ge=0)
    executable_output_count: int = Field(ge=0)
    specification_output_count: int = Field(ge=0)
    structured_artifact_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    consolidated_findings: list[ConsolidatedContextFinding]
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: datetime

    @model_validator(mode="after")
    def validate_result(self):
        outputs = [item.output_code for item in self.output_profiles]
        if outputs != self.selected_outputs or [item.output_code for item in self.planning_profiles] != outputs:
            raise ValueError("profiles must match canonical selected outputs")
        if len(outputs) != len(set(outputs)):
            raise ValueError("selected outputs must be unique")
        finding_ids = [item.consolidated_finding_id for item in self.consolidated_findings]
        if finding_ids != sorted(set(finding_ids)):
            raise ValueError("consolidated findings must be unique and canonical")
        known = set(finding_ids)
        by_output = {item.output_code: item for item in self.output_profiles}
        for profile, planning in zip(self.output_profiles, self.planning_profiles):
            if not set(profile.blocking_finding_ids + profile.warning_finding_ids).issubset(known):
                raise ValueError("profile finding reference does not resolve")
            if planning.planning_allowed != (profile.decision is not ContextDecisionStatus.BLOCKED):
                raise ValueError("planning eligibility does not match decision")
            if planning.planning_allowed != profile.planning_allowed:
                raise ValueError("planning profile does not match output profile")
            if planning.blocking_finding_ids != profile.blocking_finding_ids or planning.warning_finding_ids != profile.warning_finding_ids:
                raise ValueError("planning finding references do not match profile")
        if any(item.output_code not in by_output for item in self.consolidated_findings):
            raise ValueError("finding output is not selected")
        decisions = {item.decision for item in self.output_profiles}
        expected = (
            ContextDecisionStatus.BLOCKED if ContextDecisionStatus.BLOCKED in decisions
            else ContextDecisionStatus.PROCEED_WITH_WARNINGS
            if ContextDecisionStatus.PROCEED_WITH_WARNINGS in decisions
            else ContextDecisionStatus.PROCEED
        )
        if self.overall_decision is not expected:
            raise ValueError("overall decision is inconsistent")
        counts = {
            "planning_allowed_output_count": sum(item.planning_allowed for item in self.planning_profiles),
            "blocked_output_count": sum(item.decision is ContextDecisionStatus.BLOCKED for item in self.output_profiles),
            "blocking_count": sum(item.severity is ConsolidatedFindingSeverity.BLOCKING for item in self.consolidated_findings),
            "executable_output_count": sum(item.recommended_representation is RepresentationRecommendation.EXECUTABLE_CODE for item in self.output_profiles),
            "specification_output_count": sum(item.recommended_representation is RepresentationRecommendation.SPECIFICATION for item in self.output_profiles),
            "structured_artifact_count": sum(item.recommended_representation is RepresentationRecommendation.STRUCTURED_ARTIFACT for item in self.output_profiles),
            "warning_count": sum(item.severity is ConsolidatedFindingSeverity.WARNING for item in self.consolidated_findings),
        }
        if any(getattr(self, key) != value for key, value in counts.items()):
            raise ValueError("decision summary counts are inconsistent")
        return self
