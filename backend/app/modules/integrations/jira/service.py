"""Service and state-management layer for Jira Cloud OAuth 2.0 (3LO)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets
from threading import Lock
from typing import Any
from urllib.parse import urlencode

import uuid

import httpx

from app.common.status import AgentRunStatus
from app.core.config import Settings
from app.modules.auth.schemas import UserPublicResponse
from app.modules.integrations.jira.constants import (
    ATLASSIAN_AUDIENCE,
    ATLASSIAN_AUTHORIZE_URL,
    ATLASSIAN_TOKEN_URL,
    DEFAULT_STATE_TTL_SECONDS,
    JIRA_SCOPES,
    MAX_PENDING_STATES,
    REFRESH_SAFETY_MARGIN_SECONDS,
)
from app.modules.integrations.jira.repository import (
    JiraConnectionRepository,
    JiraSyncRepository,
)
from app.modules.integrations.jira.schemas import (
    AtlassianAccessibleResource,
    JiraBoardResponse,
    JiraConnectResponse,
    JiraConnectionDocument,
    JiraContextBoard,
    JiraContextProject,
    JiraContextResponse,
    JiraContextSite,
    JiraIssueTrace,
    JiraIssueTypeResponse,
    JiraPreviewIssue,
    JiraPreviewResponse,
    JiraPreviewSprint,
    JiraPreviewSummary,
    JiraPreviewTarget,
    JiraProjectResponse,
    JiraSelectedBoard,
    JiraSelectedProject,
    JiraSelectedSite,
    JiraSiteResponse,
    JiraSprintTrace,
    JiraStatusResponse,
    JiraSyncCounts,
    JiraSyncDocument,
    JiraSyncExecuteRequest,
    JiraSyncFailure,
    JiraSyncPreviewRequest,
    JiraSyncResultResponse,
)


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone information."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class JiraConfiguration:
    """Strongly-typed, validated Jira OAuth configuration.

    Guarantees secrets are not printed or exposed in logs.
    """

    client_id: str
    client_secret: str
    redirect_uri: str
    frontend_return_url: str
    timeout_seconds: float = 10.0

    def __repr__(self) -> str:
        return (
            f"JiraConfiguration(client_id='{self.client_id}', "
            f"client_secret='***', redirect_uri='{self.redirect_uri}', "
            f"frontend_return_url='{self.frontend_return_url}')"
        )

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_settings(cls, settings: Settings) -> "JiraConfiguration":
        if not settings.jira_client_id or not settings.jira_client_secret:
            raise JiraConfigurationError(
                "Jira Cloud OAuth client credentials are not configured"
            )
        return cls(
            client_id=settings.jira_client_id.strip(),
            client_secret=settings.jira_client_secret.strip(),
            redirect_uri=settings.jira_redirect_uri.strip(),
            frontend_return_url=settings.jira_frontend_return_url.strip(),
            timeout_seconds=settings.jira_http_timeout_seconds,
        )


@dataclass(frozen=True)
class PendingJiraOAuthState:
    """Server-side record binding an OAuth state to an authenticated user."""

    state: str
    user_id: str
    created_at: datetime
    expires_at: datetime


# ---------------------------------------------------------------------------
# Exception Hierarchy
# ---------------------------------------------------------------------------


class JiraIntegrationError(RuntimeError):
    """Base exception for normalized Jira integration errors."""

    error_code: str = "JIRA_INTEGRATION_ERROR"


class JiraConfigurationError(JiraIntegrationError):
    """Raised when required Jira OAuth settings are missing."""

    error_code: str = "JIRA_CONFIGURATION_ERROR"


class JiraNotConnectedError(JiraIntegrationError):
    """Raised when a user attempts a Jira operation without an active connection."""

    error_code: str = "JIRA_NOT_CONNECTED"


class JiraReauthorizationRequiredError(JiraIntegrationError):
    """Raised when a user's Jira connection has an expired/revoked refresh token and requires reconnection."""

    error_code: str = "JIRA_REAUTHORIZATION_REQUIRED"


class JiraStateError(ValueError):
    """Base exception for OAuth state validation errors."""


class JiraStateInvalidError(JiraStateError):
    """Raised when an OAuth state is unknown or malformed."""


class JiraStateExpiredError(JiraStateError):
    """Raised when an OAuth state has exceeded its TTL."""


class JiraStateReusedError(JiraStateError):
    """Raised when an OAuth state has already been consumed (replay prevention)."""


class JiraCrossUserStateError(JiraStateError):
    """Raised when an OAuth state is presented by a different user session."""


class JiraMissingCodeError(ValueError):
    """Raised when an authorization callback is missing an authorization code."""


class JiraOAuthApiError(JiraIntegrationError):
    """Base exception for Atlassian OAuth communication failures."""

    error_code: str = "JIRA_OAUTH_API_ERROR"


class JiraTokenExchangeError(JiraOAuthApiError):
    """Raised when Atlassian rejects the authorization code or returns an error."""

    error_code: str = "JIRA_TOKEN_EXCHANGE_ERROR"


class JiraInvalidGrantError(JiraTokenExchangeError):
    """Raised when Atlassian returns invalid_grant for an authorization code or refresh token."""

    error_code: str = "JIRA_INVALID_GRANT"


class JiraNetworkTimeoutError(JiraOAuthApiError):
    """Raised when communication with Atlassian times out."""

    error_code: str = "JIRA_NETWORK_TIMEOUT"


class JiraNetworkError(JiraOAuthApiError):
    """Raised when a network transport failure occurs connecting to Atlassian."""

    error_code: str = "JIRA_NETWORK_ERROR"


class JiraMalformedResponseError(JiraOAuthApiError):
    """Raised when Atlassian returns non-JSON or invalid payload."""

    error_code: str = "JIRA_MALFORMED_RESPONSE"


class JiraApiClientError(JiraIntegrationError):
    """Base exception for errors returned by Atlassian REST APIs."""

    error_code: str = "JIRA_API_ERROR"


class JiraAuthenticationError(JiraApiClientError):
    """Raised when an API request receives 401 Unauthorized even after token refresh."""

    error_code: str = "JIRA_AUTHENTICATION_ERROR"


class JiraPermissionError(JiraApiClientError):
    """Raised when an API request receives 403 Forbidden."""

    error_code: str = "JIRA_PERMISSION_ERROR"


class JiraResourceNotFoundError(JiraApiClientError):
    """Raised when an Atlassian resource receives 404 Not Found."""

    error_code: str = "JIRA_RESOURCE_NOT_FOUND"


class JiraRateLimitError(JiraApiClientError):
    """Raised when Atlassian API rate limit (429) is encountered."""

    error_code: str = "JIRA_RATE_LIMITED"


class JiraUpstreamError(JiraIntegrationError):
    """Raised when an upstream Atlassian API call fails or encounters an unhandled error."""

    error_code: str = "JIRA_UPSTREAM_ERROR"


class JiraRemoteApiError(JiraApiClientError):
    """Raised when Atlassian returns an unexpected error (e.g. 5xx)."""

    error_code: str = "JIRA_REMOTE_API_ERROR"


class JiraSiteNotSelectedError(JiraIntegrationError):
    """Raised when an operation requires a selected Jira Cloud site."""

    error_code: str = "JIRA_SITE_NOT_SELECTED"


class JiraSiteNotAccessibleError(JiraIntegrationError):
    """Raised when a selected Jira Cloud site is not accessible or not authorized."""

    error_code: str = "JIRA_SITE_NOT_ACCESSIBLE"


class JiraProjectNotSelectedError(JiraIntegrationError):
    """Raised when an operation requires a selected Jira project."""

    error_code: str = "JIRA_PROJECT_NOT_SELECTED"


class JiraProjectNotAccessibleError(JiraIntegrationError):
    """Raised when a selected Jira project is not found or not accessible on the site."""

    error_code: str = "JIRA_PROJECT_NOT_ACCESSIBLE"


class JiraBoardNotAccessibleError(JiraIntegrationError):
    """Raised when a Scrum board is not found or not accessible for the project."""

    error_code: str = "JIRA_BOARD_NOT_ACCESSIBLE"


class JiraBoardNotScrumError(JiraIntegrationError):
    """Raised when a selected board is not a Scrum board."""

    error_code: str = "JIRA_BOARD_NOT_SCRUM"


