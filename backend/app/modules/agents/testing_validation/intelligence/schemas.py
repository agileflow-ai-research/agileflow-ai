"""Strict contracts for later Agent 4 testing-intelligence stages."""

from collections.abc import Collection
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.preparation.chunking.constants import (
    CHUNKER_VERSION,
    CHUNK_POLICY_VERSION,
    CHUNK_SCHEMA_VERSION,
)
from app.modules.agents.testing_validation.preparation.chunking.schemas import (
    TestingChunk,
    TestingChunkSet,
)

from .taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TestingIntelligenceLabel,
)


class StrictIntelligenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


BoundedScore = Annotated[float, Field(ge=0, le=1)]
ReasonCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_-]{1,79}$")]
EvidenceId = Annotated[str, Field(pattern=r"^A4EVD-[0-9a-f]{32}$")]
SegmentId = Annotated[str, Field(pattern=r"^A4SEG-[0-9a-f]{32}$")]


def _canonical_labels(
    labels: list[TestingIntelligenceLabel],
) -> list[TestingIntelligenceLabel]:
    if len(labels) != len(set(labels)):
        raise ValueError("classification labels must not contain duplicates")
    selected = set(labels)
    return [label for label in TESTING_INTELLIGENCE_LABEL_ORDER if label in selected]


class ClassificationEvidenceType(StrEnum):
    RULE = "RULE"
    ZERO_SHOT = "ZERO_SHOT"
    HYBRID = "HYBRID"


class HybridEvidenceState(StrEnum):
    AGREEMENT = "AGREEMENT"
    RULE_ONLY = "RULE_ONLY"
    MODEL_ONLY = "MODEL_ONLY"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"


class HybridLabelDecisionStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class TestingChunkReference(StrictIntelligenceContract):
    """Evidence identity without duplicating trusted chunk text."""

    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    chunk_set_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    normalized_artifact_id: str = Field(pattern=r"^A4ART-[0-9a-f]{32}$")
    artifact_type: TestGenerationInputArtifactType
    source_type: TestGenerationInputSourceType
    sequence: int = Field(ge=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalization_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunker_version: str = Field(min_length=1, max_length=40)
    chunk_policy_version: str = Field(min_length=1, max_length=40)


class ClassificationEvidence(StrictIntelligenceContract):
    evidence_id: str = Field(pattern=r"^A4EVD-[0-9a-f]{32}$")
    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    label: TestingIntelligenceLabel
    evidence_type: ClassificationEvidenceType
    quote: str | None = Field(default=None, min_length=1, max_length=2_000)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=1)
    source_segment_ids: list[SegmentId] = Field(default_factory=list)
    confidence: BoundedScore | None = None
    reason_code: ReasonCode | None = None
    explanation: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_offsets(self) -> "ClassificationEvidence":
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("evidence offsets must be supplied together")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset <= self.start_offset
        ):
            raise ValueError("evidence end offset must follow its start offset")
        if self.start_offset is not None and self.quote is None:
            raise ValueError("offset evidence must include its grounded quote")
        return self


class TestingRuleClassificationResult(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    result_id: str = Field(pattern=r"^A4RUL-[0-9a-f]{32}$")
    chunk: TestingChunkReference
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    rules_version: str = Field(min_length=1, max_length=40)
    detected_labels: list[TestingIntelligenceLabel]
    rule_evidence: list[ClassificationEvidence]
    processed_at: datetime

    _order_labels = field_validator("detected_labels")(_canonical_labels)

    @model_validator(mode="after")
    def validate_evidence(self) -> "TestingRuleClassificationResult":
        detected = set(self.detected_labels)
        evidenced: set[TestingIntelligenceLabel] = set()
        for evidence in self.rule_evidence:
            if evidence.evidence_type is not ClassificationEvidenceType.RULE:
                raise ValueError("rule result accepts RULE evidence only")
            if evidence.chunk_id != self.chunk.chunk_id:
                raise ValueError("rule evidence must reference the result chunk")
            if evidence.label not in detected:
                raise ValueError("rule evidence label must be detected")
            evidenced.add(evidence.label)
        if evidenced != detected:
            raise ValueError("every detected rule label must have grounded evidence")
        return self


class ZeroShotInputMetadata(StrictIntelligenceContract):
    input_token_count: int = Field(ge=1)
    model_max_tokens: int = Field(ge=1)
    truncated: bool
    tokens_discarded: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_truncation(self) -> "ZeroShotInputMetadata":
        if self.truncated != (self.tokens_discarded > 0):
            raise ValueError("truncation flag and discarded-token count disagree")
        return self


class ClassificationWarning(StrictIntelligenceContract):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,79}$")
    message: str = Field(min_length=1, max_length=500)


