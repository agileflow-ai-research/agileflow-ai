from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agents.implementation.inputs.extraction.schemas import DocumentType
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel, RuleEvidence, RuleStrength,
)
from app.modules.agents.implementation.preparation.classification.zero_shot.schemas import (
    ZeroShotScore,
)


class HybridEvidenceState(StrEnum):
    RULE_AND_MODEL = "RULE_AND_MODEL"
    RULE_ONLY = "RULE_ONLY"
    MODEL_ONLY = "MODEL_ONLY"
    RULE_MODEL_DISAGREEMENT = "RULE_MODEL_DISAGREEMENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class HybridDecisionState(StrEnum):
    AUTO_CANDIDATE = "AUTO_CANDIDATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class HybridReasonCode(StrEnum):
    RULE_MODEL_AGREEMENT = "RULE_MODEL_AGREEMENT"
    STRONG_RULE_SUPPORT = "STRONG_RULE_SUPPORT"
    MODERATE_RULE_SUPPORT = "MODERATE_RULE_SUPPORT"
    STRONG_MODEL_ONLY_SUPPORT = "STRONG_MODEL_ONLY_SUPPORT"
    MODEL_ONLY_REQUIRES_REVIEW = "MODEL_ONLY_REQUIRES_REVIEW"
    MODEL_LABEL_EXPLOSION = "MODEL_LABEL_EXPLOSION"
    MODEL_AMBIGUOUS = "MODEL_AMBIGUOUS"
    RULE_MODEL_DISAGREEMENT = "RULE_MODEL_DISAGREEMENT"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    NO_ARTIFACT_EVIDENCE = "NO_ARTIFACT_EVIDENCE"
    OTHER_CONTEXT_FALLBACK = "OTHER_CONTEXT_FALLBACK"


class HybridRuleEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matched: bool
    score: float | None = Field(default=None, ge=0, le=1)
    strength: RuleStrength | None = None
    evidence: list[RuleEvidence] = Field(default_factory=list)


class HybridModelEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float | None = Field(default=None, ge=0, le=1)


class HybridCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: ArtifactDetectionLabel
    evidence_state: HybridEvidenceState
    decision: HybridDecisionState
    rule: HybridRuleEvidence
    model: HybridModelEvidence
    reason_codes: list[HybridReasonCode]


class HybridChunkDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_label_explosion: bool
    model_ambiguous: bool
    top_model_margin: float | None = Field(default=None, ge=0, le=1)
    top_model_scores: list[ZeroShotScore]


class ChunkHybridDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnostics: HybridChunkDiagnostics
    candidates: list[HybridCandidate]


class BaselineReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    detector_version: str | None = Field(default=None, pattern=r"^\d+$")
    classifier_version: str | None = Field(default=None, pattern=r"^\d+$")
    model_id: str | None = None
    model_revision: str | None = None
    label_map_version: str | None = Field(default=None, pattern=r"^\d+$")


class HybridPolicyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_version: str = Field(pattern=r"^\d+$")
    policy_version: str = Field(pattern=r"^\d+$")
    threshold_semantics: Literal["EXPERIMENTAL_ENGINEERING_DEFAULTS_NOT_VALIDATED"]
    model_strong_support: float
    model_moderate_support: float
    model_weak_support: float
    label_explosion_count: int
    label_explosion_threshold: float
    top_score_margin_threshold: float


class HybridMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_count: int = Field(ge=0)
    auto_candidate_count: int = Field(ge=0)
    review_required_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    rule_and_model_count: int = Field(ge=0)
    rule_only_count: int = Field(ge=0)
    model_only_count: int = Field(ge=0)
    disagreement_count: int = Field(ge=0)
    insufficient_evidence_count: int = Field(ge=0)
    label_explosion_chunk_count: int = Field(ge=0)
    ambiguous_chunk_count: int = Field(ge=0)
    per_label_candidate_counts: dict[ArtifactDetectionLabel, int]


class DocumentHybridDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    original_filename: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: DocumentType
    extraction_version: str = Field(pattern=r"^\d+$")
    chunker_version: str = Field(pattern=r"^\d+$")
    rule_baseline: BaselineReference
    model_baseline: BaselineReference
    policy: HybridPolicyMetadata
    chunks: list[ChunkHybridDetection]
    metrics: HybridMetrics
    warnings: list[str]
    created_at: datetime
