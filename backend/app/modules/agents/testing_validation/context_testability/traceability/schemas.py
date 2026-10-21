from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticFactType,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    TestingIntelligenceLabel,
)

from .constants import (
    LEXICAL_POLICY_VERSION,
    TRACEABILITY_ENGINE_VERSION,
    TRACEABILITY_SCHEMA_VERSION,
)


class StrictTraceabilityContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TraceabilityNodeKind(StrEnum):
    FUNCTIONAL_REQUIREMENT = "FUNCTIONAL_REQUIREMENT"
    NON_FUNCTIONAL_REQUIREMENT = "NON_FUNCTIONAL_REQUIREMENT"
    USER_STORY = "USER_STORY"
    ACCEPTANCE_CRITERION = "ACCEPTANCE_CRITERION"
    FEATURE = "FEATURE"
    API_ENDPOINT = "API_ENDPOINT"
    API_CONTRACT_ITEM = "API_CONTRACT_ITEM"
    DATA_ENTITY = "DATA_ENTITY"
    DATA_FIELD = "DATA_FIELD"
    UI_FLOW_STEP = "UI_FLOW_STEP"
    UI_ELEMENT = "UI_ELEMENT"
    ARCHITECTURE_COMPONENT = "ARCHITECTURE_COMPONENT"
    SEMANTIC_TESTING_FACT = "SEMANTIC_TESTING_FACT"
    GENERIC_EVIDENCE = "GENERIC_EVIDENCE"


class TraceabilityRelationType(StrEnum):
    REFERENCES = "REFERENCES"
    REFINES = "REFINES"
    VALIDATES = "VALIDATES"
    DESCRIBES = "DESCRIBES"
    CONSTRAINS = "CONSTRAINS"
    USES_ENDPOINT = "USES_ENDPOINT"
    USES_ENTITY = "USES_ENTITY"
    USES_FIELD = "USES_FIELD"
    SUPPORTED_BY = "SUPPORTED_BY"
    RELATED_TO = "RELATED_TO"


class TraceabilityEvidenceMethod(StrEnum):
    EXPLICIT_ID = "EXPLICIT_ID"
    EXPLICIT_REFERENCE = "EXPLICIT_REFERENCE"
    API_ENDPOINT = "API_ENDPOINT"
    ENTITY_FIELD = "ENTITY_FIELD"
    FEATURE_NAME = "FEATURE_NAME"
    LEXICAL_SIMILARITY = "LEXICAL_SIMILARITY"


class TraceabilityStrength(StrEnum):
    EXACT = "EXACT"
    STRONG = "STRONG"
    SUPPORTING = "SUPPORTING"


class UnresolvedReferenceType(StrEnum):
    EXPLICIT_ID = "EXPLICIT_ID"
    API_ENDPOINT = "API_ENDPOINT"
    ENTITY = "ENTITY"
    ENTITY_FIELD = "ENTITY_FIELD"
    IMAGE_PENDING_ANALYSIS = "IMAGE_PENDING_ANALYSIS"


class TraceabilityNode(StrictTraceabilityContract):
    node_id: str = Field(pattern=r"^A4TRN-[0-9a-f]{32}$")
    node_kind: TraceabilityNodeKind
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    artifact_type: TestGenerationInputArtifactType
    external_reference_id: str | None = Field(default=None, max_length=80)
    chunk_id: str | None = Field(default=None, pattern=r"^A4CHK-[0-9a-f]{32}$")
    semantic_fact_id: str | None = Field(default=None, pattern=r"^A4FACT-[0-9a-f]{32}$")
    semantic_fact_type: SemanticFactType | None = None
    semantic_labels: list[TestingIntelligenceLabel] = Field(default_factory=list)
    display_value: str = Field(min_length=1, max_length=500)
    canonical_value: str = Field(min_length=1, max_length=500)
    provenance_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_start: int | None = Field(default=None, ge=0)
    evidence_end: int | None = Field(default=None, ge=1)
    api_method: str | None = Field(default=None, pattern=r"^(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$")
    api_path: str | None = Field(default=None, max_length=300)
    entity_name: str | None = Field(default=None, max_length=120)
    field_name: str | None = Field(default=None, max_length=120)
    feature_name: str | None = Field(default=None, max_length=200)
    hybrid_result_id: str | None = Field(default=None, pattern=r"^A4HYB-[0-9a-f]{32}$")
    effective_result_id: str | None = Field(default=None, pattern=r"^A4EFF-[0-9a-f]{32}$")
    review_id: str | None = Field(default=None, pattern=r"^A4N3R-[0-9a-f]{32}$")

    @model_validator(mode="after")
    def validate_shape(self):
        if (self.evidence_start is None) != (self.evidence_end is None):
            raise ValueError("evidence offsets must be supplied together")
        if self.evidence_start is not None and self.evidence_end <= self.evidence_start:
            raise ValueError("evidence end must follow evidence start")
        if self.node_kind is TraceabilityNodeKind.SEMANTIC_TESTING_FACT:
            if (
                not self.semantic_fact_id
                or not self.semantic_fact_type
                or not self.semantic_labels
                or not self.chunk_id
                or not self.hybrid_result_id
            ):
                raise ValueError(
                    "semantic fact nodes require typed fact, label, chunk, and H1 references"
                )
            if self.semantic_labels != sorted(set(self.semantic_labels), key=lambda item: item.value):
                raise ValueError("semantic fact labels must be unique and canonical")
        elif (
            self.semantic_fact_id is not None
            or self.semantic_fact_type is not None
            or self.semantic_labels
        ):
            raise ValueError("only semantic fact nodes may reference semantic facts")
        if (self.api_method is None) != (self.api_path is None):
            raise ValueError("API method and path must be supplied together")
        if self.field_name and not self.entity_name:
            raise ValueError("data field nodes require an entity name")
        return self