class JiraBoardNotSelectedError(JiraIntegrationError):
    """Raised when an operation requires a selected Scrum board."""

    error_code: str = "JIRA_BOARD_NOT_SELECTED"


class JiraPlanUnavailableError(JiraIntegrationError):
    """Raised when JIRA_PLAN is not available in the specified Agent 2 run."""

    error_code: str = "JIRA_PLAN_UNAVAILABLE"


class JiraMappingIncompleteError(JiraIntegrationError):
    """Raised when one or more required artifact types lack a Jira issue type mapping."""

    error_code: str = "JIRA_MAPPING_INCOMPLETE"


class JiraIssueTypeUnavailableError(JiraIntegrationError):
    """Raised when a mapped Jira issue type does not exist in the selected Jira project."""

    error_code: str = "JIRA_ISSUE_TYPE_UNAVAILABLE"


class JiraHierarchyInvalidError(JiraIntegrationError):
    """Raised when a required hierarchy reference is broken or invalid."""

    error_code: str = "JIRA_HIERARCHY_INVALID"


class JiraConfirmationRequiredError(JiraIntegrationError):
    """Raised when synchronization execution is attempted without explicit human confirmation."""

    error_code: str = "JIRA_CONFIRMATION_REQUIRED"


class JiraSyncInProgressError(JiraIntegrationError):
    """Raised when a synchronization operation is already active for an approved run."""

    error_code: str = "JIRA_SYNC_IN_PROGRESS"


class JiraRunNotCompletedError(JiraIntegrationError):
    """Raised when attempting to synchronize a run that is not COMPLETED."""

    error_code: str = "JIRA_RUN_NOT_COMPLETED"


class JiraUnauthorizedProjectAccessError(JiraIntegrationError):
    """Raised when an authenticated user attempts to synchronize a project they do not own."""

    error_code: str = "JIRA_UNAUTHORIZED_PROJECT_ACCESS"


def suggest_issue_type_mappings(
    issue_types: list[JiraIssueTypeResponse],
) -> dict[str, str | None]:
    """Auto-suggest unambiguous mappings from AgileFlow to Jira issue types.

    Rules:
    - Epic -> 'Epic' if unambiguous
    - User Story -> 'Story' or 'User Story' if unambiguous
    - Task -> 'Task' if unambiguous
    - Feature -> 'Feature' if exact match, otherwise None (human selection required)
    """
    suggestions: dict[str, str | None] = {
        "EPIC": None,
        "FEATURE": None,
        "USER_STORY": None,
        "TASK": None,
    }

    # Match Epic (standard or epic hierarchy)
    epic_matches = [t.name for t in issue_types if t.name.lower() == "epic"]
    if len(epic_matches) == 1:
        suggestions["EPIC"] = epic_matches[0]

    # Match User Story (non-subtask)
    story_matches = [
        t.name
        for t in issue_types
        if t.name.lower() in ("story", "user story") and not t.subtask
    ]
    if len(story_matches) == 1:
        suggestions["USER_STORY"] = story_matches[0]

    # Match Task (non-subtask)
    task_matches = [
        t.name
        for t in issue_types
        if t.name.lower() == "task" and not t.subtask
    ]
    if len(task_matches) == 1:
        suggestions["TASK"] = task_matches[0]

    # Match Feature (strictly exact non-subtask match; never invented)
    feature_matches = [
        t.name
        for t in issue_types
        if t.name.lower() == "feature" and not t.subtask
    ]
    if len(feature_matches) == 1:
        suggestions["FEATURE"] = feature_matches[0]

    return suggestions


# ---------------------------------------------------------------------------
# Server-side Single-use State Store
# ---------------------------------------------------------------------------


class JiraStateStore:
    """Thread-safe, server-side store for expiring, single-use OAuth states.

    Guarantees:
    - Cryptographic randomness (secrets.token_urlsafe(32))
    - User binding (state is tied to user_id)
    - Expiring (default TTL 10 minutes)
    - Single-use (consumed upon callback, preventing replay)
    - Cross-user usage prevention
    """

    def __init__(
        self,
        *,
        clock=utc_now,
        ttl: timedelta = timedelta(seconds=DEFAULT_STATE_TTL_SECONDS),
        max_entries: int = MAX_PENDING_STATES,
    ) -> None:
        self._clock = clock
        self._ttl = ttl
        self._max_entries = max_entries
        self._pending_states: dict[str, PendingJiraOAuthState] = {}
        self._consumed_states: dict[str, datetime] = {}
        self._lock = Lock()

    def create_state(self, user_id: str) -> PendingJiraOAuthState:
        with self._lock:
            now = self._clock()
            self._cleanup(now)
            self._make_room()
            state = secrets.token_urlsafe(32)
            record = PendingJiraOAuthState(
                state=state,
                user_id=user_id,
                created_at=now,
                expires_at=now + self._ttl,
            )
            self._pending_states[state] = record
            return record

    def consume_state(
        self, state: str, expected_user_id: str | None = None
    ) -> PendingJiraOAuthState:
        with self._lock:
            now = self._clock()

            if state in self._consumed_states:
                raise JiraStateReusedError(
                    "OAuth state has already been consumed"
                )

            record = self._pending_states.pop(state, None)
            self._cleanup(now)

            if record is None:
                raise JiraStateInvalidError(
                    "OAuth state is invalid or unknown"
                )

            if record.expires_at <= now:
                raise JiraStateExpiredError("OAuth state has expired")

            if (
                expected_user_id is not None
                and record.user_id != expected_user_id
            ):
                raise JiraCrossUserStateError(
                    "OAuth state does not match the initiating user session"
                )

            self._consumed_states[state] = now
            return record

    def _cleanup(self, now: datetime) -> None:
        expired_pending = [
            st
            for st, rec in self._pending_states.items()
            if rec.expires_at <= now
        ]
        for st in expired_pending:
            self._pending_states.pop(st, None)

        consumed_cutoff = now - (self._ttl * 2)
        expired_consumed = [
            st
            for st, consumed_at in self._consumed_states.items()
            if consumed_at <= consumed_cutoff
        ]
        for st in expired_consumed:
            self._consumed_states.pop(st, None)

    def _make_room(self) -> None:
        if len(self._pending_states) >= self._max_entries:
            oldest_key = min(
                self._pending_states,
                key=lambda k: self._pending_states[k].created_at,
            )
            self._pending_states.pop(oldest_key, None)


# ---------------------------------------------------------------------------
# Atlassian Token Exchange & Refresh HTTP Client
# ---------------------------------------------------------------------------


