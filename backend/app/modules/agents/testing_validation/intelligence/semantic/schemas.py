from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.modules.agents.testing_validation.intelligence.schemas import (
    StrictIntelligenceContract,
    TestingChunkReference,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TestingIntelligenceLabel,
)

from . import constants


class SemanticFactType(StrEnum):
    BEHAVIOR = "BEHAVIOR"
    ACTOR_ACTION = "ACTOR_ACTION"
    INPUT_CONSTRAINT = "INPUT_CONSTRAINT"
    BOUNDARY_CONSTRAINT = "BOUNDARY_CONSTRAINT"
    DATA_INTEGRITY_CONSTRAINT = "DATA_INTEGRITY_CONSTRAINT"
    API_CONTRACT = "API_CONTRACT"
    UI_INTERACTION = "UI_INTERACTION"
    AUTHENTICATION_REQUIREMENT = "AUTHENTICATION_REQUIREMENT"
    AUTHORIZATION_RULE = "AUTHORIZATION_RULE"
    SECURITY_CONTROL = "SECURITY_CONTROL"
    PERFORMANCE_TARGET = "PERFORMANCE_TARGET"
    RELIABILITY_RECOVERY = "RELIABILITY_RECOVERY"
    ERROR_EXPECTATION = "ERROR_EXPECTATION"
    ACCEPTANCE_CONDITION = "ACCEPTANCE_CONDITION"
    STATE_PERSISTENCE = "STATE_PERSISTENCE"
    PRECONDITION = "PRECONDITION"
    POSTCONDITION = "POSTCONDITION"
    EXPECTED_OUTCOME = "EXPECTED_OUTCOME"


class SemanticEligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    WAITING_FOR_CLASSIFICATION_REVIEW = "WAITING_FOR_CLASSIFICATION_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SemanticResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    SUCCESS_WITH_WARNINGS = "SUCCESS_WITH_WARNINGS"
    EMPTY = "EMPTY"
    WAITING_FOR_CLASSIFICATION_REVIEW = "WAITING_FOR_CLASSIFICATION_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SemanticWarning(StrictIntelligenceContract):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,79}$")
    message: str = Field(min_length=1, max_length=500)
    candidate_index: int | None = Field(default=None, ge=0)


