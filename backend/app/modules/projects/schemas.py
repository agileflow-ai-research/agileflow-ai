from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class ProjectCreateRequest(BaseModel):
    """Client-controlled fields accepted when creating a project."""

    model_config = ConfigDict(extra="forbid")

    name: str
    domain: str
    description: str
    created_by: str


class ProjectUpdateRequest(BaseModel):
    """Basic project metadata that may be changed outside the Orchestrator."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    domain: str | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: Any) -> Any:
        if isinstance(value, dict):
            nullable_fields = {
                field_name
                for field_name in ("name", "domain", "description")
                if field_name in value and value[field_name] is None
            }
            if nullable_fields:
                fields = ", ".join(sorted(nullable_fields))
                raise ValueError(f"Project metadata fields cannot be null: {fields}")
        return value
