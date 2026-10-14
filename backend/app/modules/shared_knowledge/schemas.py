from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.id_generator import validate_id
from app.common.status import ApprovalGate
from app.modules.requirements.schemas import Agent1ArtifactModel
from app.schemas.approval import Approval


class ApprovedArtifactSnapshot(BaseModel):
    """Non-persisted typed result for one human-approved artifact package."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    gate_id: Literal[ApprovalGate.H1]
    artifact_version: int = Field(ge=1)
    approval: Approval
    artifacts: list[Agent1ArtifactModel]
    artifact_count: int = Field(ge=1)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")
