from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequirementOutputCode(StrEnum):
    FUNCTIONAL_REQUIREMENTS = "FUNCTIONAL_REQUIREMENTS"
    NON_FUNCTIONAL_REQUIREMENTS = "NON_FUNCTIONAL_REQUIREMENTS"
    USER_STORIES = "USER_STORIES"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    PERSONAS = "PERSONAS"
    SRS = "SRS"


class RequirementN1State(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETE = "COMPLETE"


class RequirementOutputSelectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_outputs: list[RequirementOutputCode] = Field(min_length=1)

    @field_validator("selected_outputs")
    @classmethod
    def reject_duplicates(
        cls, value: list[RequirementOutputCode]
    ) -> list[RequirementOutputCode]:
        if len(value) != len(set(value)):
            raise ValueError("selected_outputs must not contain duplicates")
        return value


class RequirementN1Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_at: datetime


class RequirementWorkflowRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    workflow_version: str
    agent_project_id: str
    owner_user_id: str
    selected_outputs: list[RequirementOutputCode]
    selection_revision: int = Field(ge=0)
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    n1_confirmation: RequirementN1Confirmation | None = None
    created_at: datetime
    updated_at: datetime


class RequirementWorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    workflow_version: str
    agent_project_id: str
    selected_outputs: list[RequirementOutputCode]
    selection_revision: int
    selection_digest: str
    source_set_digest: str
    source_count: int
    n1_state: RequirementN1State
    n1_confirmation_current: bool
    confirmed_source_set_digest: str | None = None
    confirmed_selection_digest: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
