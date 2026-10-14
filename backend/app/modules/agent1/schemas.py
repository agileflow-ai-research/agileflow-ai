from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.status import AgentRunMode, AgentRunStatus, AgentType
from app.modules.standalone.schemas import AgentRunMessage


class RequirementOutputCode(StrEnum):
    FUNCTIONAL_REQUIREMENTS = "FUNCTIONAL_REQUIREMENTS"
    NON_FUNCTIONAL_REQUIREMENTS = "NON_FUNCTIONAL_REQUIREMENTS"
    USER_STORIES = "USER_STORIES"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    PERSONAS = "PERSONAS"
    QUALITY_FINDINGS = "QUALITY_FINDINGS"
    CLARIFICATION_QUESTIONS = "CLARIFICATION_QUESTIONS"
    SRS = "SRS"


class QualityFindingCategory(StrEnum):
    AMBIGUITY = "AMBIGUITY"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    CONFLICT = "CONFLICT"
    DUPLICATE = "DUPLICATE"
    INCONSISTENCY = "INCONSISTENCY"


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class RequirementSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: str = "TEXT"
    content: str


class Agent1RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    selected_outputs: list[RequirementOutputCode] = Field(min_length=1)
    background_context: str | None = None
    business_goals: str | None = None
    known_constraints: str | None = None
    existing_requirements: str | None = None
    additional_notes: str | None = None

    @field_validator("text")
    @classmethod
    def require_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("at least one non-empty TEXT requirement source is required")
        return normalized

    @field_validator(
        "background_context",
        "business_goals",
        "known_constraints",
        "existing_requirements",
        "additional_notes",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("selected_outputs")
    @classmethod
    def reject_duplicate_outputs(
        cls, values: list[RequirementOutputCode]
    ) -> list[RequirementOutputCode]:
        if len(values) != len(set(values)):
            raise ValueError("selected_outputs must not contain duplicates")
        return values


class Agent1InputContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str
    domain: str
    sources: list[RequirementSource] = Field(min_length=1)
    background_context: str | None = None
    business_goals: str | None = None
    known_constraints: str | None = None
    existing_requirements: str | None = None
    additional_notes: str | None = None


class FunctionalRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    statement: str
    source_refs: list[str] = Field(min_length=1)
    rationale: str | None = None


class NonFunctionalRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: str
    statement: str
    measure: str | None = None
    source_refs: list[str] = Field(min_length=1)


class UserStory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    actor: str
    goal: str
    benefit: str
    source_refs: list[str] = Field(min_length=1)


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    related_ids: list[str] = Field(min_length=1)
    given: str
    when: str
    then: str


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    role: str
    goals: list[str] = Field(min_length=1)
    pain_points: list[str]
    context: str


class QualityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: QualityFindingCategory
    affected_refs: list[str]
    explanation: str
    suggested_clarification: str | None = None


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    question: str
    reason: str
    related_refs: list[str]


class SRSSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    content: str


class SRSArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    overview: str
    sections: list[SRSSection] = Field(min_length=1)
    assumptions: list[str]
    unresolved_issues: list[str]


class Agent1RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_project_id: str
    agent_type: AgentType
    run_mode: AgentRunMode
    status: AgentRunStatus
    selected_outputs: list[str]
    started_at: datetime | None
    completed_at: datetime | None
    outputs: dict[str, Any]
    warnings: list[AgentRunMessage]
    errors: list[AgentRunMessage]
