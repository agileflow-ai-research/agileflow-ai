from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.id_generator import validate_id
from app.common.status import ApprovalDecision, ApprovalGate, WorkflowStage


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    project_id: str
    gate_id: ApprovalGate
    reviewer_name: str | None = None
    reviewer_role: str | None = None
    decision: ApprovalDecision
    comment: str
    timestamp: datetime
    artifact_version: int = Field(gt=0)
    next_stage: WorkflowStage

    @field_validator("approval_id")
    @classmethod
    def validate_approval_id(cls, value: str) -> str:
        return validate_id(value, "APP")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")

    @model_validator(mode="after")
    def validate_reviewer(self) -> "Approval":
        if self.reviewer_name is None and self.reviewer_role is None:
            raise ValueError("reviewer_name or reviewer_role is required")
        return self
