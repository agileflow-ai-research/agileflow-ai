from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.modules.agents.testing_validation.intelligence.schemas import (
    HybridEvidenceState,
    HybridLabelDecisionStatus,
    StrictIntelligenceContract,
    TestingHybridClassificationResult,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
)

from .policy import HYBRID_POLICY_VERSION, POLICY_SEMANTICS


class HybridPolicyMetadata(StrictIntelligenceContract):
    semantics: Literal[POLICY_SEMANTICS]
    rule_model_support_threshold: float = Field(ge=0, le=1)
    rule_model_conflict_threshold: float = Field(ge=0, le=1)
    model_only_review_threshold: float = Field(ge=0, le=1)
    decision_rules_version: str
    non_testable_policy: str

    @model_validator(mode="after")
    def validate_threshold_order(self):
        if not (
            self.rule_model_conflict_threshold
            <= self.rule_model_support_threshold
            <= self.model_only_review_threshold
        ):
            raise ValueError("hybrid thresholds must be ordered")
        return self


class HybridChunkReviewSummary(StrictIntelligenceContract):
    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    requires_human_review: bool
    review_label_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    model_only_count: int = Field(ge=0)


class HybridSourceReviewSummary(StrictIntelligenceContract):
    chunks_total: int = Field(ge=1)
    chunks_with_accepted_labels: int = Field(ge=0)
    chunks_requiring_review: int = Field(ge=0)
    accepted_label_count: int = Field(ge=0)
    review_label_count: int = Field(ge=0)
    rejected_label_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    model_only_count: int = Field(ge=0)


class TestingHybridManifest(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    hybrid_policy_version: Literal[HYBRID_POLICY_VERSION]
    hybrid_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy: HybridPolicyMetadata
    rules_version: Literal["R1"]
    rule_catalog_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    zero_shot_version: Literal["Z1"]
    zero_shot_config_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    zero_shot_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_id: str
    model_revision: str
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    chunk_set_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_ids: list[str] = Field(min_length=1)
    results: list[TestingHybridClassificationResult] = Field(min_length=1)
    chunk_summaries: list[HybridChunkReviewSummary] = Field(min_length=1)
    summary: HybridSourceReviewSummary
    processed_at: datetime

    @model_validator(mode="after")
    def validate_complete_manifest(self):
        if self.chunk_ids != [result.chunk.chunk_id for result in self.results]:
            raise ValueError("hybrid results must match ordered chunk IDs")
        if self.chunk_ids != [summary.chunk_id for summary in self.chunk_summaries]:
            raise ValueError("hybrid summaries must match ordered chunk IDs")
        expected = set(TESTING_INTELLIGENCE_LABEL_ORDER)
        for result in self.results:
            if result.chunk.agent_project_id != self.agent_project_id or result.chunk.source_id != self.source_id:
                raise ValueError("hybrid result provenance does not match manifest")
            if result.chunk.chunk_set_fingerprint != self.chunk_set_fingerprint:
                raise ValueError("hybrid result chunk set does not match manifest")
            if len(result.decisions) != len(expected) or {d.label for d in result.decisions} != expected:
                raise ValueError("hybrid result must decide every T1 label exactly once")
            if [decision.label for decision in result.decisions] != list(
                TESTING_INTELLIGENCE_LABEL_ORDER
            ):
                raise ValueError("hybrid decisions must use canonical T1 order")
        expected_chunks, expected_summary = build_review_summaries(self.results)
        if self.chunk_summaries != expected_chunks or self.summary != expected_summary:
            raise ValueError("hybrid review summaries do not match results")
        return self


def build_review_summaries(results):
    chunks = [
        HybridChunkReviewSummary(
            chunk_id=result.chunk.chunk_id,
            requires_human_review=bool(result.review_required_labels),
            review_label_count=len(result.review_required_labels),
            conflict_count=sum(d.evidence_state is HybridEvidenceState.CONFLICT for d in result.decisions),
            model_only_count=sum(d.evidence_state is HybridEvidenceState.MODEL_ONLY for d in result.decisions),
        )
        for result in results
    ]
    return chunks, HybridSourceReviewSummary(
        chunks_total=len(results),
        chunks_with_accepted_labels=sum(bool(r.accepted_labels) for r in results),
        chunks_requiring_review=sum(c.requires_human_review for c in chunks),
        accepted_label_count=sum(len(r.accepted_labels) for r in results),
        review_label_count=sum(len(r.review_required_labels) for r in results),
        rejected_label_count=sum(len(r.rejected_labels) for r in results),
        conflict_count=sum(c.conflict_count for c in chunks),
        model_only_count=sum(c.model_only_count for c in chunks),
    )
