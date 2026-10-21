"""Strict immutable contracts for S6 deterministic consolidation."""

from enum import StrEnum

from pydantic import Field, model_validator

from app.modules.agents.requirements.quality.contracts import (
    ExactDuplicateGroup, QualityRequirement, RequirementClarityIssue,
    RequirementConflictPair, SemanticDuplicatePair, StrictQualityContract,
)


class QualityFindingType(StrEnum):
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    SEMANTIC_DUPLICATE = "SEMANTIC_DUPLICATE"
    CONFLICT = "CONFLICT"
    AMBIGUITY = "AMBIGUITY"
    MISSING_INFORMATION = "MISSING_INFORMATION"


class QualityFindingEvidenceKind(StrEnum):
    EXACT_DUPLICATE_GROUP = "EXACT_DUPLICATE_GROUP"
    SEMANTIC_DUPLICATE_PAIR = "SEMANTIC_DUPLICATE_PAIR"
    REQUIREMENT_CONFLICT_PAIR = "REQUIREMENT_CONFLICT_PAIR"
    REQUIREMENT_CLARITY_ISSUE = "REQUIREMENT_CLARITY_ISSUE"


class ClarificationIntent(StrEnum):
    DUPLICATE_REVIEW = "DUPLICATE_REVIEW"
    SEMANTIC_DUPLICATE_REVIEW = "SEMANTIC_DUPLICATE_REVIEW"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    AMBIGUITY_CLARIFICATION = "AMBIGUITY_CLARIFICATION"
    MISSING_INFORMATION_REQUEST = "MISSING_INFORMATION_REQUEST"


class QualityFindingEvidence(StrictQualityContract):
    kind: QualityFindingEvidenceKind
    upstream_evidence_id: str = Field(min_length=1)
    exact_duplicate_group: ExactDuplicateGroup | None = None
    semantic_duplicate_pair: SemanticDuplicatePair | None = None
    conflict_pair: RequirementConflictPair | None = None
    clarity_issue: RequirementClarityIssue | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "QualityFindingEvidence":
        payloads = {
            QualityFindingEvidenceKind.EXACT_DUPLICATE_GROUP: self.exact_duplicate_group,
            QualityFindingEvidenceKind.SEMANTIC_DUPLICATE_PAIR: self.semantic_duplicate_pair,
            QualityFindingEvidenceKind.REQUIREMENT_CONFLICT_PAIR: self.conflict_pair,
            QualityFindingEvidenceKind.REQUIREMENT_CLARITY_ISSUE: self.clarity_issue,
        }
        if payloads[self.kind] is None or sum(value is not None for value in payloads.values()) != 1:
            raise ValueError("Finding evidence requires exactly one matching payload")
        return self


class UnifiedQualityFinding(StrictQualityContract):
    finding_id: str = Field(pattern=r"^QF-[0-9A-F]{16}$")
    contract_version: str
    finding_type: QualityFindingType
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    affected_requirements: tuple[QualityRequirement, ...] = Field(min_length=1)
    evidence: QualityFindingEvidence
    detector_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=500)
    requires_human_review: bool = True


class ClarificationCandidate(StrictQualityContract):
    clarification_candidate_id: str = Field(pattern=r"^QCL-[0-9A-F]{16}$")
    contract_version: str
    finding_id: str = Field(pattern=r"^QF-[0-9A-F]{16}$")
    finding_type: QualityFindingType
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    affected_requirements: tuple[QualityRequirement, ...] = Field(min_length=1)
    intent: ClarificationIntent
    reason: str = Field(min_length=1, max_length=500)
    upstream_evidence_kind: QualityFindingEvidenceKind
    upstream_evidence_id: str = Field(min_length=1)
    requires_human_input: bool = True


class QualityConsolidationResult(StrictQualityContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_duplicate_result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_duplicate_result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    conflict_result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    clarity_result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    consolidation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: tuple[UnifiedQualityFinding, ...] = ()
    clarification_candidates: tuple[ClarificationCandidate, ...] = ()
    exact_duplicate_findings: int = Field(ge=0)
    semantic_duplicate_findings: int = Field(ge=0)
    conflict_findings: int = Field(ge=0)
    ambiguity_findings: int = Field(ge=0)
    missing_information_findings: int = Field(ge=0)
    total_findings: int = Field(ge=0)
    clarification_candidate_count: int = Field(ge=0)
    affected_requirement_count: int = Field(ge=0)
    result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_counts(self) -> "QualityConsolidationResult":
        counts = {kind: sum(item.finding_type is kind for item in self.findings)
                  for kind in QualityFindingType}
        expected = (
            self.exact_duplicate_findings, self.semantic_duplicate_findings,
            self.conflict_findings, self.ambiguity_findings,
            self.missing_information_findings,
        )
        actual = tuple(counts[kind] for kind in QualityFindingType)
        affected = {requirement.requirement_id for finding in self.findings
                    for requirement in finding.affected_requirements}
        if (expected != actual or self.total_findings != len(self.findings)
                or self.clarification_candidate_count != len(self.clarification_candidates)
                or len(self.findings) != len(self.clarification_candidates)
                or self.affected_requirement_count != len(affected)):
            raise ValueError("Quality consolidation counts are inconsistent")
        return self
