from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.common.id_generator import validate_id
from app.common.status import ArtifactStatus, WorkflowStage


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    domain: str
    description: str
    current_stage: WorkflowStage
    status: ArtifactStatus
    created_by: str
    created_at: datetime
    updated_at: datetime

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")
