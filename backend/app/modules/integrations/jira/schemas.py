"""Schemas for Jira Cloud OAuth 2.0 (3LO) integration."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JiraStatusResponse(BaseModel):
    """Safe public representation of Jira connection status.

    Never exposes access tokens, refresh tokens, client secrets, or codes.
    """

    model_config = ConfigDict(extra="forbid")

    connected: bool
    connected_at: datetime | None = None
    expires_at: datetime | None = None


class JiraConnectResponse(BaseModel):
    """Response containing the constructed Atlassian authorization URL."""

    model_config = ConfigDict(extra="forbid")

    authorization_url: str = Field(min_length=1)


class JiraDisconnectResponse(BaseModel):
    """Response indicating the AgileFlow-side Jira connection was removed."""

    model_config = ConfigDict(extra="forbid")

    disconnected: bool = True
    message: str = "Jira connection removed successfully"


class JiraConnectionDocument(BaseModel):
    """Internal persistence model for storing Jira OAuth credentials.

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
