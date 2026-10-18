from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.implementation.semantic_discovery.canonical.schemas import (
    CanonicalArtifact, CanonicalSourceRef, CanonicalStatus, NfrCategory,
    UnresolvedItem,
)
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
)

from . import constants


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


SemanticText = Annotated[
    str, Field(min_length=1, max_length=constants.MAX_SEMANTIC_STRING_CHARACTERS)
]


class EvidenceSpan(StrictModel):
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    quote: str = Field(
        min_length=1, max_length=constants.MAX_EVIDENCE_QUOTE_CHARACTERS
    )
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def offsets_are_a_pair(self):
        if (self.start_char is None) != (self.end_char is None):
            raise ValueError("Evidence offsets must be supplied together")
        if self.start_char is not None and self.end_char <= self.start_char:
            raise ValueError("Evidence end offset must follow its start offset")
        return self


EvidenceList = Annotated[
    list[EvidenceSpan],
    Field(min_length=1, max_length=constants.MAX_EVIDENCE_ENTRIES_PER_ITEM),
]
SemanticStringList = Annotated[
    list[SemanticText], Field(max_length=constants.MAX_LIST_VALUES_PER_FIELD)
]


class RequirementProposal(StrictModel):
    id: SemanticText | None = None
    statement: SemanticText
    evidence: EvidenceList


class NfrProposal(RequirementProposal):
    category: NfrCategory | None = None
    measurable_target: SemanticText | None = None


class UserStoryProposal(StrictModel):
    id: SemanticText | None = None
    role: SemanticText | None = None
    goal: SemanticText | None = None
    benefit: SemanticText | None = None
    raw_statement: SemanticText
    evidence: EvidenceList


class AcceptanceCriterionProposal(StrictModel):
    id: SemanticText | None = None
    statement: SemanticText
    given: SemanticText | None = None
    when: SemanticText | None = None
    then: SemanticText | None = None
    evidence: EvidenceList


class ApiEndpointProposal(StrictModel):
    id: SemanticText | None = None
    method: Annotated[str, Field(pattern=r"^[A-Z]+$", max_length=20)] | None = None
    path: Annotated[str, Field(pattern=r"^/", max_length=500)] | None = None
    description: SemanticText | None = None
    request_fields: SemanticStringList = Field(default_factory=list)
    response_statuses: Annotated[list[int], Field(max_length=50)] = Field(default_factory=list)
    evidence: EvidenceList


class DatabaseFieldProposal(StrictModel):
    name: SemanticText
    type: SemanticText | None = None
    nullable: bool | None = None
    primary_key: bool | None = None
    foreign_key: SemanticText | None = None
    evidence: EvidenceList


class DatabaseEntityProposal(StrictModel):
    name: SemanticText
    fields: Annotated[
        list[DatabaseFieldProposal],
        Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT),
    ] = Field(default_factory=list)
    evidence: EvidenceList


class ArchitectureComponentProposal(StrictModel):
    name: SemanticText
    type: SemanticText | None = None
    evidence: EvidenceList


