from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.status import AgentRunMode, AgentRunStatus, AgentType
from app.modules.standalone.schemas import AgentRunMessage
from app.modules.agents.testing_validation.contracts.enums import (
    TestGenerationOutputCode,
    ValidationOutputCode,
)
from app.modules.agents.testing_validation.contracts.schemas import (
    TEST_OUTPUT_MODELS,
    GeneratedTestCase,
    TestTraceabilityItem,
)
from app.modules.agents.testing_validation.executor import (
    CommandPolicyError,
    ValidationProfile,
    resolve_validation_profile,
)

# Compatibility re-exports: these names moved to the contracts/ package.
# New code should import from app.modules.agents.testing_validation.contracts.
__all__ = [
    "Agent4InputContext",
    "Agent4RunRequest",
    "Agent4RunResult",
    "GeneratedTestCase",
    "TEST_OUTPUT_MODELS",
    "TestGenerationOutputCode",
    "TestTraceabilityItem",
    "ValidationOutputCode",
]


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class Agent4RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_mode: AgentRunMode
    selected_outputs: list[str] = Field(min_length=1)
    requirements: str | None = None
    user_stories: str | None = None
    acceptance_criteria: str | None = None
    srs: str | None = Field(default=None, alias="SRS")
    system_architecture: str | None = None
    api_specification: str | None = None
    database_schema: str | None = None
    ui_specification: str | None = None
    existing_source_code: str | None = None
    technology_stack: str | None = None
    source_code_or_project: str | dict[str, str] | None = None
    test_cases: str | None = None
    validation_profile: ValidationProfile | None = None
    build_command: str | None = None
    run_command: str | None = None
    environment_information: str | None = None

    @field_validator(
        "requirements", "user_stories", "acceptance_criteria", "srs",
        "system_architecture", "api_specification", "database_schema",
        "ui_specification", "existing_source_code", "technology_stack",
        "test_cases", "build_command", "run_command", "environment_information",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("source_code_or_project")
    @classmethod
    def validate_source(cls, value: str | dict[str, str] | None):
        if isinstance(value, str):
            return _strip_optional(value)
        if isinstance(value, dict):
            if not value:
                raise ValueError("source_code_or_project must not be empty")
            if any(not path.strip() or not isinstance(content, str) for path, content in value.items()):
                raise ValueError("source_code_or_project files require nonblank paths and text content")
        return value

    @field_validator("selected_outputs")
    @classmethod
    def validate_outputs(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("selected_outputs must not contain duplicates")
        return values

    @model_validator(mode="after")
    def validate_mode_contract(self) -> "Agent4RunRequest":
        if self.run_mode is AgentRunMode.DEFAULT:
            raise ValueError("Agent 4 requires TEST_GENERATION or VALIDATION run_mode")
        if self.run_mode not in {AgentRunMode.TEST_GENERATION, AgentRunMode.VALIDATION}:
            raise ValueError("run_mode must be TEST_GENERATION or VALIDATION")

        if self.run_mode is AgentRunMode.TEST_GENERATION:
            if not any((self.requirements, self.user_stories, self.acceptance_criteria, self.srs)):
                raise ValueError(
                    "TEST_GENERATION requires at least one of requirements, user_stories, acceptance_criteria, or SRS"
                )
            allowed = {item.value for item in TestGenerationOutputCode}
            forbidden_fields = (self.source_code_or_project, self.test_cases, self.build_command, self.run_command, self.environment_information)
            forbidden_fields += (self.validation_profile,)
            if any(value is not None for value in forbidden_fields):
                raise ValueError("VALIDATION-only inputs are not accepted in TEST_GENERATION mode")
        else:
            if self.source_code_or_project is None:
                raise ValueError("VALIDATION requires source_code_or_project")
            allowed = {item.value for item in ValidationOutputCode}
            generation_only = (
                self.user_stories, self.srs, self.system_architecture,
                self.api_specification, self.database_schema,
                self.ui_specification, self.existing_source_code,
            )
            if any(value is not None for value in generation_only):
                raise ValueError(
                    "TEST_GENERATION-only inputs are not accepted in VALIDATION mode; use source_code_or_project for implementation content"
                )
            if "ACCEPTANCE_CRITERIA_VALIDATION" in self.selected_outputs and not self.acceptance_criteria:
                raise ValueError("acceptance_criteria is required for ACCEPTANCE_CRITERIA_VALIDATION")
            try:
                resolve_validation_profile(
                    self.validation_profile, self.build_command, self.run_command
                )
            except CommandPolicyError as exc:
                raise ValueError(str(exc)) from exc

        invalid = sorted(set(self.selected_outputs) - allowed)
        if invalid:
            raise ValueError(
                f"selected_outputs are not valid for {self.run_mode.value}: {', '.join(invalid)}"
            )
        return self


class Agent4InputContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    run_mode: Literal[AgentRunMode.TEST_GENERATION, AgentRunMode.VALIDATION]
    inputs: dict[str, Any]


class Agent4RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    agent_project_id: str
    agent_type: AgentType
    run_mode: AgentRunMode
    status: AgentRunStatus
    selected_outputs: list[str]
    started_at: datetime | None
    completed_at: datetime | None
    outputs: dict[str, Any]
    warnings: list[AgentRunMessage]
    errors: list[AgentRunMessage]