class JiraOAuthClient:
    """Handles HTTP exchange and refresh of OAuth tokens with Atlassian's OAuth token endpoint."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout_seconds = timeout_seconds

    def exchange_code_for_tokens(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Perform server-to-server POST to exchange authorization code for access/refresh tokens.

        Security constraints:
        - NEVER logs or reveals client_secret, authorization code, or tokens.
        - Sanitizes error messages to prevent exposing upstream payloads.
        """
        payload = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        return self._post_token_request(payload, operation="authorization code exchange")

    def refresh_access_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Perform server-to-server POST to rotate and refresh an expired or near-expiry token.

        Security constraints:
        - Never logs or exposes tokens or secrets.
        - Translates 'invalid_grant' to JiraInvalidGrantError.
        """
        payload = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        return self._post_token_request(payload, operation="token refresh")

    def _post_token_request(
        self, payload: dict[str, Any], operation: str
    ) -> dict[str, Any]:
        try:
            response = httpx.post(
                ATLASSIAN_TOKEN_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise JiraNetworkTimeoutError(
                f"Atlassian OAuth {operation} timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise JiraNetworkError(
                f"Network error connecting to Atlassian OAuth endpoint during {operation}"
            ) from exc

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise JiraMalformedResponseError(
                f"Atlassian returned malformed response during {operation}"
            ) from exc

        if not isinstance(body, dict):
            raise JiraMalformedResponseError(
                f"Atlassian returned unexpected response payload during {operation}"
            )

        if response.status_code >= 400 or body.get("error"):
            error_code = str(body.get("error") or "")
            if error_code == "invalid_grant":
                raise JiraInvalidGrantError(
                    "Atlassian refresh token is invalid, expired, or revoked"
                )
            raise JiraTokenExchangeError(
                f"Atlassian rejected the OAuth {operation}"
            )

        access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise JiraMalformedResponseError(
                f"Atlassian response missing valid access_token during {operation}"
            )

        return body


# ---------------------------------------------------------------------------
# Jira OAuth Service
# ---------------------------------------------------------------------------


class JiraOAuthService:
    """Coordinates Jira Cloud OAuth 2.0 authorization, rotating token refresh, and connection lifecycle."""

    def __init__(
        self,
        configuration: JiraConfiguration | None,
        repository: JiraConnectionRepository,
        state_store: JiraStateStore,
        client: JiraOAuthClient,
        clock=utc_now,
        sync_repository: JiraSyncRepository | None = None,
    ) -> None:
        self._configuration = configuration
        self._repository = repository
        self._state_store = state_store
        self._client = client
        self._clock = clock
        self._sync_repository = sync_repository or JiraSyncRepository()
        self._refresh_lock = Lock()

    @property
    def is_configured(self) -> bool:
        return self._configuration is not None

    def get_status(self, user_id: str) -> JiraStatusResponse:
        """Retrieve connection status for the authenticated user without exposing tokens."""
        connection = self._repository.find_by_owner(user_id)
        if connection is None:
            return JiraStatusResponse(connected=False)

        if connection.get("status") == "REAUTHORIZATION_REQUIRED":
            return JiraStatusResponse(
                connected=False,
                reauthorization_required=True,
                connected_at=connection.get("connected_at"),
                expires_at=connection.get("expires_at"),
            )

        return JiraStatusResponse(
            connected=True,
            connected_at=connection.get("connected_at"),
            expires_at=connection.get("expires_at"),
        )

    def begin_connection(
        self, current_user: UserPublicResponse
    ) -> JiraConnectResponse:
        """Initiate OAuth flow: create user-bound state and return Atlassian authorization URL."""
        if self._configuration is None:
            raise JiraConfigurationError(
                "Jira Cloud OAuth client is not configured"
            )

        state_record = self._state_store.create_state(current_user.user_id)

        params = {
            "audience": ATLASSIAN_AUDIENCE,
            "client_id": self._configuration.client_id,
            "scope": " ".join(JIRA_SCOPES),
            "redirect_uri": self._configuration.redirect_uri,
            "state": state_record.state,
            "response_type": "code",
            "prompt": "consent",
        }
        authorization_url = f"{ATLASSIAN_AUTHORIZE_URL}?{urlencode(params)}"
        return JiraConnectResponse(authorization_url=authorization_url)

    def complete_connection(
        self,
        state: str | None,
        code: str | None,
        expected_user_id: str | None = None,
    ) -> JiraConnectionDocument:
        """Validate state, exchange authorization code, and persist connection."""
        if self._configuration is None:
            raise JiraConfigurationError(
                "Jira Cloud OAuth client is not configured"
            )

        if not state:
            raise JiraStateInvalidError("OAuth state is missing or empty")

        if not code:
            raise JiraMissingCodeError("Authorization code is required")

        state_record = self._state_store.consume_state(
            state, expected_user_id=expected_user_id
        )

        tokens = self._client.exchange_code_for_tokens(
            client_id=self._configuration.client_id,
            client_secret=self._configuration.client_secret,
            code=code,
            redirect_uri=self._configuration.redirect_uri,
        )

        now = self._clock()
        expires_in = tokens.get("expires_in")
        try:
            expires_seconds = int(expires_in) if expires_in is not None else 3600
        except (ValueError, TypeError):
            expires_seconds = 3600

        expires_at = now + timedelta(seconds=expires_seconds)
        scope = tokens.get("scope") or " ".join(JIRA_SCOPES)
        token_type = tokens.get("token_type") or "Bearer"
        refresh_token = tokens.get("refresh_token")

        connection = JiraConnectionDocument(
            owner_id=state_record.user_id,
            provider="JIRA",
            access_token=tokens["access_token"],
            refresh_token=refresh_token if isinstance(refresh_token, str) else None,
            expires_at=expires_at,
            connected_at=now,
            updated_at=now,
            scope=scope if isinstance(scope, str) else " ".join(JIRA_SCOPES),
            token_type=token_type if isinstance(token_type, str) else "Bearer",
            status="CONNECTED",
            reauthorization_reason=None,
            version=1,
        )

        self._repository.upsert(connection)
        return connection

    def get_valid_access_token(
        self, user_id: str, force_refresh: bool = False
    ) -> str:
        """Retrieve a valid access token for the authenticated user, refreshing if expired or near expiry.

        Behavior:
        - If no connection exists: raises JiraNotConnectedError.
        - If connection is marked REAUTHORIZATION_REQUIRED: raises JiraReauthorizationRequiredError.
        - If token is valid and not within safety window: returns existing token.
        - If token is expired, near expiry, or force_refresh is requested: rotates tokens via refresh.
        - Bounded synchronization avoids duplicate concurrent refreshes.
        """
        doc = self._repository.find_by_owner(user_id)
        if doc is None:
            raise JiraNotConnectedError(
                "User does not have an active Jira connection"
            )

        if doc.get("status") == "REAUTHORIZATION_REQUIRED":
            raise JiraReauthorizationRequiredError(
                "Jira connection requires reauthorization; credentials are invalid or revoked"
            )

        access_token = doc.get("access_token")
        if not access_token or not isinstance(access_token, str):
            self._repository.mark_reauthorization_required(
                user_id, "Missing access token"
            )
            raise JiraReauthorizationRequiredError(
                "Jira connection is missing access token; reauthorization required"
            )

        now = self._clock()
        expires_at = doc.get("expires_at")
        safety_margin = timedelta(seconds=REFRESH_SAFETY_MARGIN_SECONDS)
        is_near_expiry = (
            expires_at is None
            or not isinstance(expires_at, datetime)
            or (expires_at - safety_margin <= now)
        )

        if not force_refresh and not is_near_expiry:
            return access_token

        # Acquire lock to coordinate concurrent refresh attempts for this user
        with self._refresh_lock:
            # Re-read document under lock in case another worker already refreshed it
            doc = self._repository.find_by_owner(user_id)
            if doc is None:
                raise JiraNotConnectedError(
                    "User does not have an active Jira connection"
                )

            if doc.get("status") == "REAUTHORIZATION_REQUIRED":
                raise JiraReauthorizationRequiredError(
                    "Jira connection requires reauthorization"
                )

            current_expires = doc.get("expires_at")
            if (
                not force_refresh
                and current_expires
                and isinstance(current_expires, datetime)
                and (current_expires - safety_margin > self._clock())
            ):
                return doc["access_token"]

            refresh_token = doc.get("refresh_token")
            if not refresh_token or not isinstance(refresh_token, str):
                self._repository.mark_reauthorization_required(
                    user_id, "Missing refresh token"
                )
                raise JiraReauthorizationRequiredError(
                    "Missing refresh token; Jira reauthorization required"
                )

            if self._configuration is None:
                raise JiraConfigurationError(
                    "Jira Cloud OAuth credentials are not configured"
                )

            try:
                tokens = self._client.refresh_access_token(
                    client_id=self._configuration.client_id,
                    client_secret=self._configuration.client_secret,
                    refresh_token=refresh_token,
                )
            except JiraInvalidGrantError as exc:
                self._repository.mark_reauthorization_required(
                    user_id, "Refresh token revoked or invalid (invalid_grant)"
                )
                raise JiraReauthorizationRequiredError(
                    "Jira refresh token is invalid or expired; reauthorization required"
                ) from exc

            new_access_token = tokens.get("access_token")
            if not isinstance(new_access_token, str) or not new_access_token:
                raise JiraMalformedResponseError(
                    "Atlassian response missing valid access_token during token refresh"
                )

            refresh_time = self._clock()
            expires_in = tokens.get("expires_in")
            try:
                expires_seconds = int(expires_in) if expires_in is not None else 3600
            except (ValueError, TypeError):
                expires_seconds = 3600

            new_expires_at = refresh_time + timedelta(seconds=expires_seconds)
            new_refresh_token = tokens.get("refresh_token")

            # Atomically update rotated tokens in repository
            updated = self._repository.update_tokens_atomic(
                owner_id=user_id,
                expected_refresh_token=refresh_token,
                new_access_token=new_access_token,
                new_refresh_token=new_refresh_token if isinstance(new_refresh_token, str) and new_refresh_token.strip() else None,
                expires_at=new_expires_at,
                now=refresh_time,
            )

            if updated is None:
                # Another worker updated the token concurrently; reload fresh token
                fresh_doc = self._repository.find_by_owner(user_id)
                if fresh_doc and fresh_doc.get("access_token"):
                    return fresh_doc["access_token"]

            return new_access_token

    def mark_reauthorization_required(self, user_id: str, reason: str) -> None:
        """Mark a user's Jira connection as requiring reauthorization."""
        self._repository.mark_reauthorization_required(user_id, reason)

    def get_api_client(self, client: Any = None) -> Any:
        """Resolve or construct a JiraApiClient."""
        if client is not None:
            return client
        from app.modules.integrations.jira.client import JiraApiClient

        timeout = (
            self._configuration.timeout_seconds
            if self._configuration is not None
            else 10.0
        )
        return JiraApiClient(service=self, timeout_seconds=timeout)

    # -----------------------------------------------------------------------
    # Discovery & Selection Methods
    # -----------------------------------------------------------------------

    def get_sites(
        self, user_id: str, client: Any = None
    ) -> list[JiraSiteResponse]:
        """Fetch authorized Jira sites for the authenticated user without credentials.

        Requires an active Jira connection. Does not auto-select.
        """
        doc = self._repository.find_by_owner(user_id)
        if doc is None:
            raise JiraNotConnectedError(
                "User does not have an active Jira connection"
            )
        if doc.get("status") == "REAUTHORIZATION_REQUIRED":
            raise JiraReauthorizationRequiredError(
                "Jira connection requires reauthorization"
            )

        api_client = self.get_api_client(client)
        resources = api_client.get_accessible_resources(user_id)
        return [
            JiraSiteResponse(
                cloud_id=r.id,
                name=r.name,
                url=r.url,
                avatar_url=r.avatar_url,
            )
            for r in resources
        ]

    def select_site(
        self, user_id: str, cloud_id: str, client: Any = None
    ) -> JiraSelectedSite:
        """Select an authorized Jira Cloud site.

        Validates server-side that cloud_id is authorized and accessible.
        Invalidates previously selected project and board if cloud_id changes.
        """
        doc = self._repository.find_by_owner(user_id)
        if doc is None:
            raise JiraNotConnectedError(
                "User does not have an active Jira connection"
            )
        if doc.get("status") == "REAUTHORIZATION_REQUIRED":
            raise JiraReauthorizationRequiredError(
                "Jira connection requires reauthorization"
            )

        api_client = self.get_api_client(client)
        resources = api_client.get_accessible_resources(user_id)
        matched = next((r for r in resources if r.id == cloud_id), None)
        if matched is None:
            raise JiraSiteNotAccessibleError(
                f"Jira site '{cloud_id}' is not accessible or authorized for this user"
            )

        selected_site = JiraSelectedSite(
            cloud_id=matched.id,
            site_name=matched.name,
            site_url=matched.url,
            avatar_url=matched.avatar_url,
            selected_at=self._clock(),
        )
        self._repository.update_selected_site(user_id, selected_site)
        return selected_site

    def get_selected_site(self, user_id: str) -> JiraSelectedSite:
        """Retrieve the currently selected Jira site or raise JiraSiteNotSelectedError."""
        doc = self._repository.find_by_owner(user_id)
        if doc is None:
            raise JiraNotConnectedError(
                "User does not have an active Jira connection"
            )
        if doc.get("status") == "REAUTHORIZATION_REQUIRED":
            raise JiraReauthorizationRequiredError(
                "Jira connection requires reauthorization"
            )

        site_data = doc.get("selected_site")
        if not site_data:
            raise JiraSiteNotSelectedError(
                "A Jira site has not been selected yet"
            )
        return JiraSelectedSite.model_validate(site_data)

    def get_projects(
        self,
        user_id: str,
        start_at: int = 0,
        max_results: int = 50,
        client: Any = None,
    ) -> list[JiraProjectResponse]:
        """Fetch accessible Jira Software projects for the selected Jira site.

        Requires an active Jira connection and selected site.
        """
        site = self.get_selected_site(user_id)
        api_client = self.get_api_client(client)
        data = api_client.search_projects(
            user_id=user_id,
            cloud_id=site.cloud_id,
            start_at=start_at,
            max_results=max_results,
        )

        raw_projects = (
            data.get("values", [])
            if isinstance(data, dict)
            else []
        )
        projects: list[JiraProjectResponse] = []
        for p in raw_projects:
            if isinstance(p, dict) and "id" in p and "key" in p and "name" in p:
                avatar_urls = p.get("avatarUrls") or {}
                avatar_url = avatar_urls.get("48x48") or avatar_urls.get("32x32")
                projects.append(
                    JiraProjectResponse(
                        id=str(p["id"]),
                        key=str(p["key"]),
                        name=str(p["name"]),
                        project_type_key=str(p.get("projectTypeKey", "software")),
                        simplified=bool(p.get("simplified", False)),
                        avatar_url=avatar_url,
                    )
                )
        return projects

    def select_project(
        self,
        user_id: str,
        project_id: str | None,
        project_key: str | None,
        client: Any = None,
    ) -> JiraSelectedProject:
        """Select an accessible Jira project on the selected Jira site.

        Validates project accessibility server-side.
        Invalidates previously selected board if the project changes.
        """
        site = self.get_selected_site(user_id)
        identifier = project_key or project_id
        if not identifier:
            raise ValueError("Either project_id or project_key must be provided")

        api_client = self.get_api_client(client)
        try:
            project_data = api_client.get_project(
                user_id=user_id,
                cloud_id=site.cloud_id,
                project_id_or_key=identifier,
            )
        except (
            JiraResourceNotFoundError,
            JiraPermissionError,
            JiraRemoteApiError,
        ) as exc:
            raise JiraProjectNotAccessibleError(
                f"Project '{identifier}' is not found or not accessible on site '{site.site_name}'"
            ) from exc

        selected_project = JiraSelectedProject(
            project_id=str(project_data["id"]),
            project_key=str(project_data["key"]),
            project_name=str(project_data["name"]),
            project_type_key=str(project_data.get("projectTypeKey", "software")),
            selected_at=self._clock(),
        )
        self._repository.update_selected_project(user_id, selected_project)
        return selected_project

    def get_selected_project(self, user_id: str) -> JiraSelectedProject:
        """Retrieve the currently selected Jira project or raise JiraProjectNotSelectedError."""
        self.get_selected_site(user_id)  # Enforces hierarchy: site must be selected
        doc = self._repository.find_by_owner(user_id)
        proj_data = doc.get("selected_project") if doc else None
        if not proj_data:
            raise JiraProjectNotSelectedError(
                "A Jira project has not been selected yet"
            )
        return JiraSelectedProject.model_validate(proj_data)

    def get_scrum_boards(
        self,
        user_id: str,
        start_at: int = 0,
        max_results: int = 50,
        client: Any = None,
    ) -> list[JiraBoardResponse]:
        """Fetch Scrum boards associated with the selected Jira project.

        Restricts discovery to boards of type 'scrum'.
        """
        site = self.get_selected_site(user_id)
        project = self.get_selected_project(user_id)
        api_client = self.get_api_client(client)

        boards_data = api_client.get_scrum_boards(
            user_id=user_id,
            cloud_id=site.cloud_id,
            project_key_or_id=project.project_key or project.project_id,
            start_at=start_at,
            max_results=max_results,
        )

        raw_boards = (
            boards_data.get("values", [])
            if isinstance(boards_data, dict)
            else []
        )
        boards: list[JiraBoardResponse] = []
        for b in raw_boards:
            if isinstance(b, dict) and "id" in b and "name" in b:
                b_type = str(b.get("type", "scrum")).lower()
                if b_type == "scrum":
                    boards.append(
                        JiraBoardResponse(
                            id=int(b["id"]),
                            name=str(b["name"]),
                            type="scrum",
                        )
                    )
        return boards

    def select_board(
        self,
        user_id: str,
        board_id: int,
        client: Any = None,
    ) -> JiraSelectedBoard:
        """Select a Scrum board for the selected Jira project.

        Validates server-side that the board exists, is a Scrum board,
        and belongs/applies to the selected project.
        """
        site = self.get_selected_site(user_id)
        project = self.get_selected_project(user_id)
        api_client = self.get_api_client(client)

        try:
            board_data = api_client.get_board(
                user_id=user_id,
                cloud_id=site.cloud_id,
                board_id=board_id,
            )
        except (
            JiraResourceNotFoundError,
            JiraPermissionError,
            JiraRemoteApiError,
        ) as exc:
            raise JiraBoardNotAccessibleError(
                f"Board '{board_id}' was not found or is not accessible on site '{site.site_name}'"
            ) from exc

        board_type = str(board_data.get("type", "")).lower()
        if board_type != "scrum":
            raise JiraBoardNotScrumError(
                f"Board '{board_id}' is a {board_data.get('type')} board, but Scrum board is required"
            )

        # Verify board belongs to the selected project
        location = board_data.get("location") or {}
        loc_proj_id = str(location.get("projectId") or "")
        loc_proj_key = str(location.get("projectKey") or "")

        if loc_proj_id or loc_proj_key:
            if loc_proj_id != project.project_id and loc_proj_key != project.project_key:
                raise JiraBoardNotAccessibleError(
                    f"Board '{board_id}' belongs to project '{loc_proj_key or loc_proj_id}', not selected project '{project.project_key}'"
                )
        else:
            # Check if board is in the project's scrum boards list
            project_boards = api_client.get_scrum_boards(
                user_id=user_id,
                cloud_id=site.cloud_id,
                project_key_or_id=project.project_key or project.project_id,
            )
            valid_ids = [
                int(b["id"])
                for b in project_boards.get("values", [])
                if isinstance(b, dict) and "id" in b
            ]
            if board_id not in valid_ids:
                raise JiraBoardNotAccessibleError(
                    f"Board '{board_id}' is not associated with selected project '{project.project_key}'"
                )

        selected_board = JiraSelectedBoard(
            board_id=int(board_data["id"]),
            board_name=str(board_data["name"]),
            board_type="scrum",
            selected_at=self._clock(),
        )
        self._repository.update_selected_board(user_id, selected_board)
        return selected_board

    def get_context(self, user_id: str) -> JiraContextResponse:
        """Retrieve current Jira connection and selection state without exposing credentials."""
        doc = self._repository.find_by_owner(user_id)
        if doc is None or doc.get("status") == "REAUTHORIZATION_REQUIRED":
            return JiraContextResponse(
                connected=False,
                site=None,
                project=None,
                board=None,
            )

        site_data = doc.get("selected_site")
        site = (
            JiraContextSite(
                cloud_id=site_data["cloud_id"],
                name=site_data["site_name"],
                url=site_data.get("site_url"),
            )
            if site_data
            else None
        )

        proj_data = doc.get("selected_project")
        project = (
            JiraContextProject(
                id=proj_data["project_id"],
                key=proj_data["project_key"],
                name=proj_data["project_name"],
            )
            if proj_data
            else None
        )

        board_data = doc.get("selected_board")
        board = (
            JiraContextBoard(
                id=board_data["board_id"],
                name=board_data["board_name"],
                type=board_data.get("board_type", "scrum"),
            )
            if board_data
            else None
        )

        return JiraContextResponse(
            connected=True,
            site=site,
            project=project,
            board=board,
        )

    def disconnect(self, user_id: str) -> bool:
        """Remove the local Jira connection for the authenticated user.

        Note: Remote Atlassian token revocation is outside this scope; disconnect
        currently removes the AgileFlow-side connection and stored tokens.
        """
        return self._repository.delete_by_owner(user_id)

    def build_frontend_redirect_url(
        self,
        *,
        connected: bool = False,
        error_code: str | None = None,
    ) -> str:
        """Build safe frontend return URL with only a status/error indicator."""
        base_url = (
            self._configuration.frontend_return_url
            if self._configuration is not None
            else "http://localhost:5173/integrations/jira"
        )
        if error_code:
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}jira_error={error_code}"
        if connected:
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}jira_connected=true"
        return base_url

    def get_project_issue_types(
        self,
        user_id: str,
        client: Any = None,
    ) -> list[JiraIssueTypeResponse]:
        """Fetch and normalize available issue types for the currently selected Jira project."""
        site = self.get_selected_site(user_id)
        project = self.get_selected_project(user_id)
        api_client = self.get_api_client(client)

        raw_types = api_client.get_project_issue_types(
            user_id=user_id,
            cloud_id=site.cloud_id,
            project_id_or_key=project.project_key or project.project_id,
        )

        issue_types: list[JiraIssueTypeResponse] = []
        for item in raw_types:
            if not isinstance(item, dict) or "id" not in item or "name" not in item:
                continue
            is_subtask = bool(item.get("subtask", False))
            raw_hlevel = item.get("hierarchyLevel")
            if raw_hlevel is not None:
                try:
                    hierarchy_level = int(raw_hlevel)
                except (ValueError, TypeError):
                    hierarchy_level = -1 if is_subtask else (1 if str(item["name"]).lower() == "epic" else 0)
            else:
                hierarchy_level = -1 if is_subtask else (1 if str(item["name"]).lower() == "epic" else 0)

            issue_types.append(
                JiraIssueTypeResponse(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    subtask=is_subtask,
                    hierarchy_level=hierarchy_level,
                )
            )

        return issue_types

    def build_sync_preview(
        self,
        user_id: str,
        agent_project_id: str,
        mappings: dict[str, str],
        run_id: str | None = None,
        outputs: dict[str, Any] | None = None,
        client: Any = None,
        standalone_service: Any = None,
    ) -> JiraPreviewResponse:
        """Construct a deterministic Jira sync preview for Agent 2 planning results.

        Validates connection, target selections, planning artifacts, and issue-type mappings.
        Performs ZERO Jira write or mutation requests.
        """
        # 1. Connection check
        doc = self._repository.find_by_owner(user_id)
        if doc is None or doc.get("status") == "REAUTHORIZATION_REQUIRED":
            raise JiraNotConnectedError("Jira is not connected")

        # 2. Site check
        site = self.get_selected_site(user_id)

        # 3. Project check
        project = self.get_selected_project(user_id)

        # 4. Board check
        board_data = doc.get("selected_board") if doc else None
        if not board_data:
            raise JiraBoardNotSelectedError("A Scrum board has not been selected yet")
        board = JiraSelectedBoard.model_validate(board_data)

        # 5. Resolve Agent 2 outputs
        resolved_outputs: dict[str, Any] | None = None
        if outputs and isinstance(outputs, dict) and "JIRA_PLAN" in outputs:
            resolved_outputs = outputs
        elif standalone_service is not None:
            user_ctx = UserPublicResponse(
                user_id=user_id,
                name="User",
                email="user@example.com",
                is_active=True,
                created_at=self._clock(),
                updated_at=self._clock(),
            )
            try:
                if run_id:
                    run = standalone_service.get_run(agent_project_id, run_id, user_ctx)
                    resolved_outputs = run.output_manifest if hasattr(run, "output_manifest") else {}
                else:
                    runs = standalone_service.list_runs(agent_project_id, user_ctx)
                    for r in reversed(runs):
                        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)
                        if status_val == "COMPLETED" and "JIRA_PLAN" in (r.output_manifest or {}):
                            resolved_outputs = r.output_manifest
                            break
            except Exception as exc:
                if isinstance(exc, JiraIntegrationError):
                    raise
                raise JiraPlanUnavailableError(
                    f"Could not load completed Agent 2 run: {exc}"
                ) from exc

        if not resolved_outputs or "JIRA_PLAN" not in resolved_outputs:
            raise JiraPlanUnavailableError(
                "A completed Agent 2 run with JIRA_PLAN is required for sync preview"
            )

        jira_plan = resolved_outputs["JIRA_PLAN"]
        if not isinstance(jira_plan, dict):
            raise JiraPlanUnavailableError("JIRA_PLAN must be a dictionary")

        # 6. Retrieve available project issue types
        project_issue_types = self.get_project_issue_types(user_id=user_id, client=client)
        by_name = {t.name.lower(): t for t in project_issue_types}
        by_id = {t.id: t for t in project_issue_types}

        # 7. Validate issue-type mappings
        normalized_mappings: dict[str, str] = {}
        for k, v in mappings.items():
            if isinstance(k, str) and v is not None and str(v).strip():
                norm_key = k.strip().upper()
                if norm_key in ("EPIC", "FEATURE", "USER_STORY", "TASK"):
                    normalized_mappings[norm_key] = str(v).strip()

        epics_list = jira_plan.get("epics") or []
        stories_list = jira_plan.get("stories") or []
        tasks_list = jira_plan.get("tasks") or []
        features_list = resolved_outputs.get("FEATURES") or []

        has_epics = len(epics_list) > 0
        has_stories = len(stories_list) > 0
        has_tasks = len(tasks_list) > 0
        has_features = len(features_list) > 0 or any(
            isinstance(s, dict) and bool(s.get("feature_id")) for s in stories_list
        )

        if has_epics and not normalized_mappings.get("EPIC"):
            raise JiraMappingIncompleteError("Mapping for artifact type 'EPIC' is required")
        if has_stories and not normalized_mappings.get("USER_STORY"):
            raise JiraMappingIncompleteError("Mapping for artifact type 'USER_STORY' is required")
        if has_tasks and not normalized_mappings.get("TASK"):
            raise JiraMappingIncompleteError("Mapping for artifact type 'TASK' is required")
        if has_features and not normalized_mappings.get("FEATURE"):
            raise JiraMappingIncompleteError(
                "Mapping for artifact type 'FEATURE' is required because Feature items are present in planning output"
            )

        resolved_jira_types: dict[str, str] = {}
        warnings: list[str] = []

        for artifact_type, mapped_val in normalized_mappings.items():
            val_str = str(mapped_val).strip()
            matched_type = by_name.get(val_str.lower()) or by_id.get(val_str)
            if matched_type is None:
                raise JiraIssueTypeUnavailableError(
                    f"Jira issue type '{mapped_val}' for '{artifact_type}' is not available in project '{project.project_key}'"
                )
            resolved_jira_types[artifact_type] = matched_type.name

            if artifact_type == "FEATURE":
                if matched_type.name.lower() in ("story", "user story", "task"):
                    warnings.append(
                        f"Feature mapped to '{matched_type.name}': Jira project '{project.project_key}' lacks a native Feature issue type; features will be previewed as {matched_type.name} issues."
                    )
            if artifact_type == "TASK" and matched_type.subtask:
                warnings.append(
                    "Task is mapped to a Jira subtask type. Subtasks will be attached as direct children of standard issues."
                )

        # 8. Validate hierarchy references
        epic_ids = {e["id"] for e in epics_list if isinstance(e, dict) and "id" in e}
        feature_ids = {f["id"] for f in features_list if isinstance(f, dict) and "id" in f}
        story_ids = {s["id"] for s in stories_list if isinstance(s, dict) and "id" in s}

        for story in stories_list:
            if isinstance(story, dict):
                s_epic = story.get("epic_id")
                if s_epic and s_epic not in epic_ids:
                    raise JiraHierarchyInvalidError(
                        f"Story '{story.get('id')}' references non-existent Epic '{s_epic}'"
                    )
                s_feat = story.get("feature_id")
                if s_feat and feature_ids and s_feat not in feature_ids:
                    raise JiraHierarchyInvalidError(
                        f"Story '{story.get('id')}' references non-existent Feature '{s_feat}'"
                    )

        for task in tasks_list:
            if isinstance(task, dict):
                t_story = task.get("story_id")
                if t_story and t_story not in story_ids:
                    raise JiraHierarchyInvalidError(
                        f"Task '{task.get('id')}' references non-existent Story '{t_story}'"
                    )

        # 9. Build Sprints and item mappings
        raw_sprints = jira_plan.get("sprints") or resolved_outputs.get("SPRINT_PLAN") or []
        item_sprint_map: dict[str, str] = {}
        preview_sprints: list[JiraPreviewSprint] = []

        for s in raw_sprints:
            if not isinstance(s, dict):
                continue
            s_id = str(s.get("id", ""))
            s_name = str(s.get("name", s_id))
            s_refs = [str(r) for r in s.get("item_refs", [])]
            for ref in s_refs:
                item_sprint_map[ref] = s_name

            preview_sprints.append(
                JiraPreviewSprint(
                    id=s_id,
                    name=s_name,
                    planned_points=int(s.get("planned_points", 0)),
                    duration_days=int(s.get("duration_days", 14)),
                    start_date=s.get("start_date"),
                    end_date=s.get("end_date"),
                    item_count=len(s_refs),
                )
            )

        priorities_list = jira_plan.get("priorities") or []
        item_priority_map: dict[str, str] = {
            str(p["item_id"]): str(p["priority"])
            for p in priorities_list
            if isinstance(p, dict) and "item_id" in p and "priority" in p
        }

        # 10. Build Preview Issues
        issues: list[JiraPreviewIssue] = []
        total_points = 0

        # Epics
        for e in epics_list:
            if not isinstance(e, dict):
                continue
            issues.append(
                JiraPreviewIssue(
                    artifact_id=str(e["id"]),
                    agileflow_type="EPIC",
                    jira_issue_type=resolved_jira_types["EPIC"],
                    summary=str(e.get("title", "")),
                    parent_id=None,
                    planned_sprint=None,
                    assignee=None,
                    priority=e.get("priority") or item_priority_map.get(str(e["id"]), "MEDIUM"),
                    estimate_points=None,
                )
            )

        # Features (if present and mapped)
        if "FEATURE" in resolved_jira_types:
            for f in features_list:
                if not isinstance(f, dict):
                    continue
                issues.append(
                    JiraPreviewIssue(
                        artifact_id=str(f["id"]),
                        agileflow_type="FEATURE",
                        jira_issue_type=resolved_jira_types["FEATURE"],
                        summary=str(f.get("title", "")),
                        parent_id=f.get("epic_id"),
                        planned_sprint=item_sprint_map.get(str(f["id"])),
                        assignee=None,
                        priority=item_priority_map.get(str(f["id"]), "MEDIUM"),
                        estimate_points=None,
                    )
                )

        # Stories
        for st in stories_list:
            if not isinstance(st, dict):
                continue
            summary = st.get("title") or (
                f"{st.get('actor')}: {st.get('goal')}"
                if st.get("actor") and st.get("goal")
                else "User Story"
            )
            pts = st.get("estimate_points")
            if pts:
                try:
                    total_points += int(pts)
                except (ValueError, TypeError):
                    pass
            issues.append(
                JiraPreviewIssue(
                    artifact_id=str(st["id"]),
                    agileflow_type="USER_STORY",
                    jira_issue_type=resolved_jira_types["USER_STORY"],
                    summary=str(summary),
                    parent_id=st.get("feature_id") or st.get("epic_id"),
                    planned_sprint=item_sprint_map.get(str(st["id"])) or st.get("planned_sprint"),
                    assignee=None,
                    priority=st.get("priority") or item_priority_map.get(str(st["id"]), "MEDIUM"),
                    estimate_points=int(pts) if pts is not None else None,
                )
            )

        # Tasks
        for t in tasks_list:
            if not isinstance(t, dict):
                continue
            pts = t.get("estimate_points")
            if pts:
                try:
                    total_points += int(pts)
                except (ValueError, TypeError):
                    pass
            issues.append(
                JiraPreviewIssue(
                    artifact_id=str(t["id"]),
                    agileflow_type="TASK",
                    jira_issue_type=resolved_jira_types["TASK"],
                    summary=str(t.get("title", "")),
                    parent_id=t.get("story_id") or t.get("feature_id") or t.get("epic_id"),
                    planned_sprint=item_sprint_map.get(str(t["id"])) or t.get("planned_sprint"),
                    assignee=None,
                    priority=item_priority_map.get(str(t["id"]), "MEDIUM"),
                    estimate_points=int(pts) if pts is not None else None,
                )
            )

        # 11. Summary
        summary = JiraPreviewSummary(
            total_issues=len(issues),
            total_sprints=len(preview_sprints),
            epic_count=len(epics_list),
            feature_count=len([i for i in issues if i.agileflow_type == "FEATURE"]),
            story_count=len(stories_list),
            task_count=len(tasks_list),
            total_points=total_points,
        )

        # 12. Target
        target = JiraPreviewTarget(
            site=JiraContextSite(
                cloud_id=site.cloud_id,
                name=site.site_name,
                url=site.site_url,
            ),
            project=JiraContextProject(
                id=project.project_id,
                key=project.project_key,
                name=project.project_name,
            ),
            board=JiraContextBoard(
                id=board.board_id,
                name=board.board_name,
                type=board.board_type,
            ),
        )

        return JiraPreviewResponse(
            target=target,
            mappings=resolved_jira_types,
            sprints=preview_sprints,
            issues=issues,
            summary=summary,
            warnings=warnings,
            synchronization_status="NOT_PERFORMED",
        )

    def execute_sync(
        self,
        user_id: str,
        request: JiraSyncExecuteRequest,
        client: Any = None,
        standalone_service: Any = None,
    ) -> JiraSyncResultResponse:
        """Execute Jira synchronization for an approved Agent 2 plan.

        Hard HITL boundary:
        - Requires valid generated sync preview.
        - Requires explicit human confirmation (request.confirmation == True).
        - Generates sprints, creates unassigned issues preserving hierarchy,
          places issues into sprints, stores traceability, and records result
          (COMPLETED, PARTIAL, or FAILED).
        - Idempotent: checks stored traceability and skips creating already-traced
          sprints/issues. Safe to resume/retry.
        - NEVER mutates Agent 2 run status or AgentRun documents.
        """
        # 1. Hard HITL boundary check
        if not request.confirmation:
            raise JiraConfirmationRequiredError(
                "Explicit human confirmation is required to execute Jira synchronization"
            )

        # 2. Authenticated user ownership & run check
        effective_run_id = request.run_id or ""
        resolved_outputs = request.outputs or {}

        if standalone_service is not None:
            user_ctx = UserPublicResponse(
                user_id=user_id,
                name="User",
                email="user@example.com",
                is_active=True,
                created_at=self._clock(),
                updated_at=self._clock(),
            )
            try:
                if request.run_id:
                    run = standalone_service.get_run(
                        request.agent_project_id, request.run_id, user_ctx
                    )
                else:
                    runs = standalone_service.list_runs(
                        request.agent_project_id, user_ctx
                    )
                    completed_runs = [
                        r
                        for r in runs
                        if (
                            r.status.value
                            if hasattr(r.status, "value")
                            else str(r.status)
                        )
                        == "COMPLETED"
                        and "JIRA_PLAN" in (r.output_manifest or {})
                    ]
                    if not completed_runs:
                        raise JiraRunNotCompletedError(
                            "No completed Agent 2 run with JIRA_PLAN found"
                        )
                    run = completed_runs[-1]
            except Exception as exc:
                if (
                    "Unauthorized" in type(exc).__name__
                    or "Forbidden" in type(exc).__name__
                    or "Permission" in type(exc).__name__
                ):
                    raise JiraUnauthorizedProjectAccessError(
                        f"User does not have access to project '{request.agent_project_id}'"
                    ) from exc
                if isinstance(exc, JiraIntegrationError):
                    raise
                raise JiraPlanUnavailableError(
                    f"Could not load Agent 2 run: {exc}"
                ) from exc

            # Run must be COMPLETED
            status_val = (
                run.status.value
                if hasattr(run.status, "value")
                else str(run.status)
            )
            if status_val != "COMPLETED":
                raise JiraRunNotCompletedError(
                    f"Agent 2 run '{run.run_id}' has status '{status_val}'; must be COMPLETED to synchronize"
                )

            effective_run_id = getattr(run, "run_id", effective_run_id)
            if not resolved_outputs:
                resolved_outputs = getattr(run, "output_manifest", None) or {}

        if not effective_run_id:
            effective_run_id = "RUN-AGENT2"

        # 3. Check for concurrent active synchronization for this run
        active_sync = self._sync_repository.find_active_by_run(
            request.agent_project_id, effective_run_id
        )
        if active_sync:
            raise JiraSyncInProgressError(
                f"A synchronization operation is already in progress for run '{effective_run_id}'"
            )

        # 4. Generate/validate preview server-side
        preview = self.build_sync_preview(
            user_id=user_id,
            agent_project_id=request.agent_project_id,
            mappings=request.mappings,
            run_id=effective_run_id,
            outputs=resolved_outputs,
            client=client,
            standalone_service=standalone_service,
        )

        # 5. Check persisted traceability for idempotency & resuming
        existing_sync = self._sync_repository.find_latest_by_run(
            request.agent_project_id, effective_run_id
        )

        # If already COMPLETED, return completed result directly without new writes
        if existing_sync and existing_sync.get("status") == "COMPLETED":
            return self._format_sync_response(existing_sync, preview.target)

        # Load existing traces if resuming from PARTIAL or FAILED
        sprints_trace: dict[str, JiraSprintTrace] = {}
        issues_trace: dict[str, JiraIssueTrace] = {}
        placements_trace: dict[str, bool] = {}
        failures: list[JiraSyncFailure] = []
        warnings: list[str] = list(preview.warnings)

        if existing_sync:
            for k, v in existing_sync.get("sprints_trace", {}).items():
                if isinstance(v, dict):
                    sprints_trace[k] = JiraSprintTrace.model_validate(v)
                elif isinstance(v, JiraSprintTrace):
                    sprints_trace[k] = v
            for k, v in existing_sync.get("issues_trace", {}).items():
                if isinstance(v, dict):
                    issues_trace[k] = JiraIssueTrace.model_validate(v)
                elif isinstance(v, JiraIssueTrace):
                    issues_trace[k] = v
            placements_trace = dict(existing_sync.get("placements_trace", {}))

        sync_id = (
            existing_sync.get("sync_id")
            if existing_sync and existing_sync.get("status") in ("PARTIAL", "FAILED")
            else f"SYNC-{uuid.uuid4().hex[:12].upper()}"
        )

        now = self._clock()
        planned_placements = sum(
            1
            for i in preview.issues
            if i.planned_sprint and i.agileflow_type != "EPIC"
        )

        # Mark IN_PROGRESS in persistence
        sync_doc = JiraSyncDocument(
            sync_id=sync_id,
            user_id=user_id,
            agent_project_id=request.agent_project_id,
            run_id=effective_run_id,
            cloud_id=preview.target.site.cloud_id,
            site_name=preview.target.site.name,
            site_url=preview.target.site.url,
            project_id=preview.target.project.id,
            project_key=preview.target.project.key,
            project_name=preview.target.project.name,
            board_id=preview.target.board.id,
            board_name=preview.target.board.name,
            mappings=preview.mappings,
            status="IN_PROGRESS",
            created_at=existing_sync.get("created_at") if existing_sync else now,
            started_at=now,
            updated_at=now,
            sprint_summary=JiraSyncCounts(planned=len(preview.sprints)),
            issue_summary=JiraSyncCounts(planned=len(preview.issues)),
            placement_summary=JiraSyncCounts(planned=planned_placements),
            sprints_trace=sprints_trace,
            issues_trace=issues_trace,
            placements_trace=placements_trace,
            warnings=warnings,
            failures=failures,
        )
        self._sync_repository.upsert(sync_doc)

        api_client = self.get_api_client(client)

        sprints_created = 0
        sprints_reused = 0
        sprints_failed = 0

        # 6. Create Sprints (idempotent)
        for sp in preview.sprints:
            sp_id = getattr(sp, "id", None) or getattr(sp, "sprint_id", "")
            if sp_id in sprints_trace and sprints_trace[sp_id].jira_sprint_id:
                sprints_reused += 1
                sprints_trace[sp_id].reused = True
                continue

            try:
                jira_sprint = api_client.create_sprint(
                    user_id=user_id,
                    cloud_id=preview.target.site.cloud_id,
                    origin_board_id=preview.target.board.id,
                    name=sp.name,
                    start_date=sp.start_date,
                    end_date=sp.end_date,
                    goal=getattr(sp, "goal", None),
                )
                j_sprint_id = int(jira_sprint.get("id"))
                sprints_trace[sp_id] = JiraSprintTrace(
                    agileflow_sprint_id=sp_id,
                    jira_sprint_id=j_sprint_id,
                    name=sp.name,
                    state=jira_sprint.get("state", "future"),
                    reused=False,
                    created_at=self._clock(),
                )
                sprints_created += 1
            except Exception as exc:
                sprints_failed += 1
                err_msg = str(exc)
                failures.append(
                    JiraSyncFailure(
                        entity_type="SPRINT",
                        entity_id=sp_id,
                        error=err_msg,
                    )
                )
                warnings.append(f"Failed to create sprint '{sp.name}': {err_msg}")

        # 7. Create Issues in hierarchy order (EPIC -> FEATURE -> USER_STORY -> TASK)
        issues_created = 0
        issues_reused = 0
        issues_failed = 0

        hierarchy_rank = {"EPIC": 0, "FEATURE": 1, "USER_STORY": 2, "TASK": 3}
        sorted_issues = sorted(
            preview.issues,
            key=lambda item: hierarchy_rank.get(item.agileflow_type, 99),
        )

        for issue in sorted_issues:
            art_id = issue.artifact_id
            if art_id in issues_trace and issues_trace[art_id].jira_key:
                issues_reused += 1
                issues_trace[art_id].reused = True
                continue

            # Determine parent Jira key if applicable
            parent_key = None
            if issue.parent_id:
                parent_trace = issues_trace.get(issue.parent_id)
                if parent_trace and parent_trace.jira_key:
                    parent_key = parent_trace.jira_key
                else:
                    # Parent was not created or failed
                    issues_failed += 1
                    err_msg = f"Parent artifact '{issue.parent_id}' was not created in Jira"
                    failures.append(
                        JiraSyncFailure(
                            entity_type="ISSUE",
                            entity_id=art_id,
                            error=err_msg,
                        )
                    )
                    warnings.append(f"Skipping issue '{issue.summary}': {err_msg}")
                    continue

            try:
                # Description preserving AgileFlow artifact reference
                desc_text = f"AgileFlow Artifact ID: {art_id}\nType: {issue.agileflow_type}"
                if issue.planned_sprint:
                    desc_text += f"\nPlanned Sprint: {issue.planned_sprint}"

                created = api_client.create_issue(
                    user_id=user_id,
                    cloud_id=preview.target.site.cloud_id,
                    project_key=preview.target.project.key,
                    issue_type_name=issue.jira_issue_type,
                    summary=issue.summary,
                    description=desc_text,
                    parent_key_or_id=parent_key,
                )
                j_id = str(created.get("id"))
                j_key = str(created.get("key"))
                browse_url = (
                    f"{preview.target.site.url.rstrip('/')}/browse/{j_key}"
                    if preview.target.site.url
                    else None
                )

                issues_trace[art_id] = JiraIssueTrace(
                    artifact_id=art_id,
                    jira_id=j_id,
                    jira_key=j_key,
                    agileflow_type=issue.agileflow_type,
                    jira_issue_type=issue.jira_issue_type,
                    summary=issue.summary,
                    parent_id=issue.parent_id,
                    parent_jira_key=parent_key,
                    planned_sprint=issue.planned_sprint,
                    browse_url=browse_url,
                    reused=False,
                    created_at=self._clock(),
                )
                issues_created += 1
            except Exception as exc:
                issues_failed += 1
                err_msg = str(exc)
                failures.append(
                    JiraSyncFailure(
                        entity_type="ISSUE",
                        entity_id=art_id,
                        error=err_msg,
                    )
                )
                warnings.append(f"Failed to create issue '{issue.summary}': {err_msg}")

        # 8. Place issues into planned sprints
        placements_placed = 0
        placements_failed = 0

        for issue in preview.issues:
            if not issue.planned_sprint or issue.agileflow_type == "EPIC":
                continue

            issue_trace = issues_trace.get(issue.artifact_id)
            if not issue_trace or not issue_trace.jira_key:
                continue

            sprint_trace = sprints_trace.get(issue.planned_sprint)
            if not sprint_trace:
                for st in sprints_trace.values():
                    if st.name == issue.planned_sprint or st.agileflow_sprint_id == issue.planned_sprint:
                        sprint_trace = st
                        break

            if not sprint_trace or not sprint_trace.jira_sprint_id:
                placements_failed += 1
                failures.append(
                    JiraSyncFailure(
                        entity_type="PLACEMENT",
                        entity_id=f"{issue.artifact_id}->{issue.planned_sprint}",
                        error=f"Sprint '{issue.planned_sprint}' was not created in Jira",
                    )
                )
                continue

            placement_key = f"{issue.artifact_id}:{sprint_trace.jira_sprint_id}"
            if placements_trace.get(placement_key):
                placements_placed += 1
                issue_trace.jira_sprint_id = sprint_trace.jira_sprint_id
                continue

            try:
                api_client.add_issues_to_sprint(
                    user_id=user_id,
                    cloud_id=preview.target.site.cloud_id,
                    sprint_id=sprint_trace.jira_sprint_id,
                    issue_keys=[issue_trace.jira_key],
                )
                placements_trace[placement_key] = True
                issue_trace.jira_sprint_id = sprint_trace.jira_sprint_id
                placements_placed += 1
            except Exception as exc:
                placements_failed += 1
                err_msg = str(exc)
                failures.append(
                    JiraSyncFailure(
                        entity_type="PLACEMENT",
                        entity_id=f"{issue.artifact_id}->{sprint_trace.jira_sprint_id}",
                        error=err_msg,
                    )
                )
                warnings.append(
                    f"Failed to place issue '{issue_trace.jira_key}' into sprint {sprint_trace.jira_sprint_id}: {err_msg}"
                )

        # 9. Determine overall status
        if len(failures) == 0:
            overall_status = "COMPLETED"
        elif (sprints_created + sprints_reused == 0) and (
            issues_created + issues_reused == 0
        ):
            overall_status = "FAILED"
        else:
            overall_status = "PARTIAL"

        completed_time = self._clock()
        sync_doc.status = overall_status
        sync_doc.completed_at = completed_time
        sync_doc.updated_at = completed_time
        sync_doc.sprint_summary = JiraSyncCounts(
            planned=len(preview.sprints),
            created=sprints_created,
            reused=sprints_reused,
            failed=sprints_failed,
        )
        sync_doc.issue_summary = JiraSyncCounts(
            planned=len(preview.issues),
            created=issues_created,
            reused=issues_reused,
            failed=issues_failed,
        )
        sync_doc.placement_summary = JiraSyncCounts(
            planned=planned_placements,
            created=placements_placed,
            reused=0,
            failed=placements_failed,
        )
        sync_doc.sprints_trace = sprints_trace
        sync_doc.issues_trace = issues_trace
        sync_doc.placements_trace = placements_trace
        sync_doc.warnings = warnings
        sync_doc.failures = failures

        self._sync_repository.upsert(sync_doc)

        return self._format_sync_response(sync_doc, preview.target)

    def get_sync_status(
        self,
        user_id: str,
        agent_project_id: str,
        run_id: str,
    ) -> JiraSyncResultResponse | None:
        """Retrieve latest synchronization status and traceability for a run."""
        doc = self._sync_repository.find_latest_by_run(agent_project_id, run_id)
        if not doc:
            return None
        return self._format_sync_response(doc)

    def _format_sync_response(
        self,
        doc_data: dict[str, Any] | JiraSyncDocument,
        target: JiraPreviewTarget | None = None,
    ) -> JiraSyncResultResponse:
        """Format an internal sync document into safe, browseable result response."""
        if isinstance(doc_data, dict):
            doc = JiraSyncDocument.model_validate(doc_data)
        else:
            doc = doc_data

        if target is None:
            target = JiraPreviewTarget(
                site=JiraContextSite(
                    cloud_id=doc.cloud_id,
                    name=doc.site_name,
                    url=doc.site_url,
                ),
                project=JiraContextProject(
                    id=doc.project_id,
                    key=doc.project_key,
                    name=doc.project_name,
                ),
                board=JiraContextBoard(
                    id=doc.board_id,
                    name=doc.board_name,
                    type="scrum",
                ),
            )

        return JiraSyncResultResponse(
            sync_id=doc.sync_id,
            status=doc.status,
            target=target,
            sprint_summary=doc.sprint_summary,
            issue_summary=doc.issue_summary,
            placement_summary=doc.placement_summary,
            traceability={
                "sprints": [s.model_dump(mode="python") for s in doc.sprints_trace.values()],
                "issues": [i.model_dump(mode="python") for i in doc.issues_trace.values()],
            },
            warnings=doc.warnings,
            failures=doc.failures,
            created_at=doc.created_at,
            completed_at=doc.completed_at,
        )
