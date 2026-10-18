from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.agents.implementation.contracts.enums import (
    GitHubRepositoryVisibility,
    ImplementationArtifactType,
    ImplementationInputSourceType,
    ImplementationOutputCode,
)


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


class GitHubRepositoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=350)
    visibility: GitHubRepositoryVisibility

    @field_validator("name")
    @classmethod
    def validate_repository_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("repository name is required")
        if normalized in {".", ".."}:
            raise ValueError("repository name cannot be a path segment")
        if any(character.isspace() or ord(character) < 32 for character in normalized):
            raise ValueError("repository name cannot contain whitespace or control characters")
        if any(character in normalized for character in ("/", "\\")):
            raise ValueError("repository name only is required, not an owner or path")
        if "://" in normalized or normalized.lower().startswith("github.com"):
            raise ValueError("repository name cannot be a URL")
        if not all(
            character.isascii()
            and (character.isalnum() or character in {"-", "_", "."})
            for character in normalized
        ):
            raise ValueError(
                "repository name may contain only letters, numbers, hyphens, underscores, and periods"
            )
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class GitHubRepositoryBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_project_id: str = Field(pattern=r"^AGP-\d{3,}$")
    owner_id: str = Field(pattern=r"^USR-\d{3,}$")
    github_connection_owner_id: str = Field(pattern=r"^USR-\d{3,}$")
    repository_id: int = Field(gt=0)
    repository_owner: str = Field(min_length=1)
    repository_name: str = Field(min_length=1, max_length=100)
    repository_full_name: str = Field(min_length=3)
    repository_html_url: str = Field(pattern=r"^https?://")
    visibility: GitHubRepositoryVisibility
    private: bool
    default_branch: str | None = None
    is_empty: Literal[True] = True
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_visibility(self) -> "GitHubRepositoryBinding":
        if self.private is not (self.visibility is GitHubRepositoryVisibility.PRIVATE):
            raise ValueError("repository visibility and private flag must agree")
        if self.github_connection_owner_id != self.owner_id:
            raise ValueError("repository binding must use the project owner's connection")
        return self


class GitHubRepositoryStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: bool
    repository_id: int | None = None
    owner: str | None = None
    name: str | None = None
    full_name: str | None = None
    html_url: str | None = None
    visibility: GitHubRepositoryVisibility | None = None
    private: bool | None = None
    default_branch: str | None = None
    is_empty: bool | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def validate_created_fields(self) -> "GitHubRepositoryStatus":
        required = (
            self.repository_id,
            self.owner,
            self.name,
            self.full_name,
            self.html_url,
            self.visibility,
            self.private,
            self.is_empty,
            self.created_at,
        )
        details = (*required, self.default_branch)
        if self.created and any(value is None for value in required):
            raise ValueError("created repository status requires repository metadata")
        if not self.created and any(value is not None for value in details):
            raise ValueError("uncreated repository status cannot contain metadata")
        return self

    @classmethod
    def from_binding(
        cls, binding: GitHubRepositoryBinding
    ) -> "GitHubRepositoryStatus":
        return cls(
            created=True,
            repository_id=binding.repository_id,
            owner=binding.repository_owner,
            name=binding.repository_name,
            full_name=binding.repository_full_name,
            html_url=binding.repository_html_url,
            visibility=binding.visibility,
            private=binding.private,
            default_branch=binding.default_branch,
            is_empty=binding.is_empty,
            created_at=binding.created_at,
        )


Agent3InputSourceFormat = ImplementationInputSourceType
Agent3ArtifactType = ImplementationArtifactType
Agent3OutputCode = ImplementationOutputCode
Agent3Input = ImplementationInput
