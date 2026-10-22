"""Schemas for Jira Cloud OAuth 2.0 (3LO) integration and resource discovery."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JiraStatusResponse(BaseModel):
    """Safe public representation of Jira connection status.

    Never exposes access tokens, refresh tokens, client secrets, or codes.
    """

    model_config = ConfigDict(extra="forbid")

    connected: bool
    connected_at: datetime | None = None
    expires_at: datetime | None = None
    reauthorization_required: bool | None = None


class JiraConnectResponse(BaseModel):
    """Response containing the constructed Atlassian authorization URL."""

    model_config = ConfigDict(extra="forbid")

    authorization_url: str = Field(min_length=1)


class JiraDisconnectResponse(BaseModel):
    """Response indicating the AgileFlow-side Jira connection was removed."""

    model_config = ConfigDict(extra="forbid")

    disconnected: bool = True
    message: str = "Jira connection removed successfully"


class AtlassianAccessibleResource(BaseModel):
    """Normalized internal representation of an accessible Atlassian Cloud resource.

    Obtained from GET https://api.atlassian.com/oauth/token/accessible-resources.
    Contains only safe resource metadata without credentials.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Atlassian Cloud Site ID (cloudId)")
    name: str = Field(description="Display name of the site")
    url: str = Field(description="Canonical URL of the site")
    scopes: list[str] = Field(
        default_factory=list, description="Scopes authorized for this resource"
    )
    avatar_url: str | None = Field(
        default=None, description="Site avatar image URL if available"
    )


# ---------------------------------------------------------------------------
# Site Discovery & Selection Schemas
# ---------------------------------------------------------------------------


class JiraSiteResponse(BaseModel):
    """Normalized representation of an accessible Jira site."""

    model_config = ConfigDict(extra="forbid")

    cloud_id: str
    name: str
    url: str
    avatar_url: str | None = None


class JiraSelectSiteRequest(BaseModel):
    """Request payload to select a Jira Cloud site."""

    model_config = ConfigDict(extra="forbid")

    cloud_id: str = Field(min_length=1)


class JiraSelectedSite(BaseModel):
    """Persisted metadata for the selected Jira Cloud site."""

    model_config = ConfigDict(extra="forbid")

    cloud_id: str
    site_name: str
    site_url: str | None = None
    avatar_url: str | None = None
    selected_at: datetime


# ---------------------------------------------------------------------------
# Project Discovery & Selection Schemas
# ---------------------------------------------------------------------------


class JiraProjectResponse(BaseModel):
    """Normalized representation of an accessible Jira Software project."""

    model_config = ConfigDict(extra="forbid")

    id: str
    key: str
    name: str
    project_type_key: str
    simplified: bool = False
    avatar_url: str | None = None


class JiraSelectProjectRequest(BaseModel):
    """Request payload to select an accessible Jira project."""

    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None
    project_key: str | None = None

    @model_validator(mode="after")
    def validate_identifier_present(self) -> "JiraSelectProjectRequest":
        if not self.project_id and not self.project_key:
            raise ValueError("Either project_id or project_key must be provided")
        return self


class JiraSelectedProject(BaseModel):
    """Persisted metadata for the selected Jira project."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    project_key: str
    project_name: str
    project_type_key: str
    selected_at: datetime


# ---------------------------------------------------------------------------
# Scrum Board Discovery & Selection Schemas
# ---------------------------------------------------------------------------


class JiraBoardResponse(BaseModel):
    """Normalized representation of an accessible Scrum board."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    type: str = "scrum"


class JiraSelectBoardRequest(BaseModel):
    """Request payload to select a Scrum board."""

    model_config = ConfigDict(extra="forbid")

    board_id: int = Field(gt=0)


class JiraSelectedBoard(BaseModel):
    """Persisted metadata for the selected Scrum board."""

    model_config = ConfigDict(extra="forbid")

    board_id: int
    board_name: str
    board_type: str = "scrum"
    selected_at: datetime


# ---------------------------------------------------------------------------
# Jira Context Schemas
# ---------------------------------------------------------------------------


class JiraContextSite(BaseModel):
    """Safe site information in the current Jira context."""

    model_config = ConfigDict(extra="forbid")

    cloud_id: str
    name: str
    url: str | None = None


class JiraContextProject(BaseModel):
    """Safe project information in the current Jira context."""

    model_config = ConfigDict(extra="forbid")

    id: str
    key: str
    name: str


class JiraContextBoard(BaseModel):
    """Safe board information in the current Jira context."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    type: str = "scrum"


class JiraContextResponse(BaseModel):
    """Current Jira connection and selection state."""

    model_config = ConfigDict(extra="forbid")

    connected: bool
    site: JiraContextSite | None = None
    project: JiraContextProject | None = None
    board: JiraContextBoard | None = None


# ---------------------------------------------------------------------------
# Internal Database Model
# ---------------------------------------------------------------------------


class JiraConnectionDocument(BaseModel):
    """Internal persistence model for storing Jira OAuth credentials and discovery context.

    NOTE ON TOKEN STORAGE SECURITY:
    Tokens are stored at rest in the database. At present, the repository lacks
    an enterprise token encryption / key-management service (e.g. AWS KMS,
    HashiCorp Vault, or envelope encryption). As an explicit security requirement,
    production deployment should integrate transparent field-level encryption for
    access_token and refresh_token fields.
    """

    model_config = ConfigDict(extra="forbid")

    owner_id: str = Field(pattern=r"^USR-\d{3,}$")
    provider: Literal["JIRA"] = "JIRA"
    access_token: str = Field(min_length=1)
    refresh_token: str | None = None
    expires_at: datetime
    connected_at: datetime
    updated_at: datetime
    scope: str
    token_type: str = "Bearer"
    status: Literal["CONNECTED", "REAUTHORIZATION_REQUIRED"] = "CONNECTED"
    reauthorization_reason: str | None = None
    version: int = 1

    selected_site: JiraSelectedSite | None = None
    selected_project: JiraSelectedProject | None = None
    selected_board: JiraSelectedBoard | None = None