class ArchitectureRelationshipProposal(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    from_component: SemanticText = Field(alias="from")
    to: SemanticText
    description: SemanticText | None = None
    evidence: EvidenceList


class ArchitectureStatementProposal(StrictModel):
    statement: SemanticText
    evidence: EvidenceList


class UiFlowStepProposal(StrictModel):
    order: int = Field(ge=1, le=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)
    screen_or_action: SemanticText
    evidence: EvidenceList


class UiFlowProposal(StrictModel):
    name: SemanticText | None = None
    steps: Annotated[
        list[UiFlowStepProposal],
        Field(min_length=1, max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT),
    ]
    evidence: EvidenceList


class TechnologyStackProposalData(StrictModel):
    frontend: SemanticStringList = Field(default_factory=list)
    styling: SemanticStringList = Field(default_factory=list)
    backend: SemanticStringList = Field(default_factory=list)
    database: SemanticStringList = Field(default_factory=list)
    languages: SemanticStringList = Field(default_factory=list)
    api_styles: SemanticStringList = Field(default_factory=list)
    other: SemanticStringList = Field(default_factory=list)
    evidence: EvidenceList


class TechnicalConstraintProposal(StrictModel):
    id: SemanticText | None = None
    statement: SemanticText
    constraint_type: SemanticText | None = None
    evidence: EvidenceList


class ImplementationTaskProposal(StrictModel):
    id: SemanticText | None = None
    title: SemanticText
    description: SemanticText | None = None
    evidence: EvidenceList


class TestCaseProposal(StrictModel):
    id: SemanticText | None = None
    description: SemanticText | None = None
    preconditions: SemanticStringList = Field(default_factory=list)
    steps: SemanticStringList = Field(default_factory=list)
    expected_result: SemanticText | None = None
    evidence: EvidenceList


class FunctionalRequirementsProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS]
    requirements: Annotated[list[RequirementProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class NonFunctionalRequirementsProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS]
    requirements: Annotated[list[NfrProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class UserStoriesProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.USER_STORIES]
    stories: Annotated[list[UserStoryProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class AcceptanceCriteriaProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.ACCEPTANCE_CRITERIA]
    criteria: Annotated[list[AcceptanceCriterionProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class ApiSpecificationProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.API_SPECIFICATION]
    endpoints: Annotated[list[ApiEndpointProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class DatabaseSchemaProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.DATABASE_SCHEMA]
    entities: Annotated[list[DatabaseEntityProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class SystemArchitectureProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.SYSTEM_ARCHITECTURE]
    components: Annotated[list[ArchitectureComponentProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)] = Field(default_factory=list)
    relationships: Annotated[list[ArchitectureRelationshipProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)] = Field(default_factory=list)
    raw_architecture_statements: Annotated[list[ArchitectureStatementProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)] = Field(default_factory=list)


class UiFlowSemanticProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.UI_FLOW]
    flows: Annotated[list[UiFlowProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class TechnologyStackProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.TECHNOLOGY_STACK]
    stack: TechnologyStackProposalData


class TechnicalConstraintsProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS]
    constraints: Annotated[list[TechnicalConstraintProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class ImplementationTasksProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.IMPLEMENTATION_TASKS]
    tasks: Annotated[list[ImplementationTaskProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


class TestCasesProposal(StrictModel):
    artifact_type: Literal[ArtifactDetectionLabel.TEST_CASES]
    test_cases: Annotated[list[TestCaseProposal], Field(max_length=constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)]


SemanticExtractionProposal = Annotated[
    FunctionalRequirementsProposal | NonFunctionalRequirementsProposal
    | UserStoriesProposal | AcceptanceCriteriaProposal
    | SystemArchitectureProposal | DatabaseSchemaProposal
    | ApiSpecificationProposal | UiFlowSemanticProposal
    | TechnologyStackProposal | TechnicalConstraintsProposal
    | ImplementationTasksProposal | TestCasesProposal,
    Field(discriminator="artifact_type"),
]


class SemanticExtractionRequest(StrictModel):
    project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    chunk_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_type: ArtifactDetectionLabel
    verified_labels: Annotated[list[ArtifactDetectionLabel], Field(min_length=1, max_length=13)]
    source_text: str = Field(min_length=1, max_length=1_000_000)
    deterministic_artifact: CanonicalArtifact
    unresolved_items: list[UnresolvedItem]
    target_schema_version: Literal["1"] = "1"
    semantic_contract_version: Literal["1"] = "1"


class SemanticValidationStatus(StrEnum):
    GROUNDED = "GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    REJECTED = "REJECTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class SemanticResultStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class FactRejection(StrictModel):
    code: Literal["UNSUPPORTED_BY_SOURCE"]
    field_path: str
    proposed_value: Any
    reason: str


class SemanticConflict(StrictModel):
    code: Literal[
        "SEMANTIC_DETERMINISTIC_CONFLICT", "CONFLICTING_SEMANTIC_FACTS"
    ]
    field_path: str
    deterministic_value: Any | None = None
    semantic_value: Any
    semantic_evidence: list[EvidenceSpan]


class SemanticValidationReport(StrictModel):
    proposal_status: SemanticValidationStatus
    accepted_facts: int = Field(ge=0)
    rejected_facts: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    rejections: list[FactRejection]
    conflicts: list[SemanticConflict]


class FieldOrigin(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC = "SEMANTIC"


class SemanticFieldProvenance(StrictModel):
    field_path: str
    origin: FieldOrigin
    source_refs: list[CanonicalSourceRef] = Field(default_factory=list)
    evidence: list[EvidenceSpan] = Field(default_factory=list)


class MergedSemanticArtifact(StrictModel):
    artifact_id: str = Field(pattern=r"^CA-[0-9A-F]{24}$")
    artifact_type: ArtifactDetectionLabel
    status: SemanticResultStatus
    data: dict[str, Any]
    field_provenance: list[SemanticFieldProvenance]
    conflicts: list[SemanticConflict]


class SemanticExtractionSessionResult(StrictModel):
    artifact_id: str
    artifact_type: ArtifactDetectionLabel
    deterministic_status: CanonicalStatus
    semantic_contract_version: Literal["1"]
    grounding_version: Literal["1"]
    merge_policy_version: Literal["1"]
    proposal: SemanticExtractionProposal
    validation: SemanticValidationReport
    merged_artifact: MergedSemanticArtifact | None


class SemanticArtifactRunStatus(StrEnum):
    SKIPPED_COMPLETE = "SKIPPED_COMPLETE"
    GROUNDED = "GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    REJECTED = "REJECTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    MODEL_ERROR = "MODEL_ERROR"


class SemanticModelMetadata(StrictModel):
    model_id: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    device: Literal["cpu", "cuda"]


class SemanticGenerationMetrics(StrictModel):
    attempt_count: int = Field(ge=1)
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    generation_ms: int = Field(ge=0)
    first_model_load_ms: int = Field(ge=0)


class SemanticArtifactRunResult(StrictModel):
    artifact_id: str = Field(pattern=r"^CA-[0-9A-F]{24}$")
    artifact_type: ArtifactDetectionLabel
    deterministic_status: CanonicalStatus
    status: SemanticArtifactRunStatus
    model: SemanticModelMetadata | None = None
    generation: SemanticGenerationMetrics | None = None
    semantic_proposal: SemanticExtractionProposal | None = None
    validation: SemanticValidationReport | None = None
    merged_preview: MergedSemanticArtifact | None = None
    error_code: Literal["MODEL_OUTPUT_INVALID", "MODEL_ERROR"] | None = None


class SemanticArtifactMetrics(StrictModel):
    artifact_count: int = Field(ge=0)
    target_artifact_count: int = Field(ge=0)
    skipped_complete_count: int = Field(ge=0)
    grounded_count: int = Field(ge=0)
    partially_grounded_count: int = Field(ge=0)
    human_review_required_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    model_output_invalid_count: int = Field(ge=0)
    model_error_count: int = Field(ge=0)
    accepted_fact_count: int = Field(ge=0)
    rejected_fact_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    total_attempt_count: int = Field(ge=0)
    total_generation_ms: int = Field(ge=0)
    first_model_load_ms: int = Field(ge=0)


class DocumentSemanticArtifactResult(StrictModel):
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    original_filename: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    human_review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_id_hashes: dict[str, str]
    semantic_contract_version: str
    grounding_version: str
    merge_policy_version: str
    adapter_version: str
    model_id: str
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    prompt_version: str
    generation_policy_version: str
    results: list[SemanticArtifactRunResult]
    metrics: SemanticArtifactMetrics
    warnings: list[str]
    created_at: datetime
