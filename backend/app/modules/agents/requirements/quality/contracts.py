"""Immutable contracts at the validated N3-to-N4 boundary."""

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.contracts import StructuredRequirementType
from app.modules.agents.requirements.processing.preparation.schemas import (
    NormalizedProvenanceSpan,
)


class StrictQualityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QualityRequirement(StrictQualityContract):
    requirement_id: str = Field(pattern=r"^(?:FR|NFR)-[0-9A-F]{16}$")
    requirement_type: StructuredRequirementType
    statement: str = Field(min_length=1)
    candidate_id: str = Field(pattern=r"^RC-[0-9A-F]{16}$")
    candidate_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{16}$")
    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    provenance: tuple[NormalizedProvenanceSpan, ...] = Field(min_length=1)
    classification_confidence: float = Field(ge=0.0, le=1.0)
    classifier_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidatedQualityInput(StrictQualityContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    n3_execution_id: str = Field(pattern=r"^N3-[0-9A-F]{16}-\d{3}$")
    n3_attempt: int = Field(ge=1)
    n2_execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    discovery_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_set_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    classifier_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    requirements: tuple[QualityRequirement, ...] = ()
    input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExactDuplicateMember(StrictQualityContract):
    """A complete reference to one unchanged requirement in a duplicate group."""

    requirement: QualityRequirement


class ExactDuplicateGroup(StrictQualityContract):
    duplicate_group_id: str = Field(pattern=r"^QDUP-[0-9A-F]{16}$")
    comparison_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[ExactDuplicateMember, ...] = Field(min_length=2)
    count: int = Field(ge=2)

    @model_validator(mode="after")
    def validate_count(self) -> "ExactDuplicateGroup":
        if self.count != len(self.members):
            raise ValueError("Duplicate group count must match its members")
        ids = [item.requirement.requirement_id for item in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("A requirement cannot occur twice in one duplicate group")
        return self


class ExactDuplicateResult(StrictQualityContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    detector_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate_groups: tuple[ExactDuplicateGroup, ...] = ()
    duplicate_group_count: int = Field(ge=0)
    affected_requirement_count: int = Field(ge=0)
    result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_counts(self) -> "ExactDuplicateResult":
        if self.duplicate_group_count != len(self.duplicate_groups):
            raise ValueError("Duplicate group count is inconsistent")
        affected = sum(group.count for group in self.duplicate_groups)
        if self.affected_requirement_count != affected:
            raise ValueError("Affected requirement count is inconsistent")
        return self


class EmbeddingModelIdentity(StrictQualityContract):
    provider_type: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    requested_revision: str | None = None
    resolved_revision: str | None = None
    device: str = Field(min_length=1)
    normalize_embeddings: bool
    embedding_dimension: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    preprocessing_policy: str = Field(min_length=1)
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class SemanticSimilarityEvidence(StrictQualityContract):
    cosine_similarity: float = Field(ge=-1.0, le=1.0)
    threshold: float = Field(ge=-1.0, le=1.0)
    model_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class SemanticDuplicatePair(StrictQualityContract):
    semantic_duplicate_id: str = Field(pattern=r"^QSEM-[0-9A-F]{16}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    left: QualityRequirement
    right: QualityRequirement
    evidence: SemanticSimilarityEvidence

    @model_validator(mode="after")
    def validate_distinct_pair(self) -> "SemanticDuplicatePair":
        if self.left.requirement_id == self.right.requirement_id:
            raise ValueError("Semantic duplicate pair members must be distinct")
        return self


class SemanticDuplicateResult(StrictQualityContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_duplicate_result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: EmbeddingModelIdentity
    detector_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    threshold: float = Field(ge=-1.0, le=1.0)
    pairs: tuple[SemanticDuplicatePair, ...] = ()
    pair_count: int = Field(ge=0)
    result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_pair_count(self) -> "SemanticDuplicateResult":
        if self.pair_count != len(self.pairs):
            raise ValueError("Semantic duplicate pair count is inconsistent")
        return self


class NliRelation(StrEnum):
    ENTAILMENT = "ENTAILMENT"
    NEUTRAL = "NEUTRAL"
    CONTRADICTION = "CONTRADICTION"


class NliRelationScore(StrictQualityContract):
    relation: NliRelation
    score: float = Field(ge=0.0, le=1.0)


class NliScoreVector(StrictQualityContract):
    scores: tuple[NliRelationScore, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "NliScoreVector":
        relations = [item.relation for item in self.scores]
        if len(set(relations)) != 3 or set(relations) != set(NliRelation):
            raise ValueError("NLI scores require the complete relation taxonomy")
        # Real transformer inference may preserve a model's half-precision
        # dtype through softmax. IEEE-754 binary16 unit roundoff is about
        # 4.88e-4, so accept only that narrow representation drift.
        total = math.fsum(item.score for item in self.scores)
        if not math.isclose(total, 1.0, rel_tol=5e-4, abs_tol=5e-4):
            raise ValueError("NLI scores must form a normalized probability distribution")
        return self

    def score_for(self, relation: NliRelation) -> float:
        return next(item.score for item in self.scores if item.relation is relation)


class ConflictModelIdentity(StrictQualityContract):
    provider_type: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    requested_revision: str | None = None
    resolved_revision: str | None = None
    device: str = Field(min_length=1)
    task: str = Field(min_length=1)
    label_mapping_policy: dict[NliRelation, str]
    directional_policy: str = Field(min_length=1)
    aggregation_policy: str = Field(min_length=1)
    contradiction_threshold: float = Field(ge=0.0, le=1.0)
    batch_size: int = Field(gt=0)
    preprocessing_policy: str = Field(min_length=1)
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class DirectionalConflictEvidence(StrictQualityContract):
    premise_requirement_id: str = Field(pattern=r"^(?:FR|NFR)-[0-9A-F]{16}$")
    hypothesis_requirement_id: str = Field(pattern=r"^(?:FR|NFR)-[0-9A-F]{16}$")
    relation_scores: NliScoreVector


class RequirementConflictPair(StrictQualityContract):
    conflict_id: str = Field(pattern=r"^QCON-[0-9A-F]{16}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    left: QualityRequirement
    right: QualityRequirement
    relatedness_score: float = Field(ge=-1.0, le=1.0)
    relatedness_threshold: float = Field(ge=-1.0, le=1.0)
    left_to_right: DirectionalConflictEvidence
    right_to_left: DirectionalConflictEvidence
    final_contradiction_score: float = Field(ge=0.0, le=1.0)
    contradiction_threshold: float = Field(ge=0.0, le=1.0)
    final_relation: NliRelation
    embedding_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    nli_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class RequirementConflictResult(StrictQualityContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_duplicate_result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_duplicate_result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    nli_model: ConflictModelIdentity
    detector_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    relatedness_threshold: float = Field(ge=-1.0, le=1.0)
    contradiction_threshold: float = Field(ge=0.0, le=1.0)
    total_potential_pair_count: int = Field(ge=0)
    relatedness_candidate_pair_count: int = Field(ge=0)
    nli_evaluated_pair_count: int = Field(ge=0)
    conflicts: tuple[RequirementConflictPair, ...] = ()
    conflict_count: int = Field(ge=0)
    result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_counts(self) -> "RequirementConflictResult":
        if self.conflict_count != len(self.conflicts):
            raise ValueError("Conflict count is inconsistent")
        if self.nli_evaluated_pair_count != self.relatedness_candidate_pair_count:
            raise ValueError("Every relatedness candidate must have NLI evidence")
        if self.conflict_count > self.nli_evaluated_pair_count:
            raise ValueError("Conflict count exceeds evaluated pair count")
        return self


class RequirementClarityIssueType(StrEnum):
    AMBIGUITY = "AMBIGUITY"
    MISSING_INFORMATION = "MISSING_INFORMATION"


class RequirementClaritySignal(StrEnum):
    VAGUE_QUALIFIER = "VAGUE_QUALIFIER"
    VAGUE_QUANTIFIER = "VAGUE_QUANTIFIER"
    VAGUE_FREQUENCY = "VAGUE_FREQUENCY"
    SUBJECTIVE_TERM = "SUBJECTIVE_TERM"
    OPEN_ENDED_PHRASE = "OPEN_ENDED_PHRASE"
    UNCLEAR_CONDITION = "UNCLEAR_CONDITION"
    PERFORMANCE_TARGET_MISSING = "PERFORMANCE_TARGET_MISSING"
    CAPACITY_TARGET_MISSING = "CAPACITY_TARGET_MISSING"
    AVAILABILITY_TARGET_MISSING = "AVAILABILITY_TARGET_MISSING"
    FREQUENCY_VALUE_MISSING = "FREQUENCY_VALUE_MISSING"
    CONDITION_DETAIL_MISSING = "CONDITION_DETAIL_MISSING"


class RequirementClarityIssue(StrictQualityContract):
    issue_id: str = Field(pattern=r"^Q(?:AMB|MISS)-[0-9A-F]{16}$")
    issue_type: RequirementClarityIssueType
    signal_code: RequirementClaritySignal
    requirement: QualityRequirement
    evidence_text: str = Field(min_length=1)
    evidence_start: int = Field(ge=0)
    evidence_end: int = Field(gt=0)
    detector_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_version: str = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_evidence_span(self) -> "RequirementClarityIssue":
        if self.evidence_end <= self.evidence_start:
            raise ValueError("Clarity evidence span is invalid")
        if self.requirement.statement[self.evidence_start:self.evidence_end] != self.evidence_text:
            raise ValueError("Clarity evidence must exactly match the requirement statement")
        prefix = "QAMB-" if self.issue_type is RequirementClarityIssueType.AMBIGUITY else "QMISS-"
        if not self.issue_id.startswith(prefix):
            raise ValueError("Clarity issue prefix does not match its issue type")
        return self


class RequirementClarityResult(StrictQualityContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    quality_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    detector_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    issues: tuple[RequirementClarityIssue, ...] = ()
    ambiguity_count: int = Field(ge=0)
    missing_information_count: int = Field(ge=0)
    affected_requirement_count: int = Field(ge=0)
    result_identity: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_counts(self) -> "RequirementClarityResult":
        ambiguity = sum(item.issue_type is RequirementClarityIssueType.AMBIGUITY for item in self.issues)
        missing = len(self.issues) - ambiguity
        affected = len({item.requirement.requirement_id for item in self.issues})
        if (self.ambiguity_count != ambiguity
                or self.missing_information_count != missing
                or self.affected_requirement_count != affected):
            raise ValueError("Clarity result counts are inconsistent")
        return self
