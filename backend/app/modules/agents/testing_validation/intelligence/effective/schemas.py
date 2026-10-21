from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.modules.agents.testing_validation.intelligence.schemas import (
    HybridLabelDecisionStatus,
    StrictIntelligenceContract,
    TestingChunkReference,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TestingIntelligenceLabel,
)


EFFECTIVE_CLASSIFICATION_POLICY_VERSION = "E1"


class EffectiveDecisionStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class EffectiveDecisionOrigin(StrEnum):
    H1_AUTO_ACCEPTED = "H1_AUTO_ACCEPTED"
    H1_AUTO_REJECTED = "H1_AUTO_REJECTED"
    HUMAN_ACCEPTED = "HUMAN_ACCEPTED"
    HUMAN_REJECTED = "HUMAN_REJECTED"


class EffectiveLabelDecision(StrictIntelligenceContract):
    label: TestingIntelligenceLabel
    status: EffectiveDecisionStatus
    origin: EffectiveDecisionOrigin
    hybrid_status: HybridLabelDecisionStatus
    review_id: str | None = Field(default=None, pattern=r"^A4N3R-[0-9a-f]{32}$")

    @model_validator(mode="after")
    def validate_origin(self):
        human = self.origin in {
            EffectiveDecisionOrigin.HUMAN_ACCEPTED,
            EffectiveDecisionOrigin.HUMAN_REJECTED,
        }
        if human != (self.review_id is not None):
            raise ValueError("human effective decisions require a review reference")
        if human != (self.hybrid_status is HybridLabelDecisionStatus.REVIEW_REQUIRED):
            raise ValueError("only H1 review-required labels may be human-resolved")
        expected = {
            EffectiveDecisionOrigin.H1_AUTO_ACCEPTED: (
                EffectiveDecisionStatus.ACCEPTED,
                HybridLabelDecisionStatus.ACCEPTED,
            ),
            EffectiveDecisionOrigin.H1_AUTO_REJECTED: (
                EffectiveDecisionStatus.REJECTED,
                HybridLabelDecisionStatus.REJECTED,
            ),
            EffectiveDecisionOrigin.HUMAN_ACCEPTED: (
                EffectiveDecisionStatus.ACCEPTED,
                HybridLabelDecisionStatus.REVIEW_REQUIRED,
            ),
            EffectiveDecisionOrigin.HUMAN_REJECTED: (
                EffectiveDecisionStatus.REJECTED,
                HybridLabelDecisionStatus.REVIEW_REQUIRED,
            ),
        }[self.origin]
        if (self.status, self.hybrid_status) != expected:
            raise ValueError("effective decision status does not match its origin")
        return self


class TestingEffectiveClassificationResult(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    effective_result_id: str = Field(pattern=r"^A4EFF-[0-9a-f]{32}$")
    chunk: TestingChunkReference
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    hybrid_result_id: str = Field(pattern=r"^A4HYB-[0-9a-f]{32}$")
    hybrid_policy_version: str
    hybrid_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_labels: list[TestingIntelligenceLabel]
    rejected_labels: list[TestingIntelligenceLabel]
    decisions: list[EffectiveLabelDecision]
    review_id: str | None = Field(default=None, pattern=r"^A4N3R-[0-9a-f]{32}$")
    effective_policy_version: Literal[EFFECTIVE_CLASSIFICATION_POLICY_VERSION]
    created_at: datetime

    @field_validator("accepted_labels", "rejected_labels")
    @classmethod
    def canonical_labels(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("effective labels must be unique")
        selected = set(value)
        return [label for label in TESTING_INTELLIGENCE_LABEL_ORDER if label in selected]

    @model_validator(mode="after")
    def validate_complete(self):
        if [item.label for item in self.decisions] != list(TESTING_INTELLIGENCE_LABEL_ORDER):
            raise ValueError("effective decisions must use complete canonical T1 order")
        accepted = {item.label for item in self.decisions if item.status is EffectiveDecisionStatus.ACCEPTED}
        rejected = {item.label for item in self.decisions if item.status is EffectiveDecisionStatus.REJECTED}
        if accepted != set(self.accepted_labels) or rejected != set(self.rejected_labels):
            raise ValueError("effective label groups must match decisions")
        if accepted & rejected or accepted | rejected != set(TESTING_INTELLIGENCE_LABEL_ORDER):
            raise ValueError("effective decisions must resolve every T1 label")
        review_ids = {item.review_id for item in self.decisions if item.review_id}
        if review_ids and review_ids != {self.review_id}:
            raise ValueError("effective review references are inconsistent")
        return self


class EffectiveClassificationCounts(StrictIntelligenceContract):
    chunk_count: int = Field(ge=1)
    accepted_label_count: int = Field(ge=0)
    rejected_label_count: int = Field(ge=0)
    human_accepted_count: int = Field(ge=0)
    human_rejected_count: int = Field(ge=0)


class TestingEffectiveClassificationManifest(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    effective_policy_version: Literal[EFFECTIVE_CLASSIFICATION_POLICY_VERSION]
    hybrid_policy_version: str
    hybrid_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_ids: list[str]
    chunk_ids: list[str] = Field(min_length=1)
    results: list[TestingEffectiveClassificationResult] = Field(min_length=1)
    counts: EffectiveClassificationCounts
    created_at: datetime

    @model_validator(mode="after")
    def validate_manifest(self):
        if self.chunk_ids != [item.chunk.chunk_id for item in self.results]:
            raise ValueError("effective results must match ordered chunk IDs")
        if any(item.source_id != self.source_id or item.agent_project_id != self.agent_project_id for item in (r.chunk for r in self.results)):
            raise ValueError("effective result provenance does not match manifest")
        expected_reviews = sorted({r.review_id for r in self.results if r.review_id})
        if self.review_ids != expected_reviews:
            raise ValueError("effective review references must be canonical")
        expected_counts = EffectiveClassificationCounts(
            chunk_count=len(self.results),
            accepted_label_count=sum(len(item.accepted_labels) for item in self.results),
            rejected_label_count=sum(len(item.rejected_labels) for item in self.results),
            human_accepted_count=sum(
                decision.origin is EffectiveDecisionOrigin.HUMAN_ACCEPTED
                for item in self.results for decision in item.decisions
            ),
            human_rejected_count=sum(
                decision.origin is EffectiveDecisionOrigin.HUMAN_REJECTED
                for item in self.results for decision in item.decisions
            ),
        )
        if self.counts != expected_counts:
            raise ValueError("effective classification counts do not match results")
        return self
