from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.implementation.extraction.schemas import DocumentType
from app.modules.agents.implementation.semantic_discovery.schemas import ArtifactDetectionLabel


class CanonicalStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"


class CanonicalSourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    chunk_id: str = Field(pattern=r"^CHK-[0-9A-F]{20}$")
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_filename: str = Field(min_length=1, max_length=255)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    block_start: int | None = Field(default=None, ge=1)
    block_end: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    structured_path: str | None = Field(default=None, max_length=500)


class UnresolvedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,100}$")
    source_ref: CanonicalSourceRef


class RequirementItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    statement: str = Field(min_length=1)
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class FunctionalRequirementsData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: list[RequirementItem]


class NfrCategory(StrEnum):
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    AVAILABILITY = "AVAILABILITY"
    USABILITY = "USABILITY"
    SCALABILITY = "SCALABILITY"
    RELIABILITY = "RELIABILITY"
    MAINTAINABILITY = "MAINTAINABILITY"
    COMPATIBILITY = "COMPATIBILITY"


class NonFunctionalRequirementItem(RequirementItem):
    category: NfrCategory | None = None
    measurable_target: str | None = None


class NonFunctionalRequirementsData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: list[NonFunctionalRequirementItem]


class UserStoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    role: str | None = None
    goal: str | None = None
    benefit: str | None = None
    raw_statement: str = Field(min_length=1)
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class UserStoriesData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stories: list[UserStoryItem]


class AcceptanceCriterionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    statement: str = Field(min_length=1)
    given: str | None = None
    when: str | None = None
    then: str | None = None
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class AcceptanceCriteriaData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criteria: list[AcceptanceCriterionItem]


class ApiEndpointItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    method: str = Field(pattern=r"^[A-Z]+$")
    path: str = Field(pattern=r"^/")
    description: str | None = None
    request_fields: list[str]
    response_statuses: list[int]
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class ApiSpecificationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoints: list[ApiEndpointItem]


class DatabaseFieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    type: str | None = None
    nullable: bool | None = None
    primary_key: bool = False
    foreign_key: str | None = None


class DatabaseEntityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    fields: list[DatabaseFieldItem]
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class DatabaseSchemaData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[DatabaseEntityItem]


class ArchitectureComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    type: str | None = None
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class ArchitectureRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_component: str = Field(alias="from", min_length=1)
    to: str = Field(min_length=1)
    description: str | None = None
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class ArchitectureStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1)
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class SystemArchitectureData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    components: list[ArchitectureComponent]
    relationships: list[ArchitectureRelationship]
    raw_architecture_statements: list[ArchitectureStatement]


class UiFlowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: int = Field(ge=1)
    screen_or_action: str = Field(min_length=1)


class UiFlowItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    steps: list[UiFlowStep]
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class UiFlowData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flows: list[UiFlowItem]


class TechnologyStackData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frontend: list[str]
    styling: list[str]
    backend: list[str]
    database: list[str]
    languages: list[str]
    api_styles: list[str]
    other: list[str]
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class TechnicalConstraintItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    statement: str = Field(min_length=1)
    constraint_type: str | None = None
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class TechnicalConstraintsData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    constraints: list[TechnicalConstraintItem]


class ImplementationTaskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class ImplementationTasksData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tasks: list[ImplementationTaskItem]


class TestCaseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    description: str | None = None
    preconditions: list[str]
    steps: list[str]
    expected_result: str | None = None
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class TestCasesData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_cases: list[TestCaseItem]


class OtherContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)


class OtherContextData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_items: list[OtherContextItem]
    usable_for_generation: Literal[False] = False


CanonicalData = (
    FunctionalRequirementsData | NonFunctionalRequirementsData | UserStoriesData
    | AcceptanceCriteriaData | ApiSpecificationData | DatabaseSchemaData
    | SystemArchitectureData | UiFlowData | TechnologyStackData
    | TechnicalConstraintsData | ImplementationTasksData | TestCasesData
    | OtherContextData
)


class CanonicalArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: str = Field(pattern=r"^CA-[0-9A-F]{24}$")
    artifact_type: ArtifactDetectionLabel
    extraction_method: Literal["DETERMINISTIC"] = "DETERMINISTIC"
    status: CanonicalStatus
    data: CanonicalData
    source_refs: list[CanonicalSourceRef] = Field(min_length=1)
    unresolved_items: list[UnresolvedItem]
    canonical_schema_version: str = Field(pattern=r"^\d+$")
    extractor_version: str = Field(pattern=r"^\d+$")
    created_at: datetime

    @model_validator(mode="after")
    def require_item_sources(self):
        if not self.source_refs:
            raise ValueError("Canonical artifacts require source evidence")
        expected_data_type = {
            ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS: FunctionalRequirementsData,
            ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS: NonFunctionalRequirementsData,
            ArtifactDetectionLabel.USER_STORIES: UserStoriesData,
            ArtifactDetectionLabel.ACCEPTANCE_CRITERIA: AcceptanceCriteriaData,
            ArtifactDetectionLabel.SYSTEM_ARCHITECTURE: SystemArchitectureData,
            ArtifactDetectionLabel.DATABASE_SCHEMA: DatabaseSchemaData,
            ArtifactDetectionLabel.API_SPECIFICATION: ApiSpecificationData,
            ArtifactDetectionLabel.UI_FLOW: UiFlowData,
            ArtifactDetectionLabel.TECHNOLOGY_STACK: TechnologyStackData,
            ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS: TechnicalConstraintsData,
            ArtifactDetectionLabel.IMPLEMENTATION_TASKS: ImplementationTasksData,
            ArtifactDetectionLabel.TEST_CASES: TestCasesData,
            ArtifactDetectionLabel.OTHER_CONTEXT: OtherContextData,
        }[self.artifact_type]
        if not isinstance(self.data, expected_data_type):
            raise ValueError("Canonical artifact data does not match artifact_type")
        return self


class CanonicalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified_chunk_count: int = Field(ge=0)
    canonical_artifact_count: int = Field(ge=0)
    complete_artifact_count: int = Field(ge=0)
    partial_artifact_count: int = Field(ge=0)
    unresolved_artifact_count: int = Field(ge=0)
    per_artifact_type_counts: dict[ArtifactDetectionLabel, int]


class DocumentCanonicalArtifactResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    original_filename: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: DocumentType
    extraction_version: str = Field(pattern=r"^\d+$")
    chunker_version: str = Field(pattern=r"^\d+$")
    human_review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    human_review_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_schema_version: str = Field(pattern=r"^\d+$")
    extractor_version: str = Field(pattern=r"^\d+$")
    status: CanonicalStatus
    artifacts: list[CanonicalArtifact]
    metrics: CanonicalMetrics
    warnings: list[str]
    created_at: datetime
