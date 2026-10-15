from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

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


class UploadedFileMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str = Field(pattern=r"^A3UP-[0-9a-f]{32}$")
    source_type: Literal[
        ImplementationInputSourceType.DOCUMENT,
        ImplementationInputSourceType.IMAGE,
    ]
    artifact_type: ImplementationArtifactType
    label: str | None = Field(default=None, max_length=200)
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1)
    extension: str = Field(pattern=r"^\.[a-z0-9]+$")
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class _ImplementationInputBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_type: ImplementationArtifactType
    label: str | None = Field(default=None, max_length=200)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class TextImplementationInput(_ImplementationInputBase):
    source_type: Literal[ImplementationInputSourceType.TEXT]
    content: str

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must be non-empty")
        return normalized


class DocumentImplementationInput(_ImplementationInputBase):
    source_type: Literal[ImplementationInputSourceType.DOCUMENT]
    file: UploadedFileMetadata

    @model_validator(mode="after")
    def validate_file_reference(self) -> "DocumentImplementationInput":
        if self.file.source_type is not ImplementationInputSourceType.DOCUMENT:
            raise ValueError("DOCUMENT input requires DOCUMENT upload metadata")
        if self.file.artifact_type is not self.artifact_type:
            raise ValueError("artifact_type must match the uploaded file metadata")
        return self


class ImageImplementationInput(_ImplementationInputBase):
    source_type: Literal[ImplementationInputSourceType.IMAGE]
    file: UploadedFileMetadata

    @model_validator(mode="after")
    def validate_file_reference(self) -> "ImageImplementationInput":
        if self.file.source_type is not ImplementationInputSourceType.IMAGE:
            raise ValueError("IMAGE input requires IMAGE upload metadata")
        if self.file.artifact_type is not self.artifact_type:
            raise ValueError("artifact_type must match the uploaded file metadata")
        return self


ImplementationInput = Annotated[
    TextImplementationInput
    | DocumentImplementationInput
    | ImageImplementationInput,
    Field(discriminator="source_type"),
]


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


class GitHubConnectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installation_url: str = Field(min_length=1)
    expires_at: datetime


class GitHubConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_id: str = Field(pattern=r"^USR-\d{3,}$")
    provider: Literal["GITHUB"] = "GITHUB"
    github_user_id: int = Field(gt=0)
    github_login: str = Field(min_length=1)
    github_avatar_url: str | None = None
    installation_id: int = Field(gt=0)
    installation_account_id: int = Field(gt=0)
    installation_account_login: str = Field(min_length=1)
    installation_account_type: Literal["User"]
    status: Literal["CONNECTED"] = "CONNECTED"
    connected_at: datetime
    updated_at: datetime


class GitHubConnectionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connected: bool
    github_user_id: int | None = None
    github_login: str | None = None
    avatar_url: str | None = None
    installation_id: int | None = None
    account_type: Literal["User"] | None = None

    @model_validator(mode="after")
    def validate_connected_fields(self) -> "GitHubConnectionStatus":
        required_details = (
            self.github_user_id,
            self.github_login,
            self.installation_id,
            self.account_type,
        )
        all_details = (*required_details, self.avatar_url)
        if self.connected and any(value is None for value in required_details):
            raise ValueError("connected GitHub status requires account metadata")
        if not self.connected and any(value is not None for value in all_details):
            raise ValueError("disconnected GitHub status cannot contain account metadata")
        return self


Agent3InputSourceFormat = ImplementationInputSourceType
Agent3ArtifactType = ImplementationArtifactType
Agent3OutputCode = ImplementationOutputCode
Agent3Input = ImplementationInput
