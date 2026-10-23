"""Schemas for Jira Cloud OAuth 2.0 (3LO) integration and resource discovery."""

from datetime import datetime
from typing import Any, Literal

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
# Issue Types & Sync Preview Schemas
# ---------------------------------------------------------------------------


class JiraIssueTypeResponse(BaseModel):
    """Normalized safe metadata for a Jira issue type."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    subtask: bool = False
    hierarchy_level: int = 0


class JiraPreviewTarget(BaseModel):
    """Target Jira environment for synchronization preview."""

    model_config = ConfigDict(extra="forbid")

    site: JiraContextSite
    project: JiraContextProject
    board: JiraContextBoard


class JiraPreviewSprint(BaseModel):
    """Sprint details included in the synchronization preview."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    planned_points: int = 0
    duration_days: int = 14
    start_date: str | None = None
    end_date: str | None = None
    item_count: int = 0


class JiraPreviewIssue(BaseModel):
    """Deterministic preview issue preserving AgileFlow artifact identifiers."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    agileflow_type: Literal["EPIC", "FEATURE", "USER_STORY", "TASK"]
    jira_issue_type: str
    summary: str
    parent_id: str | None = None
    planned_sprint: str | None = None
    assignee: None = None
    priority: str | None = None
    estimate_points: int | None = None


class JiraPreviewSummary(BaseModel):
    """Aggregate metric counts for synchronization preview."""

    model_config = ConfigDict(extra="forbid")

    total_issues: int
    total_sprints: int
    epic_count: int
    feature_count: int
    story_count: int
    task_count: int
    total_points: int = 0


class JiraPreviewResponse(BaseModel):
    """Deterministic Jira synchronization preview response.

    Guarantees synchronization_status is strictly NOT_PERFORMED and zero Jira
    data has been written or modified.
    """

    model_config = ConfigDict(extra="forbid")

    target: JiraPreviewTarget
    mappings: dict[str, str]
    sprints: list[JiraPreviewSprint]
    issues: list[JiraPreviewIssue]
    summary: JiraPreviewSummary
    warnings: list[str] = Field(default_factory=list)
    synchronization_status: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"


class JiraSyncPreviewRequest(BaseModel):
    """Request payload to generate a deterministic Jira sync preview."""

    model_config = ConfigDict(extra="forbid")

    agent_project_id: str = Field(min_length=1)
    run_id: str | None = None
    mappings: dict[str, str] = Field(min_length=1)
    outputs: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Synchronization Execution & Traceability Schemas
# ---------------------------------------------------------------------------


class JiraSprintTrace(BaseModel):
    """Traceability mapping for an individual Jira sprint created or reused."""

    model_config = ConfigDict(extra="forbid")

    agileflow_sprint_id: str
    jira_sprint_id: int
    name: str
    state: str = "future"
    reused: bool = False
    created_at: datetime


class JiraIssueTrace(BaseModel):
    """Traceability mapping for an individual Jira issue created or reused."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    agileflow_type: Literal["EPIC", "FEATURE", "USER_STORY", "TASK"]
    jira_id: str
    jira_key: str
    jira_issue_type: str
    summary: str
    parent_id: str | None = None
    parent_jira_key: str | None = None
    planned_sprint: str | None = None
    jira_sprint_id: int | None = None
    browse_url: str | None = None
    reused: bool = False
    created_at: datetime


class JiraSyncFailure(BaseModel):
    """Records a failure for a specific sprint, issue, or placement."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["SPRINT", "ISSUE", "PLACEMENT"]
    entity_id: str
    error: str


class JiraSyncCounts(BaseModel):
    """Progress counts for a synchronization operation."""

    model_config = ConfigDict(extra="forbid")

    planned: int = 0
    created: int = 0
    reused: int = 0
    failed: int = 0


class JiraSyncDocument(BaseModel):
    """Persistence model for Jira synchronization records and full traceability."""

    model_config = ConfigDict(extra="forbid")

    sync_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    agent_project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    cloud_id: str
    site_name: str
    site_url: str | None = None
    project_id: str
    project_key: str
    project_name: str
    board_id: int
    board_name: str
    mappings: dict[str, str]
    status: Literal["NOT_PERFORMED", "IN_PROGRESS", "PARTIAL", "COMPLETED", "FAILED"]
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    sprint_summary: JiraSyncCounts
    issue_summary: JiraSyncCounts
    placement_summary: JiraSyncCounts
    sprints_trace: dict[str, JiraSprintTrace] = Field(default_factory=dict)
    issues_trace: dict[str, JiraIssueTrace] = Field(default_factory=dict)
    placements_trace: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[JiraSyncFailure] = Field(default_factory=list)


class JiraSyncExecuteRequest(BaseModel):
    """Request payload to initiate or resume Jira synchronization."""

    model_config = ConfigDict(extra="forbid")

    agent_project_id: str = Field(min_length=1)
    run_id: str | None = None
    mappings: dict[str, str] = Field(min_length=1)
    confirmation: bool = Field(default=False)
    outputs: dict[str, Any] | None = None


class JiraSyncResultResponse(BaseModel):
    """Safe synchronization result response containing summaries and browseable traceability."""

    model_config = ConfigDict(extra="forbid")

    sync_id: str
    status: Literal["NOT_PERFORMED", "IN_PROGRESS", "PARTIAL", "COMPLETED", "FAILED"]
    target: JiraPreviewTarget
    sprint_summary: JiraSyncCounts
    issue_summary: JiraSyncCounts
    placement_summary: JiraSyncCounts
    traceability: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    failures: list[JiraSyncFailure] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None


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
