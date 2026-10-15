from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ImplementationInputSourceType(StrEnum):
    TEXT = "TEXT"
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"


class ImplementationArtifactType(StrEnum):
    SRS = "SRS"

    FUNCTIONAL_REQUIREMENTS = "FUNCTIONAL_REQUIREMENTS"
    NON_FUNCTIONAL_REQUIREMENTS = "NON_FUNCTIONAL_REQUIREMENTS"
    USER_STORIES = "USER_STORIES"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"

    SYSTEM_ARCHITECTURE = "SYSTEM_ARCHITECTURE"
    UML_DIAGRAMS = "UML_DIAGRAMS"
    DATABASE_SCHEMA = "DATABASE_SCHEMA"
    API_SPECIFICATION = "API_SPECIFICATION"
    UI_WIREFRAMES = "UI_WIREFRAMES"
    UI_FLOW = "UI_FLOW"

    IMPLEMENTATION_TASKS = "IMPLEMENTATION_TASKS"
    PRODUCT_BACKLOG = "PRODUCT_BACKLOG"
    TECHNICAL_CONSTRAINTS = "TECHNICAL_CONSTRAINTS"
    TECHNOLOGY_STACK = "TECHNOLOGY_STACK"

    UNIT_TEST_CASES = "UNIT_TEST_CASES"
    API_TEST_CASES = "API_TEST_CASES"
    INTEGRATION_TEST_CASES = "INTEGRATION_TEST_CASES"
    FUNCTIONAL_TEST_CASES = "FUNCTIONAL_TEST_CASES"
    E2E_TEST_CASES = "E2E_TEST_CASES"
    SECURITY_TEST_CASES = "SECURITY_TEST_CASES"
    ACCEPTANCE_TEST_CASES = "ACCEPTANCE_TEST_CASES"
    TEST_TRACEABILITY = "TEST_TRACEABILITY"


class ImplementationOutputCode(StrEnum):
    PROJECT_STRUCTURE = "PROJECT_STRUCTURE"
    FRONTEND_CODE = "FRONTEND_CODE"
    BACKEND_CODE = "BACKEND_CODE"
    DATABASE_IMPLEMENTATION = "DATABASE_IMPLEMENTATION"
    API_IMPLEMENTATION = "API_IMPLEMENTATION"
    CONFIGURATION_FILES = "CONFIGURATION_FILES"
    CONTAINER_CONFIGURATION = "CONTAINER_CONFIGURATION"
    GIT_SUMMARY = "GIT_SUMMARY"


class ImplementationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: ImplementationInputSourceType
    artifact_type: ImplementationArtifactType
    content: str
    label: str | None = None

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must be non-empty")
        return normalized

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_supported_source(self) -> "ImplementationInput":
        if self.source_type is not ImplementationInputSourceType.TEXT:
            raise ValueError(
                "only TEXT inputs are supported in Step 1A; document and image uploads are not available"
            )
        return self


class Agent3WorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: list[ImplementationInput] = Field(min_length=1)
    selected_outputs: list[ImplementationOutputCode] = Field(min_length=1)

    @field_validator("selected_outputs")
    @classmethod
    def reject_duplicate_outputs(
        cls, values: list[ImplementationOutputCode]
    ) -> list[ImplementationOutputCode]:
        if len(values) != len(set(values)):
            raise ValueError("selected_outputs must not contain duplicates")
        return values


# Agent-number aliases keep the public schema vocabulary easy to discover while
# the implementation-prefixed names remain consistent with the feature package.
Agent3InputSourceFormat = ImplementationInputSourceType
Agent3ArtifactType = ImplementationArtifactType
Agent3OutputCode = ImplementationOutputCode
Agent3Input = ImplementationInput
