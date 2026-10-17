from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.status import AgentRunMode, AgentRunStatus, AgentType
from app.modules.standalone.schemas import AgentRunMessage


class SourceProcessingStatus(StrEnum):
    READY = "READY"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


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


class RequirementSourceType(StrEnum):
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"


ALLOWED_EXTENSIONS: dict[RequirementSourceType, frozenset[str]] = {
    RequirementSourceType.DOCUMENT: frozenset({".pdf", ".docx", ".txt"}),
    RequirementSourceType.AUDIO: frozenset({".mp3", ".wav", ".m4a"}),
    RequirementSourceType.VIDEO: frozenset({".mp4", ".mov", ".webm"}),
}

PREFIX_BY_SOURCE_TYPE: dict[RequirementSourceType, str] = {
    RequirementSourceType.DOCUMENT: "DOC",
    RequirementSourceType.AUDIO: "AUD",
    RequirementSourceType.VIDEO: "VID",
}

SOURCE_TYPE_BY_PREFIX: dict[str, RequirementSourceType] = {
    "DOC": RequirementSourceType.DOCUMENT,
    "AUD": RequirementSourceType.AUDIO,
    "VID": RequirementSourceType.VIDEO,
}

EXTENSION_TO_SOURCE_TYPE: dict[str, RequirementSourceType] = {
    ".pdf": RequirementSourceType.DOCUMENT,
    ".docx": RequirementSourceType.DOCUMENT,
    ".txt": RequirementSourceType.DOCUMENT,
    ".mp3": RequirementSourceType.AUDIO,
    ".wav": RequirementSourceType.AUDIO,
    ".m4a": RequirementSourceType.AUDIO,
    ".mp4": RequirementSourceType.VIDEO,
    ".mov": RequirementSourceType.VIDEO,
    ".webm": RequirementSourceType.VIDEO,
}


class RequirementSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    agent_project_id: str
    owner_user_id: str
    source_type: RequirementSourceType
    original_filename: str
    safe_filename: str
    storage_path: str
    mime_type: str | None = None
    file_size: int
    processing_status: SourceProcessingStatus = SourceProcessingStatus.READY
    normalized_text: str | None = None
    processing_error_code: str | None = None
    processing_error_message: str | None = None
    processed_at: datetime | None = None
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime


class RequirementSourceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_id: str
    agent_project_id: str
    source_type: RequirementSourceType
    original_filename: str
    mime_type: str | None = None
    file_size: int
    processing_status: SourceProcessingStatus = SourceProcessingStatus.READY
    processing_error_code: str | None = None
    processing_error_message: str | None = None
    processed_at: datetime | None = None
    created_at: datetime


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class RequirementSource(BaseModel):
    """A normalised source entry passed into the Agent 1 engine."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: Literal["TEXT", "DOCUMENT"] = "TEXT"
    content: str


class Agent1RunRequest(BaseModel):
    """
    Run request for Agent 1.

    At least one of *text* or uploaded requirement sources must be present.
    Validation of that constraint happens in the service layer (after DB lookup).
    """

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    selected_outputs: list[RequirementOutputCode] = Field(min_length=1)
    background_context: str | None = None
    business_goals: str | None = None
    known_constraints: str | None = None
    existing_requirements: str | None = None
    additional_notes: str | None = None

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

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


class SourceProcessingResult(BaseModel):
    """Safe result for one independently processed requirement source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: RequirementSourceType
    processing_status: SourceProcessingStatus
    processing_error_code: str | None = None
    processing_error_message: str | None = None


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
    id: str = Field(pattern=r"^FR-\d{3,}$")
    statement: str
    source_refs: list[str] = Field(min_length=1)
    rationale: str | None = None


class NonFunctionalRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^NFR-\d{3,}$")
    category: str
    statement: str
    measure: str | None = None
    source_refs: list[str] = Field(min_length=1)


class UserStory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^US-\d{3,}$")
    actor: str
    goal: str
    benefit: str
    source_refs: list[str] = Field(min_length=1)
    requirement_refs: list[str]


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^AC-\d{3,}$")
    related_ids: list[str] = Field(min_length=1)
    given: str
    when: str
    then: str


class Persona(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^PER-\d{3,}$")
    role: str
    goals: list[str] = Field(min_length=1)
    pain_points: list[str]
    context: str


class QualityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^QF-(?:\d{3,}|DUP-\d{3,})$")
    category: QualityFindingCategory
    affected_refs: list[str]
    explanation: str
    suggested_clarification: str | None = None


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(
        pattern=r"^CQ-(?:\d{3,}|DUP-\d{3,}|QF-(?:\d{3,}|DUP-\d{3,}))$"
    )
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
