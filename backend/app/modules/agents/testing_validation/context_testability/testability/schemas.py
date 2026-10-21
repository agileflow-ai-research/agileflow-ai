from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode

from .constants import (
    OUTPUT_POLICY_VERSION,
    TESTABILITY_ENGINE_VERSION,
    TESTABILITY_SCHEMA_VERSION,
    EvidenceCategory,
)


class StrictTestabilityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TestabilityStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


class TestabilityFindingSeverity(StrEnum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"


class EvidenceInventoryItem(StrictTestabilityContract):
    category: EvidenceCategory
    observed_count: int = Field(ge=0)
    node_ids: list[str] = Field(default_factory=list)
    link_ids: list[str] = Field(default_factory=list)
    semantic_fact_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_inventory(self):
        for values in (self.node_ids, self.link_ids, self.semantic_fact_ids):
            if values != sorted(set(values)):
                raise ValueError("evidence references must be unique and canonical")
        if self.observed_count != len(set(self.node_ids + self.link_ids)):
            raise ValueError("observed_count must match unique evidence references")
        return self


class EvidenceRequirementAssessment(StrictTestabilityContract):
    requirement_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    description: str = Field(min_length=1, max_length=300)
    required_categories: list[EvidenceCategory] = Field(min_length=1)
    satisfied: bool
    observed_count: int = Field(ge=0)
    evidence_node_ids: list[str] = Field(default_factory=list)
    evidence_link_ids: list[str] = Field(default_factory=list)
    semantic_fact_ids: list[str] = Field(default_factory=list)


class MissingContextFinding(StrictTestabilityContract):
    finding_id: str = Field(pattern=r"^A4TBF-[0-9a-f]{32}$")
    output_code: TestGenerationOutputCode
    severity: TestabilityFindingSeverity
    category: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    message: str = Field(min_length=1, max_length=500)
    required_evidence_categories: list[EvidenceCategory] = Field(default_factory=list)
    observed_count: int = Field(ge=0)
    related_node_ids: list[str] = Field(default_factory=list)
    related_link_ids: list[str] = Field(default_factory=list)
    related_finding_ids: list[str] = Field(default_factory=list)
    semantic_fact_ids: list[str] = Field(default_factory=list)


class OutputTestabilityAssessment(StrictTestabilityContract):
    output_code: TestGenerationOutputCode
    status: TestabilityStatus
    policy_version: Literal[OUTPUT_POLICY_VERSION]
    mandatory_requirements: list[EvidenceRequirementAssessment]
    supporting_requirements: list[EvidenceRequirementAssessment]
    satisfied_requirements: list[str]
    missing_requirements: list[str]
    finding_ids: list[str]
    evidence_node_ids: list[str]
    evidence_link_ids: list[str]
    semantic_fact_ids: list[str]
    reason_codes: list[str]

    @model_validator(mode="after")
    def validate_assessment(self):
        for values in (
            self.satisfied_requirements, self.missing_requirements,
            self.finding_ids, self.evidence_node_ids, self.evidence_link_ids,
            self.semantic_fact_ids, self.reason_codes,
        ):
            if values != sorted(set(values)):
                raise ValueError("assessment references must be unique and canonical")
        missing_mandatory = any(not item.satisfied for item in self.mandatory_requirements)
        missing_supporting = any(not item.satisfied for item in self.supporting_requirements)
        if missing_mandatory and self.status is not TestabilityStatus.NOT_READY:
            raise ValueError("missing mandatory evidence must be not ready")
        if missing_supporting and self.status is TestabilityStatus.READY:
            raise ValueError("missing supporting evidence requires a warning")
        return self


class Agent4TestabilityResult(StrictTestabilityContract):
    schema_version: Literal[TESTABILITY_SCHEMA_VERSION]
    engine_version: Literal[TESTABILITY_ENGINE_VERSION]
    output_policy_version: Literal[OUTPUT_POLICY_VERSION]
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    confirmation_id: str = Field(pattern=r"^A4N1C-[0-9a-f]{32}$")
    selection_revision: int = Field(ge=1)
    selected_outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_selected_outputs: list[TestGenerationOutputCode] = Field(min_length=1)
    traceability_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    traceability_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    traceability_finding_ids: list[str]
    evidence_inventory: list[EvidenceInventoryItem]
    output_assessments: list[OutputTestabilityAssessment] = Field(min_length=1)
    overall_status: TestabilityStatus
    blocking_finding_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    findings: list[MissingContextFinding]
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: datetime

    @model_validator(mode="after")
    def validate_result(self):
        if [item.output_code for item in self.output_assessments] != self.confirmed_selected_outputs:
            raise ValueError("assessments must match confirmed selected outputs")
        finding_ids = [item.finding_id for item in self.findings]
        if finding_ids != sorted(finding_ids) or len(finding_ids) != len(set(finding_ids)):
            raise ValueError("findings must be unique and canonical")
        known_findings = set(finding_ids)
        if any(not set(item.finding_ids).issubset(known_findings) for item in self.output_assessments):
            raise ValueError("assessment finding references are invalid")
        if self.blocking_finding_count != sum(
            item.severity is TestabilityFindingSeverity.BLOCKING for item in self.findings
        ):
            raise ValueError("blocking finding count is inconsistent")
        if self.warning_count != sum(
            item.severity is TestabilityFindingSeverity.WARNING for item in self.findings
        ):
            raise ValueError("warning count is inconsistent")
        statuses = {item.status for item in self.output_assessments}
        expected = (
            TestabilityStatus.NOT_READY if TestabilityStatus.NOT_READY in statuses
            else TestabilityStatus.READY_WITH_WARNINGS
            if TestabilityStatus.READY_WITH_WARNINGS in statuses
            else TestabilityStatus.READY
        )
        if self.overall_status is not expected:
            raise ValueError("overall status does not match selected outputs")
        inventory_categories = [item.category for item in self.evidence_inventory]
        if inventory_categories != list(EvidenceCategory):
            raise ValueError("evidence inventory must use canonical complete category order")
        if self.traceability_finding_ids != sorted(set(self.traceability_finding_ids)):
            raise ValueError("traceability finding identities must be unique and canonical")
        known_nodes = {value for item in self.evidence_inventory for value in item.node_ids}
        known_links = {value for item in self.evidence_inventory for value in item.link_ids}
        known_facts = {value for item in self.evidence_inventory for value in item.semantic_fact_ids}
        known_graph_findings = set(self.traceability_finding_ids)
        for finding in self.findings:
            if (
                not set(finding.related_node_ids).issubset(known_nodes)
                or not set(finding.related_link_ids).issubset(known_links)
                or not set(finding.semantic_fact_ids).issubset(known_facts)
                or not set(finding.related_finding_ids).issubset(known_graph_findings)
            ):
                raise ValueError("finding evidence references are invalid")
        for assessment in self.output_assessments:
            if (
                not set(assessment.evidence_node_ids).issubset(known_nodes)
                or not set(assessment.evidence_link_ids).issubset(known_links)
                or not set(assessment.semantic_fact_ids).issubset(known_facts)
            ):
                raise ValueError("assessment evidence references are invalid")
        return self
