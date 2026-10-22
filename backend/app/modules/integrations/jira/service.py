"""Service and state-management layer for Jira Cloud OAuth 2.0 (3LO)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets
from threading import Lock
from typing import Any
from urllib.parse import urlencode

import httpx

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
)
from app.modules.integrations.jira.schemas import (
    JiraConnectResponse,
    JiraConnectionDocument,
    JiraStatusResponse,
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

    error_code: str = "JIRA_RATE_LIMIT"


class JiraRemoteApiError(JiraApiClientError):
    """Raised when Atlassian returns an unexpected error (e.g. 5xx)."""

    error_code: str = "JIRA_REMOTE_API_ERROR"


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
    ) -> None:
        self._configuration = configuration
        self._repository = repository
        self._state_store = state_store
        self._client = client
        self._clock = clock
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
                new_refresh_token=new_refresh_token if isinstance(new_refresh_token, str) else None,
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
