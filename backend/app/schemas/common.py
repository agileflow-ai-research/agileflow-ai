from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.common.id_generator import validate_id
from app.common.status import ApprovalGate, ArtifactStatus


class BaseArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    artifact_id: str
    artifact_type: str
    title: str
    status: ArtifactStatus
    approval_gate: ApprovalGate
    created_by_agent: str
    created_at: datetime
    updated_at: datetime
    version: int
    traceability_refs: list[str]

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")

    @field_validator("artifact_id")
    @classmethod
    def validate_artifact_id(cls, value: str) -> str:
        return validate_id(value)

    @field_validator("traceability_refs")
    @classmethod
    def validate_traceability_refs(cls, values: list[str]) -> list[str]:
        return [validate_id(value, "TRACE") for value in values]