class TraceabilityLink(StrictTraceabilityContract):
    traceability_link_id: str = Field(pattern=r"^A4TRL-[0-9a-f]{32}$")
    source_node_id: str = Field(pattern=r"^A4TRN-[0-9a-f]{32}$")
    target_node_id: str = Field(pattern=r"^A4TRN-[0-9a-f]{32}$")
    relation_type: TraceabilityRelationType
    evidence_method: TraceabilityEvidenceMethod
    evidence_references: list[str] = Field(min_length=1)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,79}$")
    explanation: str = Field(min_length=1, max_length=500)
    matched_tokens: list[str] = Field(default_factory=list)
    lexical_score: float | None = Field(default=None, ge=0, le=1)
    strength: TraceabilityStrength
    traceability_version: Literal[TRACEABILITY_ENGINE_VERSION]

    @model_validator(mode="after")
    def validate_link(self):
        if self.source_node_id == self.target_node_id:
            raise ValueError("traceability links require distinct nodes")
        if self.evidence_method is TraceabilityEvidenceMethod.LEXICAL_SIMILARITY:
            if self.lexical_score is None or self.relation_type is not TraceabilityRelationType.RELATED_TO:
                raise ValueError("lexical links require a score and neutral relation")
        elif self.lexical_score is not None:
            raise ValueError("only lexical links may contain lexical_score")
        return self


class UnresolvedTraceabilityReference(StrictTraceabilityContract):
    unresolved_id: str = Field(pattern=r"^A4TRU-[0-9a-f]{32}$")
    source_node_id: str = Field(pattern=r"^A4TRN-[0-9a-f]{32}$")
    reference_type: UnresolvedReferenceType
    reference_value: str = Field(min_length=1, max_length=300)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,79}$")
    evidence_start: int | None = Field(default=None, ge=0)
    evidence_end: int | None = Field(default=None, ge=1)


class AmbiguousTraceabilityMatch(StrictTraceabilityContract):
    ambiguity_id: str = Field(pattern=r"^A4TRA-[0-9a-f]{32}$")
    source_node_id: str = Field(pattern=r"^A4TRN-[0-9a-f]{32}$")
    candidate_node_ids: list[str] = Field(min_length=2)
    evidence_method: TraceabilityEvidenceMethod
    reference_value: str = Field(min_length=1, max_length=300)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,79}$")

    @model_validator(mode="after")
    def validate_candidates(self):
        if self.candidate_node_ids != sorted(set(self.candidate_node_ids)):
            raise ValueError("ambiguity candidates must be unique and canonical")
        return self


class TraceabilityCounts(StrictTraceabilityContract):
    node_count: int = Field(ge=0)
    link_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)


class Agent4TraceabilityManifest(StrictTraceabilityContract):
    schema_version: Literal[TRACEABILITY_SCHEMA_VERSION]
    engine_version: Literal[TRACEABILITY_ENGINE_VERSION]
    lexical_policy_version: Literal[LEXICAL_POLICY_VERSION]
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    confirmation_id: str = Field(pattern=r"^A4N1C-[0-9a-f]{32}$")
    n2_execution_id: str = Field(pattern=r"^A4N2E-[0-9a-f]{32}$")
    n3_execution_id: str = Field(pattern=r"^A4N3E-[0-9a-f]{32}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_fingerprints: dict[str, str]
    nodes: list[TraceabilityNode]
    links: list[TraceabilityLink]
    unresolved_references: list[UnresolvedTraceabilityReference]
    ambiguities: list[AmbiguousTraceabilityMatch]
    counts: TraceabilityCounts
    built_at: datetime

    @model_validator(mode="after")
    def validate_graph(self):
        node_ids = [item.node_id for item in self.nodes]
        link_ids = [item.traceability_link_id for item in self.links]
        if node_ids != sorted(node_ids) or len(node_ids) != len(set(node_ids)):
            raise ValueError("traceability nodes must be unique and canonical")
        if link_ids != sorted(link_ids) or len(link_ids) != len(set(link_ids)):
            raise ValueError("traceability links must be unique and canonical")
        known = set(node_ids)
        if any(link.source_node_id not in known or link.target_node_id not in known for link in self.links):
            raise ValueError("traceability links must resolve to manifest nodes")
        if any(item.source_node_id not in known for item in self.unresolved_references + self.ambiguities):
            raise ValueError("traceability findings must resolve to source nodes")
        if any(not set(item.candidate_node_ids).issubset(known) for item in self.ambiguities):
            raise ValueError("ambiguity candidates must resolve to manifest nodes")
        expected = TraceabilityCounts(
            node_count=len(self.nodes), link_count=len(self.links),
            unresolved_count=len(self.unresolved_references),
            ambiguous_count=len(self.ambiguities),
        )
        if self.counts != expected:
            raise ValueError("traceability counts do not match graph content")
        return self
