from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app.common.id_generator import validate_id
from app.common.status import EventType, WorkflowStage


class WorkflowEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    project_id: str
    event_type: EventType
    source_component: str
    target_component: str | None = None
    stage_before: WorkflowStage | None = None
    stage_after: WorkflowStage | None = None
    message: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        return validate_id(value, "EVT")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")
