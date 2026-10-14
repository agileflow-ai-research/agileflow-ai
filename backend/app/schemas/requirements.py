from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.common.id_generator import validate_id
from app.common.status import ApprovalGate
from app.schemas.common import BaseArtifact


class Agent1ArtifactType(str, Enum):
    REQUIREMENT = "REQUIREMENT"
    USER_STORY = "USER_STORY"
    ACCEPTANCE_CRITERION = "ACCEPTANCE_CRITERION"
    QUALITY_FINDING = "QUALITY_FINDING"
    PERSONA = "PERSONA"
    SRS_DOCUMENT = "SRS_DOCUMENT"


class RequirementKind(str, Enum):
    FUNCTIONAL = "FUNCTIONAL"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"


class QualityFindingType(str, Enum):
    AMBIGUITY = "AMBIGUITY"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    CONFLICT = "CONFLICT"
    DUPLICATE = "DUPLICATE"
    INCONSISTENCY = "INCONSISTENCY"


ARTIFACT_ID_PREFIX_BY_TYPE = {
    Agent1ArtifactType.REQUIREMENT: "REQ",
    Agent1ArtifactType.USER_STORY: "US",
    Agent1ArtifactType.ACCEPTANCE_CRITERION: "AC",
    Agent1ArtifactType.QUALITY_FINDING: "REQ",
    Agent1ArtifactType.PERSONA: "REQ",
    Agent1ArtifactType.SRS_DOCUMENT: "REQ",
}


class Agent1Artifact(BaseArtifact):
    """Common H1 constraints for documents stored in `requirements`."""

    approval_gate: Literal[ApprovalGate.H1]

    @model_validator(mode="after")
    def validate_agent1_identity(self) -> "Agent1Artifact":
        artifact_type = Agent1ArtifactType(self.artifact_type)
        validate_id(
            self.artifact_id,
            ARTIFACT_ID_PREFIX_BY_TYPE[artifact_type],
        )
        return self


class Requirement(Agent1Artifact):
    artifact_type: Literal[Agent1ArtifactType.REQUIREMENT]
    requirement_kind: RequirementKind
    statement: str = Field(min_length=1)
    rationale: str | None = None
    priority: str | None = None
    source_reference: str = Field(min_length=1)
    quality_flags: list[str] = Field(default_factory=list)


class UserStory(Agent1Artifact):
    artifact_type: Literal[Agent1ArtifactType.USER_STORY]
    actor: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    benefit: str = Field(min_length=1)
    story_text: str = Field(min_length=1)


class AcceptanceCriteria(Agent1Artifact):
    artifact_type: Literal[Agent1ArtifactType.ACCEPTANCE_CRITERION]
    criterion: str = Field(min_length=1)


class QualityFinding(Agent1Artifact):
    artifact_type: Literal[Agent1ArtifactType.QUALITY_FINDING]
    finding_type: QualityFindingType
    description: str = Field(min_length=1)
    suggested_clarification: str | None = None
    affected_artifact_ids: list[str] = Field(default_factory=list)

    @field_validator("affected_artifact_ids")
    @classmethod
    def validate_affected_artifact_ids(cls, values: list[str]) -> list[str]:
        return [validate_id(value) for value in values]


class Persona(Agent1Artifact):
    artifact_type: Literal[Agent1ArtifactType.PERSONA]
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    goals: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    context: str = Field(min_length=1)


class SrsDocument(Agent1Artifact):
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
