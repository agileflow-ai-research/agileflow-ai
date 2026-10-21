from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.testing_validation.context_testability.testability.schemas import (
    TestabilityStatus,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode

from .constants import (
    FEASIBILITY_ENGINE_VERSION,
    FEASIBILITY_POLICY_VERSION,
    FEASIBILITY_SCHEMA_VERSION,
    TECHNOLOGY_CATALOG_VERSION,
    TechnicalEvidenceCategory,
)


class StrictFeasibilityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FeasibilityStatus(StrEnum):
    NOT_READY = "NOT_READY"
    SPECIFICATION_ONLY = "SPECIFICATION_ONLY"
    EXECUTABLE_POSSIBLE = "EXECUTABLE_POSSIBLE"


class RepresentationRecommendation(StrEnum):
    SPECIFICATION = "SPECIFICATION"
    EXECUTABLE_CODE = "EXECUTABLE_CODE"
    STRUCTURED_ARTIFACT = "STRUCTURED_ARTIFACT"


class FeasibilityFindingSeverity(StrEnum):
    BLOCKING_EXECUTABLE = "BLOCKING_EXECUTABLE"
    WARNING = "WARNING"


class TechnicalEvidenceItem(StrictFeasibilityContract):
    category: TechnicalEvidenceCategory
    values: list[str]
    node_ids: list[str]
    link_ids: list[str]
    semantic_fact_ids: list[str]
    source_ids: list[str]
    chunk_ids: list[str]

    @model_validator(mode="after")
    def validate_item(self):
        for values in (
            self.values, self.node_ids, self.link_ids, self.semantic_fact_ids,
            self.source_ids, self.chunk_ids,
        ):
            if values != sorted(set(values)):
                raise ValueError("technical evidence must be unique and canonical")
        return self


class GenerationProfile(StrictFeasibilityContract):
    language: str = Field(min_length=1, max_length=80)
    test_framework: str = Field(min_length=1, max_length=80)
    automation_surface: Literal["UNIT", "API", "INTEGRATION", "SERVICE", "UI", "E2E", "REGRESSION", "SECURITY", "ACCEPTANCE"]
    package_ecosystem: str | None = Field(default=None, max_length=80)
    backend_framework: str | None = Field(default=None, max_length=80)
    frontend_framework: str | None = Field(default=None, max_length=80)
    evidence_node_ids: list[str]
    evidence_link_ids: list[str]


class FeasibilityFinding(StrictFeasibilityContract):
    finding_id: str = Field(pattern=r"^A4FBF-[0-9a-f]{32}$")
    output_code: TestGenerationOutputCode
    severity: FeasibilityFindingSeverity
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    message: str = Field(min_length=1, max_length=500)
    technical_categories: list[TechnicalEvidenceCategory]
    evidence_values: list[str]
    related_node_ids: list[str]
    related_link_ids: list[str]
    semantic_fact_ids: list[str]
    source_ids: list[str]
    chunk_ids: list[str]


class OutputFeasibilityAssessment(StrictFeasibilityContract):
    output_code: TestGenerationOutputCode
    n4_2_status: TestabilityStatus
    feasibility: FeasibilityStatus
    recommended_representation: RepresentationRecommendation | None
    policy_version: Literal[FEASIBILITY_POLICY_VERSION]
    technical_evidence_categories: list[TechnicalEvidenceCategory]
    generation_profile: GenerationProfile | None = None
    execution_status: Literal["NOT_EXECUTED"] | None = None
    finding_ids: list[str]
    evidence_node_ids: list[str]
    evidence_link_ids: list[str]
    semantic_fact_ids: list[str]
    source_ids: list[str]
    chunk_ids: list[str]
    reason_codes: list[str]

    @model_validator(mode="after")
    def validate_assessment(self):
        for values in (
            self.technical_evidence_categories, self.finding_ids,
            self.evidence_node_ids, self.evidence_link_ids,
            self.semantic_fact_ids, self.source_ids, self.chunk_ids,
            self.reason_codes,
        ):
            if values != sorted(set(values), key=lambda item: getattr(item, "value", item)):
                raise ValueError("assessment evidence must be unique and canonical")
        if self.n4_2_status is TestabilityStatus.NOT_READY:
            if (
                self.feasibility is not FeasibilityStatus.NOT_READY
                or self.recommended_representation is not None
            ):
                raise ValueError("N4.2 NOT_READY cannot be upgraded")
        if self.feasibility is FeasibilityStatus.EXECUTABLE_POSSIBLE:
            if (
                self.recommended_representation is not RepresentationRecommendation.EXECUTABLE_CODE
                or self.generation_profile is None
                or self.execution_status != "NOT_EXECUTED"
            ):
                raise ValueError("executable feasibility requires an unexecuted generation profile")
        elif self.generation_profile is not None or self.execution_status is not None:
            raise ValueError("non-executable feasibility cannot carry an execution profile")
        if self.feasibility is FeasibilityStatus.SPECIFICATION_ONLY and self.recommended_representation not in {
            RepresentationRecommendation.SPECIFICATION,
            RepresentationRecommendation.STRUCTURED_ARTIFACT,
        }:
            raise ValueError("specification-only feasibility requires a non-code representation")
        return self


class Agent4FeasibilityResult(StrictFeasibilityContract):
    schema_version: Literal[FEASIBILITY_SCHEMA_VERSION]
    engine_version: Literal[FEASIBILITY_ENGINE_VERSION]
    policy_version: Literal[FEASIBILITY_POLICY_VERSION]
    technology_catalog_version: Literal[TECHNOLOGY_CATALOG_VERSION]
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    confirmation_id: str = Field(pattern=r"^A4N1C-[0-9a-f]{32}$")
    selection_revision: int = Field(ge=1)
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_outputs: list[TestGenerationOutputCode] = Field(min_length=1)
    traceability_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    testability_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    testability_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    technical_evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    technical_evidence_inventory: list[TechnicalEvidenceItem]
    output_assessments: list[OutputFeasibilityAssessment] = Field(min_length=1)
    overall_feasibility: FeasibilityStatus
    blocking_executable_finding_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    findings: list[FeasibilityFinding]
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: datetime

    @model_validator(mode="after")
    def validate_result(self):
        if [item.output_code for item in self.output_assessments] != self.selected_outputs:
            raise ValueError("feasibility assessments must match selected outputs")
        if [item.category for item in self.technical_evidence_inventory] != list(TechnicalEvidenceCategory):
            raise ValueError("technical inventory must use canonical complete ordering")
        finding_ids = [item.finding_id for item in self.findings]
        if finding_ids != sorted(set(finding_ids)):
            raise ValueError("feasibility findings must be unique and canonical")
        if any(not set(item.finding_ids).issubset(finding_ids) for item in self.output_assessments):
            raise ValueError("assessment finding references are invalid")
        if self.blocking_executable_finding_count != sum(
            item.severity is FeasibilityFindingSeverity.BLOCKING_EXECUTABLE
            for item in self.findings
        ):
            raise ValueError("blocking executable finding count is inconsistent")
        if self.warning_count != sum(
            item.severity is FeasibilityFindingSeverity.WARNING for item in self.findings
        ):
            raise ValueError("warning finding count is inconsistent")
        values = {item.feasibility for item in self.output_assessments}
        expected = (
            FeasibilityStatus.NOT_READY if FeasibilityStatus.NOT_READY in values
            else FeasibilityStatus.EXECUTABLE_POSSIBLE
            if values == {FeasibilityStatus.EXECUTABLE_POSSIBLE}
            else FeasibilityStatus.SPECIFICATION_ONLY
        )
        if self.overall_feasibility is not expected:
            raise ValueError("overall feasibility is inconsistent")
        known_nodes = {value for item in self.technical_evidence_inventory for value in item.node_ids}
        known_links = {value for item in self.technical_evidence_inventory for value in item.link_ids}
        known_facts = {value for item in self.technical_evidence_inventory for value in item.semantic_fact_ids}
        known_sources = {value for item in self.technical_evidence_inventory for value in item.source_ids}
        known_chunks = {value for item in self.technical_evidence_inventory for value in item.chunk_ids}
        for item in [*self.findings, *self.output_assessments]:
            if (
                not set(item.evidence_node_ids if hasattr(item, "evidence_node_ids") else item.related_node_ids).issubset(known_nodes)
                or not set(item.evidence_link_ids if hasattr(item, "evidence_link_ids") else item.related_link_ids).issubset(known_links)
                or not set(item.semantic_fact_ids).issubset(known_facts)
                or not set(item.source_ids).issubset(known_sources)
                or not set(item.chunk_ids).issubset(known_chunks)
            ):
                raise ValueError("feasibility evidence references are invalid")
        return self