class SemanticFactCandidate(StrictIntelligenceContract):
    fact_type: SemanticFactType
    related_labels: list[TestingIntelligenceLabel] = Field(min_length=1)
    evidence_quote: str = Field(min_length=1, max_length=4000)
    evidence_start: int | None = Field(default=None, ge=0)
    evidence_end: int | None = Field(default=None, ge=1)
    actor: str | None = None
    role: str | None = None
    action: str | None = None
    target: str | None = None
    field_name: str | None = None
    operator: str | None = None
    value: str | int | float | bool | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    unit: str | None = None
    allowed_values: list[str] = Field(default_factory=list)
    disallowed_values: list[str] = Field(default_factory=list)
    api_method: str | None = None
    api_endpoint: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    precondition: str | None = None
    postcondition: str | None = None
    expected_outcome: str | None = None
    security_mechanism: str | None = None
    performance_metric: str | None = None
    reliability_condition: str | None = None
    persistence_behavior: str | None = None

    @field_validator("related_labels")
    @classmethod
    def canonical_labels(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("related labels must be unique")
        selected = set(value)
        return [label for label in TESTING_INTELLIGENCE_LABEL_ORDER if label in selected]

    @model_validator(mode="after")
    def validate_offsets_and_content(self):
        if (self.evidence_start is None) != (self.evidence_end is None):
            raise ValueError("evidence offsets must be supplied together")
        if self.evidence_start is not None and self.evidence_end <= self.evidence_start:
            raise ValueError("evidence end must follow evidence start")
        semantic = self.model_dump(exclude={
            "fact_type", "related_labels", "evidence_quote",
            "evidence_start", "evidence_end",
        })
        if not any(value not in (None, [], "") for value in semantic.values()):
            raise ValueError("a semantic fact must contain structured content")
        return self


class SemanticFact(SemanticFactCandidate):
    fact_id: str = Field(pattern=r"^A4FACT-[0-9a-f]{32}$")


class SemanticClassificationContext(StrictIntelligenceContract):
    chunk_id: str = Field(pattern=r"^A4CHK-[0-9a-f]{32}$")
    hybrid_result_id: str = Field(pattern=r"^A4HYB-[0-9a-f]{32}$")
    effective_result_id: str | None = Field(default=None, pattern=r"^A4EFF-[0-9a-f]{32}$")
    context_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    accepted_labels: list[TestingIntelligenceLabel]
    review_required_labels: list[TestingIntelligenceLabel]
    eligibility: SemanticEligibility


class SemanticGenerationMetadata(StrictIntelligenceContract):
    attempt_count: int = Field(ge=0, le=constants.MAX_SEMANTIC_ATTEMPTS)
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    generation_duration_ms: int = Field(ge=0)
    device: str | None = None


class TestingSemanticResult(StrictIntelligenceContract):
    semantic_result_id: str = Field(pattern=r"^A4SEM-[0-9a-f]{32}$")
    chunk: TestingChunkReference
    taxonomy_version: Literal[AGENT4_TESTING_TAXONOMY_VERSION]
    hybrid_policy_version: Literal["H1"]
    hybrid_result_id: str = Field(pattern=r"^A4HYB-[0-9a-f]{32}$")
    effective_result_id: str | None = Field(default=None, pattern=r"^A4EFF-[0-9a-f]{32}$")
    classification_context_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    accepted_labels: list[TestingIntelligenceLabel]
    semantic_schema_version: Literal[constants.SEMANTIC_SCHEMA_VERSION]
    semantic_stage_version: Literal[constants.SEMANTIC_STAGE_VERSION]
    prompt_version: Literal[constants.SEMANTIC_PROMPT_VERSION]
    grounding_version: Literal[constants.SEMANTIC_GROUNDING_VERSION]
    model_id: Literal[constants.SEMANTIC_MODEL_ID]
    model_revision: Literal[constants.SEMANTIC_MODEL_REVISION]
    generation_policy_version: Literal[constants.SEMANTIC_GENERATION_POLICY_VERSION]
    status: SemanticResultStatus
    facts: list[SemanticFact] = Field(default_factory=list)
    rejected_candidate_count: int = Field(default=0, ge=0)
    warnings: list[SemanticWarning] = Field(default_factory=list)
    generation: SemanticGenerationMetadata
    processed_at: datetime

    @field_validator("accepted_labels")
    @classmethod
    def canonical_accepted_labels(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("accepted semantic labels must be unique")
        if TestingIntelligenceLabel.NON_TESTABLE_CONTEXT in value:
            raise ValueError("non-testable context cannot scope semantic facts")
        selected = set(value)
        return [label for label in TESTING_INTELLIGENCE_LABEL_ORDER if label in selected]

    @model_validator(mode="after")
    def validate_result(self):
        usable = {
            SemanticResultStatus.SUCCESS,
            SemanticResultStatus.SUCCESS_WITH_WARNINGS,
        }
        if self.status not in usable and self.facts:
            raise ValueError("non-usable semantic dispositions cannot contain facts")
        if self.status is SemanticResultStatus.SUCCESS and self.warnings:
            raise ValueError("successful semantic result cannot contain warnings")
        if self.status is SemanticResultStatus.SUCCESS_WITH_WARNINGS and not self.warnings:
            raise ValueError("warning status requires warnings")
        if self.status in usable and not self.facts:
            raise ValueError("successful semantic result requires grounded facts")
        if len({fact.fact_id for fact in self.facts}) != len(self.facts):
            raise ValueError("semantic fact identities must be unique")
        accepted = set(self.accepted_labels)
        if any(not set(fact.related_labels).issubset(accepted) for fact in self.facts):
            raise ValueError("semantic fact labels must be accepted concerns")
        return self


class SemanticManifestMetrics(StrictIntelligenceContract):
    chunk_count: int = Field(ge=1)
    eligible_count: int = Field(ge=0)
    waiting_review_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    fact_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)


class SemanticGenerationPolicyMetadata(StrictIntelligenceContract):
    do_sample: Literal[False]
    max_input_tokens: Literal[constants.MAX_SEMANTIC_INPUT_TOKENS]
    max_new_tokens: Literal[constants.MAX_SEMANTIC_NEW_TOKENS]
    max_attempts: Literal[constants.MAX_SEMANTIC_ATTEMPTS]
    local_files_only: Literal[True]


class TestingSemanticManifest(StrictIntelligenceContract):
    schema_version: Literal["1"] = "1"
    semantic_stage_version: Literal[constants.SEMANTIC_STAGE_VERSION]
    prompt_version: Literal[constants.SEMANTIC_PROMPT_VERSION]
    grounding_version: Literal[constants.SEMANTIC_GROUNDING_VERSION]
    generation_policy_version: Literal[constants.SEMANTIC_GENERATION_POLICY_VERSION]
    model_id: Literal[constants.SEMANTIC_MODEL_ID]
    model_revision: Literal[constants.SEMANTIC_MODEL_REVISION]
    generation_configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation_policy: SemanticGenerationPolicyMetadata
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    source_id: str = Field(pattern=r"^A4SRC-[0-9a-f]{32}$")
    chunk_set_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    hybrid_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_manifest_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    chunk_ids: list[str] = Field(min_length=1)
    eligible_chunk_ids: list[str]
    waiting_review_chunk_ids: list[str]
    not_applicable_chunk_ids: list[str]
    results: list[TestingSemanticResult] = Field(min_length=1)
    metrics: SemanticManifestMetrics
    processed_at: datetime

    @model_validator(mode="after")
    def validate_manifest(self):
        if self.chunk_ids != [result.chunk.chunk_id for result in self.results]:
            raise ValueError("semantic results must match ordered chunk IDs")
        if any(
            result.chunk.agent_project_id != self.agent_project_id
            or result.chunk.source_id != self.source_id
            or result.chunk.chunk_set_fingerprint != self.chunk_set_fingerprint
            for result in self.results
        ):
            raise ValueError("semantic result provenance does not match manifest")
        groups = self.eligible_chunk_ids + self.waiting_review_chunk_ids + self.not_applicable_chunk_ids
        if len(groups) != len(set(groups)) or set(groups) != set(self.chunk_ids):
            raise ValueError("semantic dispositions must partition current chunks")
        expected = SemanticManifestMetrics(
            chunk_count=len(self.results),
            eligible_count=len(self.eligible_chunk_ids),
            waiting_review_count=len(self.waiting_review_chunk_ids),
            not_applicable_count=len(self.not_applicable_chunk_ids),
            fact_count=sum(len(result.facts) for result in self.results),
            warning_count=sum(len(result.warnings) for result in self.results),
        )
        if self.metrics != expected:
            raise ValueError("semantic metrics do not match results")
        return self


class SemanticCandidateEnvelope(StrictIntelligenceContract):
    facts: list[dict[str, Any]]
