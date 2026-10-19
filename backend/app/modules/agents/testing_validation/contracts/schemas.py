"""Contract-level result models shared by Mode A and the rebuilt Agent 4 pipeline."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.testing_validation.contracts.enums import (
    TestExecutionStatus,
    TestGenerationOutputCode,
    TestRepresentation,
)


class GeneratedTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^TEST-\d{3,}$")
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    preconditions: list[str]
    test_data: list[str]
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    representation: TestRepresentation
    executable: bool
    framework: str | None
    code: str | None
    execution_status: TestExecutionStatus = TestExecutionStatus.NOT_EXECUTED

    @model_validator(mode="after")
    def validate_representation(self) -> "GeneratedTestCase":
        is_executable_code = self.representation is TestRepresentation.EXECUTABLE_CODE
        if self.executable != is_executable_code:
            raise ValueError("executable must match representation")
        if self.executable and (not self.framework or not self.code):
            raise ValueError("executable tests require framework and code")
        if not self.executable and (self.framework is not None or self.code is not None):
            raise ValueError("specification-only tests cannot claim framework or code")
        return self


class TestTraceabilityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_ref: str = Field(min_length=1)
    source_type: Literal["REQUIREMENT", "USER_STORY", "ACCEPTANCE_CRITERION", "SRS"]
    test_refs: list[str] = Field(min_length=1)
    scope: Literal["STANDALONE_RESULT"] = "STANDALONE_RESULT"


TEST_OUTPUT_MODELS: dict[TestGenerationOutputCode, Any] = {
    **{code: list[GeneratedTestCase] for code in TestGenerationOutputCode if code is not TestGenerationOutputCode.TEST_TRACEABILITY},
    TestGenerationOutputCode.TEST_TRACEABILITY: list[TestTraceabilityItem],
}
