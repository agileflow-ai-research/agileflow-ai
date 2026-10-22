from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.modules.agents.requirements.workflow.contracts.common import (
    StrictWorkflowContract,
)


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


class RequirementOutputSelectionUpdate(StrictWorkflowContract):
    selected_outputs: list[RequirementOutputCode] = Field(min_length=1)

    @field_validator("selected_outputs")
    @classmethod
    def reject_duplicates(
        cls, value: list[RequirementOutputCode]
    ) -> list[RequirementOutputCode]:
        if len(value) != len(set(value)):
            raise ValueError("selected_outputs must not contain duplicates")
        return value


class RequirementN1Confirmation(StrictWorkflowContract):
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_at: datetime