class TestingZeroShotClassificationResult(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    result_id: str = Field(pattern=r"^A4ZSC-[0-9a-f]{32}$")
    chunk: TestingChunkReference
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    model_id: str = Field(min_length=1, max_length=300)
    model_revision: str = Field(min_length=1, max_length=200)
    task: Literal["zero-shot-classification"] = "zero-shot-classification"
    multi_label: Literal[True] = True
    label_scores: dict[TestingIntelligenceLabel, BoundedScore]
    label_description_version: Literal[
        AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION
    ]
    hypothesis_template_version: str = Field(min_length=1, max_length=40)
    input_metadata: ZeroShotInputMetadata
    inference_duration_ms: float = Field(ge=0)
    warnings: list[ClassificationWarning] = Field(default_factory=list)
    processed_at: datetime

    @field_validator("label_scores")
    @classmethod
    def validate_score_vector(
        cls, value: dict[TestingIntelligenceLabel, float]
    ) -> dict[TestingIntelligenceLabel, float]:
        if set(value) != set(TESTING_INTELLIGENCE_LABEL_ORDER):
            raise ValueError("zero-shot scores must contain the complete taxonomy")
        return {label: value[label] for label in TESTING_INTELLIGENCE_LABEL_ORDER}


class HybridLabelDecision(StrictIntelligenceContract):
    label: TestingIntelligenceLabel
    status: HybridLabelDecisionStatus
    evidence_state: HybridEvidenceState
    reason_codes: list[ReasonCode] = Field(min_length=1)
    explanation: str | None = Field(default=None, min_length=1, max_length=500)
    rule_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    model_score: BoundedScore | None = None


class TestingHybridClassificationResult(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    result_id: str = Field(pattern=r"^A4HYB-[0-9a-f]{32}$")
    chunk: TestingChunkReference
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    rule_result_id: str = Field(pattern=r"^A4RUL-[0-9a-f]{32}$")
    zero_shot_result_id: str = Field(pattern=r"^A4ZSC-[0-9a-f]{32}$")
    hybrid_policy_version: str = Field(min_length=1, max_length=40)
    accepted_labels: list[TestingIntelligenceLabel]
    review_required_labels: list[TestingIntelligenceLabel]
    rejected_labels: list[TestingIntelligenceLabel]
    decisions: list[HybridLabelDecision]
    processed_at: datetime

    _order_accepted = field_validator("accepted_labels")(_canonical_labels)
    _order_review = field_validator("review_required_labels")(_canonical_labels)
    _order_rejected = field_validator("rejected_labels")(_canonical_labels)

    @model_validator(mode="after")
    def validate_decisions(self) -> "TestingHybridClassificationResult":
        groups = (
            (HybridLabelDecisionStatus.ACCEPTED, self.accepted_labels),
            (HybridLabelDecisionStatus.REVIEW_REQUIRED, self.review_required_labels),
            (HybridLabelDecisionStatus.REJECTED, self.rejected_labels),
        )
        all_grouped = [label for _, labels in groups for label in labels]
        if len(all_grouped) != len(set(all_grouped)):
            raise ValueError("hybrid label groups must be disjoint")
        if len(self.decisions) != len({decision.label for decision in self.decisions}):
            raise ValueError("hybrid decisions must have unique labels")
        decision_by_label = {decision.label: decision for decision in self.decisions}
        if set(decision_by_label) != set(all_grouped):
            raise ValueError("hybrid decisions must cover every grouped label exactly once")
        for expected_status, labels in groups:
            if any(decision_by_label[label].status is not expected_status for label in labels):
                raise ValueError("hybrid decision status does not match its label group")
        return self


class TestingIntelligenceGroundTruth(StrictIntelligenceContract):
    """Minimal future expert-evaluation sample; no annotation workflow state."""

    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    expected_labels: list[TestingIntelligenceLabel]

    _order_expected = field_validator("expected_labels")(_canonical_labels)


def current_chunk_reference(
    chunk: TestingChunk,
    chunk_set: TestingChunkSet,
    *,
    confirmed_source_ids: Collection[str],
) -> TestingChunkReference:
    """Validate a current N2.3 manifest member and return its evidence reference.

    N3 callers must load the current manifest and the authoritative N1
    confirmation rather than accepting an arbitrary chunk, source ID, or path.
    """

    if (
        chunk_set.schema_version != CHUNK_SCHEMA_VERSION
        or chunk_set.chunker_version != CHUNKER_VERSION
        or chunk_set.policy_version != CHUNK_POLICY_VERSION
    ):
        raise ValueError("chunk set does not use the current chunking policy")
    if chunk.source_id not in confirmed_source_ids:
        raise ValueError("chunk source is not present in the N1 confirmation snapshot")
    if chunk.chunk_id not in chunk_set.chunk_ids:
        raise ValueError("chunk is not present in the current chunk manifest")
    stored = next(
        (candidate for candidate in chunk_set.chunks if candidate.chunk_id == chunk.chunk_id),
        None,
    )
    if stored is None or stored != chunk:
        raise ValueError("chunk does not match the current chunk manifest")
    if (
        chunk.agent_project_id != chunk_set.agent_project_id
        or chunk.source_id != chunk_set.source_id
        or chunk.normalized_artifact_id != chunk_set.normalized_artifact_id
        or chunk.normalization_fingerprint != chunk_set.normalization_fingerprint
        or chunk.source_evidence_sha256 != chunk_set.source_evidence_sha256
    ):
        raise ValueError("chunk provenance does not match its manifest")
    if chunk.source_type is TestGenerationInputSourceType.IMAGE:
        raise ValueError("image sources do not produce classifiable text chunks")
    if not chunk.text.strip():
        raise ValueError("chunk must contain textual evidence")
    if sha256(chunk.text.encode("utf-8")).hexdigest() != chunk.text_sha256:
        raise ValueError("chunk text does not match its evidence hash")
    return TestingChunkReference(
        chunk_id=chunk.chunk_id,
        chunk_set_fingerprint=chunk_set.chunk_set_fingerprint,
        agent_project_id=chunk.agent_project_id,
        source_id=chunk.source_id,
        normalized_artifact_id=chunk.normalized_artifact_id,
        artifact_type=chunk.artifact_type,
        source_type=chunk.source_type,
        sequence=chunk.sequence,
        text_sha256=chunk.text_sha256,
        source_evidence_sha256=chunk.source_evidence_sha256,
        normalization_fingerprint=chunk.normalization_fingerprint,
        chunker_version=chunk_set.chunker_version,
        chunk_policy_version=chunk_set.policy_version,
    )
