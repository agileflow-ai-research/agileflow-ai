from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.id_generator import validate_id


class TraceabilityLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    project_id: str
    source_artifact_id: str = Field(min_length=1)
    source_artifact_type: str
    target_artifact_id: str = Field(min_length=1)
    target_artifact_type: str
    relation_type: str
    created_at: datetime

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, value: str) -> str:
        return validate_id(value, "TRACE")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_id(value, "PRJ")

    @field_validator(
        "source_artifact_id",
        "target_artifact_id",
    )
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def validate_distinct_artifacts(self) -> "TraceabilityLink":
        if self.source_artifact_id == self.target_artifact_id:
            raise ValueError("source and target artifact IDs must be different")
        return self
