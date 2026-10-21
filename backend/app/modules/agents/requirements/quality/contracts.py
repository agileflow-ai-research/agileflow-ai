"""Immutable contracts at the validated N3-to-N4 boundary."""

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
