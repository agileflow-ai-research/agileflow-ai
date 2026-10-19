from datetime import datetime
from types import MappingProxyType
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.common.id_generator import validate_id
from app.common.status import (
    AgentProjectStatus,
    AgentRunMode,
    AgentRunStatus,
    AgentType,
)


ALLOWED_RUN_MODES = MappingProxyType(
    {
        AgentType.REQUIREMENTS: frozenset(
            {AgentRunMode.DEFAULT, AgentRunMode.REFINEMENT}
        ),
        AgentType.DESIGN_PLANNING: frozenset({AgentRunMode.DEFAULT}),
        AgentType.IMPLEMENTATION: frozenset({AgentRunMode.DEFAULT}),
        AgentType.TESTING_VALIDATION: frozenset(
            {AgentRunMode.TEST_GENERATION, AgentRunMode.VALIDATION}
        ),
    }
)


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _require_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


class AgentProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_type: AgentType
    name: str
    domain: str
    description: str = ""

    _validate_name = field_validator("name")(_require_nonblank)
    _validate_domain = field_validator("domain")(_require_nonblank)


class AgentProjectUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    domain: str | None = None
    status: AgentProjectStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: Any) -> Any:
        if isinstance(value, dict):
            null_fields = sorted(
                field_name
                for field_name in cls.model_fields
                if field_name in value and value[field_name] is None
            )
            if null_fields:
                raise ValueError(
                    "Agent project fields cannot be null: "
                    + ", ".join(null_fields)
                )
        return value

    _validate_name = field_validator("name")(_require_nonblank)
    _validate_domain = field_validator("domain")(_require_nonblank)


class AgentProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_project_id: str
    owner_user_id: str
    agent_type: AgentType
    name: str
    description: str = ""
    domain: str
    status: AgentProjectStatus = AgentProjectStatus.ACTIVE
    created_at: datetime
    updated_at: datetime

    _validate_name = field_validator("name")(_require_nonblank)
    _validate_domain = field_validator("domain")(_require_nonblank)
    _validate_created_at = field_validator("created_at")(_require_utc_aware)
    _validate_updated_at = field_validator("updated_at")(_require_utc_aware)

    @field_validator("agent_project_id")
    @classmethod
    def validate_agent_project_id(cls, value: str) -> str:
        return validate_id(value, "AGP")

    @field_validator("owner_user_id")
    @classmethod
    def validate_owner_user_id(cls, value: str) -> str:
        return validate_id(value, "USR")

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> "AgentProject":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        return self


class AgentRunMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, JsonValue] | None = None

    _validate_code = field_validator("code")(_require_nonblank)
    _validate_message = field_validator("message")(_require_nonblank)


class AgentRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_project_id: str
    owner_user_id: str
    agent_type: AgentType
    run_mode: AgentRunMode
    selected_outputs: list[str] = Field(min_length=1)
    input_snapshot: dict[str, JsonValue]
    status: AgentRunStatus = AgentRunStatus.QUEUED
    output_manifest: dict[str, JsonValue] = Field(default_factory=dict)
    warnings: list[AgentRunMessage] = Field(default_factory=list)
    errors: list[AgentRunMessage] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    _validate_created_at = field_validator("created_at")(_require_utc_aware)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_optional_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return _require_utc_aware(value) if value is not None else None

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_id(value, "RUN")

    @field_validator("agent_project_id")
    @classmethod
    def validate_agent_project_id(cls, value: str) -> str:
        return validate_id(value, "AGP")

    @field_validator("owner_user_id")
    @classmethod
    def validate_owner_user_id(cls, value: str) -> str:
        return validate_id(value, "USR")

    @field_validator("selected_outputs")
    @classmethod
    def validate_selected_outputs(cls, values: list[str]) -> list[str]:
        for value in values:
            _require_nonblank(value)
        return values

    @model_validator(mode="after")
    def validate_lifecycle_timestamps(self) -> "AgentRun":
        if self.run_mode not in ALLOWED_RUN_MODES[self.agent_type]:
            raise ValueError(
                f"{self.run_mode.value} is not valid for "
                f"{self.agent_type.value}"
            )
        if self.status is AgentRunStatus.QUEUED:
            if self.started_at is not None or self.completed_at is not None:
                raise ValueError("QUEUED runs cannot have execution timestamps")
        elif self.status is AgentRunStatus.RUNNING:
            if self.started_at is None or self.completed_at is not None:
                raise ValueError(
                    "RUNNING runs require started_at and no completed_at"
                )
        else:
            if self.started_at is None or self.completed_at is None:
                raise ValueError(
                    "terminal runs require started_at and completed_at"
                )

        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at must not be earlier than created_at")
        if (
            self.completed_at is not None
            and self.started_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not be earlier than started_at")
        if self.status is AgentRunStatus.FAILED and not self.errors:
            raise ValueError("FAILED runs require at least one error")
        return self
