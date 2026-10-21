"""Strict contracts exposed by the validated N3 discovery boundary."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.processing.preparation.schemas import (
    EvidenceChunk,
    NormalizedProvenanceSpan,
)


class StrictDiscoveryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DiscoveryInputReference(StrictDiscoveryContract):
    n2_execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    n2_attempt: int = Field(ge=1)
    chunk_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidatedDiscoveryChunk(StrictDiscoveryContract):
    """An existing N2 chunk plus its validated parent/source identity."""

    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalizer_version: str = Field(pattern=r"^\d+$")
    chunker_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk: EvidenceChunk


class ValidatedDiscoveryInput(StrictDiscoveryContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    reference: DiscoveryInputReference
    chunks: tuple[ValidatedDiscoveryChunk, ...] = Field(min_length=1)
    input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")


class CandidateDiscoverySignal(StrEnum):
    MODAL_SHALL = "MODAL_SHALL"
    MODAL_MUST = "MODAL_MUST"
    MODAL_SHOULD = "MODAL_SHOULD"
    MODAL_MAY = "MODAL_MAY"
    MODAL_CAN = "MODAL_CAN"
    NEED_OBLIGATION = "NEED_OBLIGATION"
    REQUIRED_OBLIGATION = "REQUIRED_OBLIGATION"
    CAPABILITY_PATTERN = "CAPABILITY_PATTERN"
    SYSTEM_BEHAVIOR_PATTERN = "SYSTEM_BEHAVIOR_PATTERN"
    PERFORMANCE_CONSTRAINT = "PERFORMANCE_CONSTRAINT"
    SECURITY_CONSTRAINT = "SECURITY_CONSTRAINT"
    CAPACITY_CONSTRAINT = "CAPACITY_CONSTRAINT"
    COMPATIBILITY_CONSTRAINT = "COMPATIBILITY_CONSTRAINT"
    EXPLICIT_REQUIREMENT = "EXPLICIT_REQUIREMENT"


class RequirementCandidate(StrictDiscoveryContract):
    candidate_id: str = Field(pattern=r"^RC-[0-9A-F]{16}$")
    candidate_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    n2_execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    chunk_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{16}$")
    source_id: str = Field(pattern=r"^(?:DOC|AUD|VID)-\d{3,}$")
    source_type: RequirementSourceType
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    discovery_signals: tuple[CandidateDiscoverySignal, ...] = Field(min_length=1)
    provenance: tuple[NormalizedProvenanceSpan, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_span(self) -> "RequirementCandidate":
        if self.end_offset <= self.start_offset:
            raise ValueError("Candidate end must follow its start")
        if self.end_offset - self.start_offset != len(self.text):
            raise ValueError("Candidate span length must match its evidence text")
        return self


class RequirementCandidateSet(StrictDiscoveryContract):
    contract_version: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    n2_execution_id: str = Field(pattern=r"^N2-[0-9A-F]{16}-\d{3}$")
    chunk_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    discovery_input_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidates: tuple[RequirementCandidate, ...] = ()


class RequirementClassificationLabel(StrEnum):
    FUNCTIONAL = "FUNCTIONAL"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"
    OTHER = "OTHER"


class ClassificationPolicyReason(StrEnum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"


class ClassificationScore(StrictDiscoveryContract):
    label: RequirementClassificationLabel
    score: float = Field(ge=0.0, le=1.0)


class ClassifierModelIdentity(StrictDiscoveryContract):
    provider_type: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    requested_revision: str | None = None
    resolved_revision: str | None = None
    task: str = Field(min_length=1)
    label_descriptions: dict[RequirementClassificationLabel, str]
    hypothesis_template: str = Field(min_length=1)
    minimum_confidence: float = Field(ge=0.0, le=1.0)
    minimum_margin: float | None = Field(default=None, ge=0.0, le=1.0)
    device: str = Field(min_length=1)
    batch_size: int = Field(ge=1)
    local_files_only: bool
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class RequirementClassification(StrictDiscoveryContract):
    candidate_id: str = Field(pattern=r"^RC-[0-9A-F]{16}$")
    candidate_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    label: RequirementClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    scores: tuple[ClassificationScore, ...] = Field(min_length=3, max_length=3)
    raw_winner: RequirementClassificationLabel
    policy_reason: ClassificationPolicyReason | None = None

    @model_validator(mode="after")
    def validate_scores(self) -> "RequirementClassification":
        labels = [item.label for item in self.scores]
        if len(set(labels)) != 3 or set(labels) != set(RequirementClassificationLabel):
            raise ValueError("Classification requires exactly one score per label")
        score_by_label = {item.label: item.score for item in self.scores}
        if self.confidence != score_by_label[self.raw_winner]:
            raise ValueError("Confidence must equal the raw winner score")
        if self.policy_reason is not None and self.label is not RequirementClassificationLabel.OTHER:
            raise ValueError("Policy demotion must classify the candidate as OTHER")
        return self


class RequirementClassificationSet(StrictDiscoveryContract):
    candidate_set: RequirementCandidateSet
    model: ClassifierModelIdentity
    classifications: tuple[RequirementClassification, ...] = ()
