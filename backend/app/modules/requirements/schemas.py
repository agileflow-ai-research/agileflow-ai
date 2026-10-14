from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.common.id_generator import validate_id
from app.common.status import ApprovalGate, ArtifactStatus
from app.schemas.requirements import (
    ARTIFACT_ID_PREFIX_BY_TYPE,
    AcceptanceCriteria,
    Agent1ArtifactType,
    Persona,
    QualityFinding,
    QualityFindingType,
    Requirement,
    RequirementKind,
    SrsDocument,
    UserStory,
)


class ClientInputType(str, Enum):
    TEXT = "TEXT"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    LIVE_INTERVIEW = "LIVE_INTERVIEW"


class ClientInputCreateRequest(BaseModel):
    """Client-controlled fields accepted by the ClientInput endpoint."""

    model_config = ConfigDict(extra="forbid")

    input_type: ClientInputType
    content: str
    original_filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, JsonValue] | None = None


class ClientInputResponse(BaseModel):
    """Public ClientInput representation without MongoDB identity."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    input_type: ClientInputType
    content: str
    original_filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, JsonValue] | None = None
    created_at: datetime


Agent1ArtifactModel: TypeAlias = (
    Requirement
    | UserStory
    | AcceptanceCriteria
    | QualityFinding
    | Persona
    | SrsDocument
)


class Agent1ArtifactInput(BaseModel):
    """Internal pre-persistence artifact fields with optional public identity."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    artifact_id: str | None = None
    artifact_type: Agent1ArtifactType
    title: str
    status: ArtifactStatus
    approval_gate: Literal[ApprovalGate.H1]
    created_by_agent: str
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)
    traceability_refs: list[str] = Field(default_factory=list)

    @field_validator("artifact_type", "title", "created_by_agent")
    @classmethod
    def reject_blank_metadata(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")

    @field_validator("traceability_refs")
    @classmethod
    def validate_traceability_refs(cls, values: list[str]) -> list[str]:
        return [validate_id(value, "TRACE") for value in values]

    @model_validator(mode="after")
    def validate_identity_and_timestamps(self) -> "Agent1ArtifactInput":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        if self.artifact_id is not None:
            validate_id(
                self.artifact_id,
                ARTIFACT_ID_PREFIX_BY_TYPE[self.artifact_type],
            )
        return self


class RequirementInput(Agent1ArtifactInput):
    artifact_type: Literal[Agent1ArtifactType.REQUIREMENT]
    requirement_kind: RequirementKind
    statement: str = Field(min_length=1)
    rationale: str | None = None
    priority: str | None = None
    source_reference: str = Field(min_length=1)
    quality_flags: list[str] = Field(default_factory=list)


class UserStoryInput(Agent1ArtifactInput):
    artifact_type: Literal[Agent1ArtifactType.USER_STORY]
    actor: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    benefit: str = Field(min_length=1)
    story_text: str = Field(min_length=1)


class AcceptanceCriteriaInput(Agent1ArtifactInput):
    artifact_type: Literal[Agent1ArtifactType.ACCEPTANCE_CRITERION]
    criterion: str = Field(min_length=1)


class QualityFindingInput(Agent1ArtifactInput):
    artifact_type: Literal[Agent1ArtifactType.QUALITY_FINDING]
    finding_type: QualityFindingType
    description: str = Field(min_length=1)
    suggested_clarification: str | None = None
    affected_artifact_ids: list[str] = Field(default_factory=list)

    @field_validator("affected_artifact_ids")
    @classmethod
    def validate_affected_artifact_ids(cls, values: list[str]) -> list[str]:
        return [validate_id(value) for value in values]


class PersonaInput(Agent1ArtifactInput):
    artifact_type: Literal[Agent1ArtifactType.PERSONA]
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    goals: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    context: str = Field(min_length=1)


class SrsDocumentInput(Agent1ArtifactInput):
    artifact_type: Literal[Agent1ArtifactType.SRS_DOCUMENT]
    overview: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    user_story_ids: list[str] = Field(default_factory=list)
    acceptance_criteria_ids: list[str] = Field(default_factory=list)
    persona_ids: list[str] = Field(default_factory=list)
    quality_finding_ids: list[str] = Field(default_factory=list)

    @field_validator("requirement_ids", "persona_ids", "quality_finding_ids")
    @classmethod
    def validate_requirement_family_ids(cls, values: list[str]) -> list[str]:
        return [validate_id(value, "REQ") for value in values]

    @field_validator("user_story_ids")
    @classmethod
    def validate_user_story_ids(cls, values: list[str]) -> list[str]:
        return [validate_id(value, "US") for value in values]

    @field_validator("acceptance_criteria_ids")
    @classmethod
    def validate_acceptance_criteria_ids(cls, values: list[str]) -> list[str]:
        return [validate_id(value, "AC") for value in values]


Agent1ArtifactInputModel: TypeAlias = Annotated[
    RequirementInput
    | UserStoryInput
    | AcceptanceCriteriaInput
    | QualityFindingInput
    | PersonaInput
    | SrsDocumentInput,
    Field(discriminator="artifact_type"),
]


class H1SnapshotResult(BaseModel):
    """Typed result for one persisted logical H1 package."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    version: int = Field(ge=1)
    artifacts: list[Agent1ArtifactModel]

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")
