from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Page(StrictDetail):
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=50)
    total: int = Field(ge=0)
    has_more: bool


class PreparedSection(StrictDetail):
    chunk_id: str
    source_id: str
    source_label: str
    artifact_type: str
    sequence: int
    section_count: int
    text: str
    heading_path: list[str]
    structure_type: str
    token_count: int


class PreparedSectionsPage(Page):
    items: list[PreparedSection]


class ClassificationDetail(StrictDetail):
    source_id: str
    source_label: str
    chunk_id: str
    sequence: int
    label: str
    evidence_quote: str
    rule_detected: bool
    model_score: float | None
    hybrid_relationship: str
    hybrid_decision: str
    effective_decision: str | None
    effective_origin: str | None
    review_id: str | None
    reason_codes: list[str]
    explanation: str | None


class ClassificationDetailsPage(Page):
    items: list[ClassificationDetail]


class ReviewDecisionDetail(StrictDetail):
    review_id: str
    source_id: str
    source_label: str
    chunk_id: str
    evidence_quote: str | None
    label: str
    human_decision: str
    note: str | None
    effective_decision: str | None
    reviewed_at: datetime


class ReviewDecisionsPage(Page):
    items: list[ReviewDecisionDetail]


class TestingFactDetail(StrictDetail):
    fact_id: str
    source_id: str
    source_label: str
    chunk_id: str
    sequence: int
    fact_type: str
    related_labels: list[str]
    evidence_quote: str
    structured_values: dict[str, Any]


class TestingFactsPage(Page):
    items: list[TestingFactDetail]


class TraceabilityConnection(StrictDetail):
    link_id: str
    source_value: str
    source_kind: str
    relation: str
    target_value: str
    target_kind: str
    explanation: str
    strength: str


class EvidenceRequirement(StrictDetail):
    requirement_id: str
    description: str
    satisfied: bool
    observed_count: int


class OutputAnalysisDetail(StrictDetail):
    output_code: str
    testability_status: str
    mandatory_requirements: list[EvidenceRequirement]
    supporting_requirements: list[EvidenceRequirement]
    feasibility_status: str
    recommended_representation: str | None
    generation_profile: dict[str, Any] | None
    decision: str
    planning_allowed: bool
    blockers: list[str]
    warnings: list[str]
    evidence_node_count: int
    evidence_link_count: int
    semantic_fact_count: int


class ContextDetailProjection(StrictDetail):
    overall_testability: str
    overall_feasibility: str
    overall_decision: str
    traceability_total: int
    traceability_offset: int
    traceability_limit: int
    traceability_has_more: bool
    connections: list[TraceabilityConnection]
    outputs: list[OutputAnalysisDetail]

